# sports_betting_analyzer.py
# Versão reescrita — tipster inteligente (pré-jogo), endpoints organizados, sem emojis.

import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from collections import Counter

# -------------------------
# App + CORS
# -------------------------
app = FastAPI(title="Sports Betting Analyzer - Tipster", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajustar para produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Models
# -------------------------
class TipInfo(BaseModel):
    market: str
    suggestion: str
    justification: str
    confidence: int


# -------------------------
# Config / Sports map
# -------------------------
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY não definida no ambiente. Configure a variável de ambiente API_KEY.")

# key header naming: alguns planos/API usam x-apisports-key; mantendo compatibilidade com x-rapidapi-key também
DEFAULT_HEADERS = {"x-rapidapi-key": API_KEY, "x-apisports-key": API_KEY}

TIMEOUT = 30  # segundos

SPORTS_MAP = {
    "football": {"host": "v3.football.api-sports.io", "type": "fixtures"},
    "basketball": {"host": "v1.basketball.api-sports.io", "type": "games"},
    "nba": {"host": "v2.nba.api-sports.io", "type": "games"},
    "baseball": {"host": "v1.baseball.api-sports.io", "type": "games"},
    "formula-1": {"host": "v1.formula-1.api-sports.io", "type": "races"},
    "handball": {"host": "v1.handball.api-sports.io", "type": "games"},
    "hockey": {"host": "v1.hockey.api-sports.io", "type": "games"},
    "mma": {"host": "v1.mma.api-sports.io", "type": "events"},
    "american-football": {"host": "v1.american-football.api-sports.io", "type": "games"},
    "rugby": {"host": "v1.rugby.api-sports.io", "type": "games"},
    "volleyball": {"host": "v1.volleyball.api-sports.io", "type": "games"},
    "afl": {"host": "v1.afl.api-sports.io", "type": "games"},
}

# -------------------------
# Helper: async GET with retries
# -------------------------
async def _get_json_async(url: str, params: dict = None, headers: dict = None) -> dict:
    headers = headers or DEFAULT_HEADERS
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        # retornar estrutura vazia para o tipster lidar
        return {}
    except Exception:
        return {}

# -------------------------
# Utility parsers
# -------------------------
def safe_get_response(json_obj: dict) -> list:
    """Padrão da api-sports: response dentro do JSON"""
    if not json_obj:
        return []
    if isinstance(json_obj, dict) and "response" in json_obj:
        return json_obj.get("response") or []
    return []

def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0

def _get_winner_id_from_game_generic(game: Dict) -> Optional[int]:
    # tenta várias formas de extrair vencedor
    teams = game.get("teams", {})
    scores = game.get("scores", {}) or {}
    # 1) flags winner boolean
    try:
        if teams.get("home", {}).get("winner") is True:
            return teams.get("home", {}).get("id")
        if teams.get("away", {}).get("winner") is True:
            return teams.get("away", {}).get("id")
    except Exception:
        pass
    # 2) scores simples (home/away) ou nested points
    home_score = scores.get("home")
    away_score = scores.get("away")
    if home_score is None or away_score is None:
        # tentar keys internas
        hs = scores.get("home", {})
        as_ = scores.get("away", {})
        home_score = hs.get("points") if isinstance(hs, dict) else hs
        away_score = as_.get("points") if isinstance(as_, dict) else as_
    try:
        if home_score is None or away_score is None:
            return None
        h = int(home_score)
        a = int(away_score)
        if h > a:
            return teams.get("home", {}).get("id")
        if a > h:
            return teams.get("away", {}).get("id")
    except Exception:
        return None
    return None

# -------------------------
# Core analyzer: team sports pre-game
# -------------------------
async def analyze_team_sport_pre_game(game_id: int, sport: str) -> List[TipInfo]:
    """
    Tipster principal para esportes de equipe (football, basketball, nba, etc.)
    Estratégia:
     - buscar dados do jogo (fixtures/games)
     - buscar H2H (headtohead) quando disponível
     - buscar forma recente (últimos N jogos)
     - usar odds (se disponível) para ajustar confiança
     - fallback: vantagem casa
    """
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    host = config["host"]
    kind = config["type"]  # 'fixtures' ou 'games'
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}

    base = f"https://{host}"

    # 1) buscar info do jogo (fixture/game)
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    res = await _get_json_async(f"{base}{endpoint}", params={"id": game_id}, headers=headers)
    resp_list = safe_get_response(res)
    if not resp_list:
        # tentar variações (algumas APIs retornam objeto direto)
        return [TipInfo(market="Erro", suggestion="Dados não encontrados", justification="Não foi possível carregar dados do jogo pela API.", confidence=0)]

    game = resp_list[0]
    # extrair ids e nomes
    home = game.get("teams", {}).get("home") or {}
    away = game.get("teams", {}).get("away") or {}
    home_id = home.get("id")
    away_id = away.get("id")
    home_name = home.get("name", "Time da Casa")
    away_name = away.get("name", "Visitante")

    tips: List[TipInfo] = []

    # 2) H2H
    # endpoints diferem: para football existe /fixtures/headtohead?h2h=home-away
    h2h_res = {}
    if sport == "football":
        # endpoint explicitamente de headtohead
        h2h_res = await _get_json_async(f"{base}/fixtures/headtohead", params={"h2h": f"{home_id}-{away_id}"}, headers=headers)
    else:
        # muitos endpoints suportam param h2h no mesmo resource
        h2h_res = await _get_json_async(f"{base}{endpoint}", params={"h2h": f"{home_id}-{away_id}"}, headers=headers)

    h2h_list = safe_get_response(h2h_res)
    if h2h_list:
        winner_ids = [_get_winner_id_from_game_generic(g) for g in h2h_list]
        win_counts = Counter(winner_ids)
        home_wins = win_counts.get(home_id, 0)
        away_wins = win_counts.get(away_id, 0)
        total = max(1, len(h2h_list))
        if home_wins > away_wins:
            confidence = 50 + int((home_wins / total) * 30)
            tips.append(TipInfo(
                market="Vencedor (H2H)",
                suggestion=f"Vitória do {home_name}",
                justification=f"{home_name} tem vantagem no confronto direto: {home_wins} vitórias em {total} jogos.",
                confidence=min(confidence, 95)
            ))
            # retornar cedo: h2h é forte argumento
            return tips
        elif away_wins > home_wins:
            confidence = 50 + int((away_wins / total) * 30)
            tips.append(TipInfo(
                market="Vencedor (H2H)",
                suggestion=f"Vitória do {away_name}",
                justification=f"{away_name} tem vantagem no confronto direto: {away_wins} vitórias em {total} jogos.",
                confidence=min(confidence, 95)
            ))
            return tips

    # 3) Forma recente (últimos 10)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        task_home = client.get(f"{base}{endpoint}", params={"team": home_id, "last": 10}, headers=headers)
        task_away = client.get(f"{base}{endpoint}", params={"team": away_id, "last": 10}, headers=headers)
        try:
            home_res, away_res = await asyncio.gather(task_home, task_away)
            home_list = safe_get_response(home_res.json())
            away_list = safe_get_response(away_res.json())
        except Exception:
            home_list, away_list = [], []

    if home_list or away_list:
        home_wins = sum(1 for g in home_list if _get_winner_id_from_game_generic(g) == home_id)
        away_wins = sum(1 for g in away_list if _get_winner_id_from_game_generic(g) == away_id)
        # normalizar pelo número de jogos disponíveis
        home_total = max(1, len(home_list))
        away_total = max(1, len(away_list))

        # média de vitórias (percentual)
        home_win_pct = (home_wins / home_total) * 100
        away_win_pct = (away_wins / away_total) * 100

        # decidir com margem
        margin = home_win_pct - away_win_pct
        if margin >= 10:
            confidence = 45 + int(min(margin * 0.8, 45))
            tips.append(TipInfo(
                market="Vencedor (Forma)",
                suggestion=f"Vitória do {home_name}",
                justification=f"{home_name} tem melhor forma recente ({home_wins}/{home_total} vitórias).",
                confidence=min(confidence, 95)
            ))
            return tips
        elif margin <= -10:
            confidence = 45 + int(min(abs(margin) * 0.8, 45))
            tips.append(TipInfo(
                market="Vencedor (Forma)",
                suggestion=f"Vitória do {away_name}",
                justification=f"{away_name} tem melhor forma recente ({away_wins}/{away_total} vitórias).",
                confidence=min(confidence, 95)
            ))
            return tips

    # 4) Odds (se disponível) - influência na confiança
    odds_res = await _get_json_async(f"https://{host}/odds", params={"fixture": game_id}, headers=headers)
    odds_list = safe_get_response(odds_res)
    if odds_list:
        # tenta extrair menor odd por mercado de vencedor simples
        try:
            # alguns provedores retornam bookmakers -> bets -> values
            # vamos procurar por mercado 'Match Winner' ou similar
            best = None
            for book in odds_list:
                # odds_list pode ter bookmakers array ou odds diretas
                if isinstance(book, dict) and book.get("bookmakers"):
                    for b in book.get("bookmakers", []):
                        for m in b.get("bets", []):
                            if "winner" in m.get("name", "").lower() or "match winner" in m.get("name", "").lower() or m.get("name", "") == "":
                                for v in m.get("values", []):
                                    odd = float(v.get("odd", 0) or 0)
                                    selection = v.get("value")
                                    if odd > 0:
                                        if not best or odd < best[0]:
                                            best = (odd, selection)
            if best:
                odd_val, selection = best
                # melhorar a confiança quanto menor a odd (favoritismo)
                implied = int(min(max((1 / odd_val) * 100, 10), 90))
                # selection pode ser 'Home'/'Draw'/'Away' or team name
                tips.append(TipInfo(
                    market="Odds (Mercado)",
                    suggestion=f"{selection}",
                    justification=f"Odds indicam favorito com odd {odd_val}.",
                    confidence=implied
                ))
                return tips
        except Exception:
            pass

    # 5) Se nada conclusivo: fallback com vantagem de casa e observações
    # tentamos verificar se o jogo é em casa (algumas APIs têm info venue/home/away)
    # sem dados extra, sugerimos vantagem casa com confiança moderada
    tips.append(TipInfo(
        market="Tendência Geral",
        suggestion=f"Leve vantagem para {home_name} (fator casa)",
        justification="Sem evidência estatística forte. Usar vantagem de jogar em casa como critério.",
        confidence=55
    ))
    return tips

# -------------------------
# F1 analyzer (pre-race)
# -------------------------
async def analyze_f1_pre_race(race_id: int) -> List[TipInfo]:
    host = "v1.formula-1.api-sports.io"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    base = f"https://{host}"
    tips: List[TipInfo] = []

    # buscar grid e standings
    grid = safe_get_response(await _get_json_async(f"{base}/rankings/starting_grid", params={"race": race_id}, headers=headers))
    standings = safe_get_response(await _get_json_async(f"{base}/rankings/drivers", params={"season": datetime.now().year}, headers=headers))

    if grid:
        pole = next((g for g in grid if _safe_int(g.get("position")) == 1), None)
        if pole:
            driver = pole.get("driver", {}).get("name", "Pole")
            tips.append(TipInfo(
                market="Vencedor (Pole)",
                suggestion=f"Vitória de {driver}",
                justification="Piloto na pole tem vantagem estatística em muitas corridas.",
                confidence=70
            ))
    if standings:
        leader = next((d for d in standings if _safe_int(d.get("position")) == 1), None)
        if leader:
            driver = leader.get("driver", {}).get("name", "Líder")
            tips.append(TipInfo(
                market="Top3 (Campeonato)",
                suggestion=f"{driver} deve ir ao pódio (Top 3)",
                justification="Líder do campeonato com consistência de resultados.",
                confidence=65
            ))

    if not tips:
        tips.append(TipInfo(
            market="Análise",
            suggestion="Aguardar",
            justification="Dados insuficientes para previsão robusta.",
            confidence=0
        ))
    return tips

# -------------------------
# MMA placeholder
# -------------------------
async def analyze_mma_pre_fight(fight_id: int) -> List[TipInfo]:
    # placeholder — pode ser enriquecido com estilo de luta, alcance, idade, cartel
    return [TipInfo(
        market="MMA - Avaliação",
        suggestion="Não disponível",
        justification="Análise detalhada de MMA não implementada ainda.",
        confidence=0
    )]

# -------------------------
# Endpoints públicos do Tipster
# -------------------------
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int = Query(...), sport: str = Query(...)):
    """
    Retorna lista de dicas (TipInfo) para um jogo prévia a partir de game_id e sport.
    """
    sport = sport.lower()
    if sport not in SPORTS_MAP and sport not in ("formula-1", "mma"):
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    # rotas específicas
    if sport in ("football", "basketball", "nba", "baseball", "handball", "hockey", "american-football", "rugby", "volleyball", "afl", "nfl"):
        return await analyze_team_sport_pre_game(game_id, sport)
    if sport == "formula-1":
        return await analyze_f1_pre_race(game_id)
    if sport == "mma":
        return await analyze_mma_pre_fight(game_id)

    return [TipInfo(market="Erro", suggestion="Não implementado", justification=f"Análise para {sport} não implementada.", confidence=0)]

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int = Query(...), sport: str = Query(...)):
    """
    Análise ao vivo: por enquanto retorna placeholder que pode ser melhorado
    - futuro: usar endpoint live/stats, momentum, odds live, cartões e eventos ocorrendo
    """
    # Para não deixar vazio, retornar sugestão conservadora baseada em dados estáticos se possível
    sport = sport.lower()
    if sport in ("football", "basketball", "nba", "baseball", "handball", "hockey", "american-football", "rugby", "volleyball", "afl", "nfl"):
        # tentar usar pre-game analyzer como fallback (não ideal, mas evita vazio)
        return await analyze_team_sport_pre_game(game_id, sport)
    if sport == "formula-1":
        return await analyze_f1_pre_race(game_id)
    return [TipInfo(market="Ao vivo", suggestion="Não disponível", justification="Análise ao vivo ainda não implementada.", confidence=0)]

# -------------------------
# Health
# -------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}
