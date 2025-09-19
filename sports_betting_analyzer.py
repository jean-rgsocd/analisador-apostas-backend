# sports_betting_analyzer.py
# Versão corrigida: inclui endpoints para front (paises/ligas/jogos) + tipster multi-esporte.
# Requisitos: fastapi, httpx, pydantic

import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from collections import Counter

app = FastAPI(title="Sports Betting Analyzer - Full", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajustar em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Models
# -------------------------
class GameInfo(BaseModel):
    home: str
    away: str
    time: str
    game_id: int
    status: str

class TipInfo(BaseModel):
    market: str
    suggestion: str
    justification: str
    confidence: int

# -------------------------
# Config
# -------------------------
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY não definida no ambiente. Configure a variável de ambiente API_KEY.")

# Suportar ambos os cabeçalhos possíveis (alguns planos usam x-apisports-key)
DEFAULT_HEADERS = {"x-rapidapi-key": API_KEY, "x-apisports-key": API_KEY}
TIMEOUT = 30

# -------------------------
# SPORTS_MAP: host + tipo
# tipo 'fixtures' para futebol, 'games' para os demais (padrão)
# -------------------------
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
# Helpers HTTP async
# -------------------------
async def _get_json_async(url: str, params: dict = None, headers: dict = None) -> dict:
    headers = headers or DEFAULT_HEADERS
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        print("HTTP error:", exc)
        return {}
    except Exception as exc:
        print("Request error:", exc)
        return {}

def safe_get_response(json_obj: dict) -> list:
    if not json_obj:
        return []
    if isinstance(json_obj, dict) and "response" in json_obj:
        resp = json_obj.get("response") or []
        return resp if isinstance(resp, list) else [resp]
    return []

def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0

def _get_winner_id_from_game_generic(game: Dict) -> Optional[int]:
    teams = game.get("teams", {}) or {}
    scores = game.get("scores", {}) or {}
    try:
        if teams.get("home", {}).get("winner") is True:
            return teams.get("home", {}).get("id")
        if teams.get("away", {}).get("winner") is True:
            return teams.get("away", {}).get("id")
    except Exception:
        pass
    home_score = scores.get("home")
    away_score = scores.get("away")
    if home_score is None or away_score is None:
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
# Endpoints: Países / Ligas / Jogos
# -------------------------
@app.get("/paises")
async def get_countries(sport: str):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    url = f"https://{host}/countries"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    data = safe_get_response(await _get_json_async(url, headers=headers))
    return [{"name": c.get("name"), "code": c.get("code")} for c in data if c.get("code")]

@app.get("/ligas")
async def get_leagues(sport: str, country_code: Optional[str] = None):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    url = f"https://{host}/leagues"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    query = {}
    if sport == "football":
        if not country_code:
            raise HTTPException(status_code=400, detail="País obrigatório para futebol.")
        query = {"season": str(datetime.utcnow().year), "country_code": country_code}
    data = safe_get_response(await _get_json_async(url, params=query, headers=headers))
    return [{"id": l.get("id"), "name": l.get("name")} for l in data]

@app.get("/jogos-por-liga")
async def get_games_by_league(sport: str, league_id: int, days: int = 1):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    kind = config.get("type", "games")
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    today = datetime.utcnow()
    end_date = today + timedelta(days=days)
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    url = f"https://{host}{endpoint}"
    params = {"league": league_id, "season": today.year, "from": today.strftime("%Y-%m-%d"), "to": end_date.strftime("%Y-%m-%d")}
    print(f"Buscando jogos por liga: sport={sport} league={league_id} url={url} params={params}")
    data = safe_get_response(await _get_json_async(url, params=params, headers=headers))
    games_list = []
    for item in data:
        # normalização robusta das chaves
        if "fixture" in item:
            fixture = item.get("fixture", {})
            home = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = fixture.get("id") or item.get("id") or 0
            timestamp = fixture.get("timestamp")
            status = fixture.get("status", {}).get("short", "N/A")
        else:
            home = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = item.get("id") or 0
            timestamp = item.get("timestamp") or item.get("time", {}).get("timestamp")
            status = item.get("status", {}).get("short", "N/A") if item.get("status") else item.get("time", {}).get("status")
        game_dt = datetime.utcfromtimestamp(timestamp) if timestamp else None
        game_time = game_dt.strftime("%d/%m %H:%M") if game_dt else "N/A"
        games_list.append(GameInfo(home=home, away=away, time=game_time, game_id=int(game_id), status=status))
    return games_list

@app.get("/jogos-por-esporte")
async def get_games_by_sport(sport: str, days: int = 1):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    kind = config.get("type", "games")
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    url = f"https://{host}{endpoint}"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    today = datetime.utcnow()
    end_date = today + timedelta(days=days)
    params_today = {"date": today.strftime("%Y-%m-%d")}
    params_tomorrow = {"date": end_date.strftime("%Y-%m-%d")}
    print(f"Buscando jogos por esporte: sport={sport} host={host} endpoint={endpoint}")
    day1 = safe_get_response(await _get_json_async(url, params=params_today, headers=headers))
    day2 = safe_get_response(await _get_json_async(url, params=params_tomorrow, headers=headers))
    all_items = day1 + day2
    games_list = []
    for item in all_items:
        # mesma normalização do endpoint anterior
        if "fixture" in item:
            fixture = item.get("fixture", {})
            home = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = fixture.get("id") or item.get("id") or 0
            timestamp = fixture.get("timestamp")
            status = fixture.get("status", {}).get("short", "N/A")
        else:
            home = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = item.get("id") or 0
            timestamp = item.get("timestamp") or item.get("time", {}).get("timestamp")
            status = item.get("status", {}).get("short", "N/A") if item.get("status") else item.get("time", {}).get("status")
        game_dt = datetime.utcfromtimestamp(timestamp) if timestamp else None
        game_time = game_dt.strftime("%d/%m %H:%M") if game_dt else "N/A"
        games_list.append(GameInfo(home=home, away=away, time=game_time, game_id=int(game_id), status=status))
    # ordenar por horário
    games_list.sort(key=lambda g: g.time)
    return games_list

# -------------------------
# Tipster analyzers (reaproveita a versão multi-esporte)
# (Resumido aqui: analisadores reaproveitam lógica já discutida)
# -------------------------
RECENT_LAST = 10

async def fetch_game_by_id(host: str, kind: str, game_id: int, headers: dict) -> Optional[dict]:
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    res = await _get_json_async(f"https://{host}{endpoint}", params={"id": game_id}, headers=headers)
    lst = safe_get_response(res)
    return lst[0] if lst else None

async def fetch_h2h(host: str, kind: str, home_id: int, away_id: int, headers: dict) -> list:
    if kind == "fixtures":
        res = await _get_json_async(f"https://{host}/fixtures/headtohead", params={"h2h": f"{home_id}-{away_id}"}, headers=headers)
    else:
        res = await _get_json_async(f"https://{host}/games", params={"h2h": f"{home_id}-{away_id}"}, headers=headers)
    return safe_get_response(res)

async def fetch_recent_for_team(host: str, kind: str, team_id: int, last: int, headers: dict) -> list:
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    res = await _get_json_async(f"https://{host}{endpoint}", params={"team": team_id, "last": last}, headers=headers)
    return safe_get_response(res)

# generic analyzer (team sports): H2H -> recent form -> odds -> fallback casa
async def analyze_team_sport(game_id: int, sport: str) -> List[TipInfo]:
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte não suportado")
    host = config["host"]
    kind = config["type"]
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}

    game = await fetch_game_by_id(host, kind, game_id, headers)
    if not game:
        return [TipInfo(market="Dados", suggestion="Indefinido", justification="Jogo não encontrado na API.", confidence=0)]

    home = game.get("teams", {}).get("home", {}) or {}
    away = game.get("teams", {}).get("away", {}) or {}
    home_id, away_id = home.get("id"), away.get("id")
    home_name, away_name = home.get("name", "Time da Casa"), away.get("name", "Visitante")

    tips: List[TipInfo] = []

    # H2H
    try:
        h2h = await fetch_h2h(host, kind, home_id, away_id, headers)
        if h2h:
            winner_ids = [_get_winner_id_from_game_generic(g) for g in h2h]
            win_counts = Counter(winner_ids)
            home_wins = win_counts.get(home_id, 0)
            away_wins = win_counts.get(away_id, 0)
            total = max(1, len(h2h))
            if home_wins > away_wins:
                confidence = 50 + int((home_wins / total) * 30)
                tips.append(TipInfo(market="Vencedor (H2H)", suggestion=f"Vitória do {home_name}",
                                     justification=f"{home_name} tem vantagem no confronto direto ({home_wins}/{total}).",
                                     confidence=min(confidence, 95)))
                return tips
            elif away_wins > home_wins:
                confidence = 50 + int((away_wins / total) * 30)
                tips.append(TipInfo(market="Vencedor (H2H)", suggestion=f"Vitória do {away_name}",
                                     justification=f"{away_name} tem vantagem no confronto direto ({away_wins}/{total}).",
                                     confidence=min(confidence, 95)))
                return tips
    except Exception as e:
        print("Erro H2H:", e)

    # Forma recente
    try:
        recent_home = await fetch_recent_for_team(host, kind, home_id, RECENT_LAST, headers)
        recent_away = await fetch_recent_for_team(host, kind, away_id, RECENT_LAST, headers)
    except Exception:
        recent_home, recent_away = [], []

    # Exemplo de heurística genérica de vitórias (ajustável por esporte)
    home_wins_recent = sum(1 for g in recent_home if _get_winner_id_from_game_generic(g) == home_id)
    away_wins_recent = sum(1 for g in recent_away if _get_winner_id_from_game_generic(g) == away_id)
    home_total = max(1, len(recent_home))
    away_total = max(1, len(recent_away))
    home_pct = (home_wins_recent / home_total) * 100
    away_pct = (away_wins_recent / away_total) * 100
    margin = home_pct - away_pct
    if margin >= 12:
        tips.append(TipInfo(market="Vencedor (Forma)", suggestion=f"Vitória do {home_name}",
                             justification=f"{home_name} com melhor forma recente ({home_wins_recent}/{home_total}).",
                             confidence=60))
        return tips
    if margin <= -12:
        tips.append(TipInfo(market="Vencedor (Forma)", suggestion=f"Vitória do {away_name}",
                             justification=f"{away_name} com melhor forma recente ({away_wins_recent}/{away_total}).",
                             confidence=60))
        return tips

    # Odds (influencia confiança)
    try:
        odds_res = await _get_json_async(f"https://{host}/odds", params={"fixture": game_id}, headers=headers)
        odds_list = safe_get_response(odds_res)
        if odds_list:
            best = None
            for o in odds_list:
                if isinstance(o, dict):
                    bks = o.get("bookmakers") or o.get("bookmaker") or []
                    if isinstance(bks, list):
                        for bk in bks:
                            for bet in bk.get("bets", []) or []:
                                for val in bet.get("values", []) or []:
                                    try:
                                        odd = float(val.get("odd") or val.get("price") or 0)
                                    except Exception:
                                        odd = 0
                                    if odd > 0:
                                        sel = val.get("value") or val.get("label") or ""
                                        if not best or odd < best[0]:
                                            best = (odd, sel)
            if best:
                odd_val, selection = best
                implied = int(min(max((1 / odd_val) * 100, 10), 90))
                tips.append(TipInfo(market="Odds (Mercado)", suggestion=f"{selection}",
                                     justification=f"Odds indicam favorito com odd {odd_val}.",
                                     confidence=implied))
                return tips
    except Exception as e:
        print("Erro odds:", e)

    # Fallback: vantagem casa
    tips.append(TipInfo(market="Tendência Geral", suggestion=f"Leve vantagem para {home_name}",
                         justification="Sem evidência estatística forte; vantagem de jogar em casa.", confidence=55))
    return tips

# Wrappers para esportes específicos (reaproveitam função genérica)
async def analyze_football(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "football")

async def analyze_basketball(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "basketball")

async def analyze_nba(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "nba")

async def analyze_baseball(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "baseball")

async def analyze_hockey(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "hockey")

async def analyze_handball(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "handball")

async def analyze_volleyball(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "volleyball")

async def analyze_rugby(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "rugby")

async def analyze_american_football(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "american-football")

# Formula 1 (specialized)
async def analyze_formula1(race_id: int) -> List[TipInfo]:
    host = "v1.formula-1.api-sports.io"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    grid = safe_get_response(await _get_json_async(f"https://{host}/rankings/starting_grid", params={"race": race_id}, headers=headers))
    standings = safe_get_response(await _get_json_async(f"https://{host}/rankings/drivers", params={"season": datetime.now().year}, headers=headers))
    tips: List[TipInfo] = []
    if grid:
        pole = next((g for g in grid if _safe_int(g.get("position")) == 1), None)
        if pole:
            driver = pole.get("driver", {}).get("name", "Pole")
            tips.append(TipInfo(market="Vencedor (Pole)", suggestion=f"Vitória de {driver}",
                                 justification="Piloto na pole tem vantagem estatística.", confidence=70))
    if standings:
        leader = next((d for d in standings if _safe_int(d.get("position")) == 1), None)
        if leader:
            driver = leader.get("driver", {}).get("name", "Líder")
            tips.append(TipInfo(market="Top3 (Campeonato)", suggestion=f"{driver} deve ir ao pódio (Top 3)",
                                 justification="Líder do campeonato com consistência.", confidence=65))
    if not tips:
        tips.append(TipInfo(market="Análise", suggestion="Aguardar", justification="Dados insuficientes.", confidence=0))
    return tips

# MMA (tentativa de enriquecer)
async def analyze_mma(fight_id: int) -> List[TipInfo]:
    host = "v1.mma.api-sports.io"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    res = await _get_json_async(f"https://{host}/events", params={"id": fight_id}, headers=headers)
    items = safe_get_response(res)
    if not items:
        return [TipInfo(market="MMA", suggestion="Indefinido", justification="Dados da luta não encontrados.", confidence=0)]
    fight = items[0]
    fighters = fight.get("fighters") or []
    tips: List[TipInfo] = []
    if len(fighters) >= 2:
        f1 = fighters[0]; f2 = fighters[1]
        def parse_record(f):
            wins = f.get("wins") or f.get("record", {}).get("wins") or 0
            losses = f.get("losses") or f.get("record", {}).get("losses") or 0
            ko = f.get("ko") or 0
            sub = f.get("sub") or 0
            total = int(wins) + int(losses) if (wins is not None and losses is not None) else 0
            win_pct = (int(wins) / total * 100) if total else 0
            return {"wins": int(wins) if wins else 0, "losses": int(losses) if losses else 0, "win_pct": win_pct, "ko": int(ko) if ko else 0, "sub": int(sub) if sub else 0}
        r1 = parse_record(f1); r2 = parse_record(f2)
        if r1["win_pct"] - r2["win_pct"] >= 15:
            tips.append(TipInfo(market="Vencedor (MMA)", suggestion=f"{f1.get('name','F1')}", justification=f"Maior taxa de vitórias ({r1['win_pct']:.0f}% vs {r2['win_pct']:.0f}%).", confidence=65))
            return tips
        if r2["win_pct"] - r1["win_pct"] >= 15:
            tips.append(TipInfo(market="Vencedor (MMA)", suggestion=f"{f2.get('name','F2')}", justification=f"Maior taxa de vitórias ({r2['win_pct']:.0f}% vs {r1['win_pct']:.0f}%).", confidence=65))
            return tips
    return [TipInfo(market="MMA", suggestion="Indefinido", justification="Dados insuficientes.", confidence=0)]

# -------------------------
# Tipster endpoints
# -------------------------
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int = Query(...), sport: str = Query(...)):
    sport = sport.lower()
    if sport == "football":
        return await analyze_football(game_id)
    if sport in ("basketball",):
        return await analyze_basketball(game_id)
    if sport in ("nba",):
        return await analyze_nba(game_id)
    if sport == "baseball":
        return await analyze_baseball(game_id)
    if sport == "hockey":
        return await analyze_hockey(game_id)
    if sport == "handball":
        return await analyze_handball(game_id)
    if sport == "volleyball":
        return await analyze_volleyball(game_id)
    if sport in ("rugby",):
        return await analyze_rugby(game_id)
    if sport in ("american-football", "nfl", "afl"):
        return await analyze_american_football(game_id)
    if sport == "formula-1":
        return await analyze_formula1(game_id)
    if sport == "mma":
        return await analyze_mma(game_id)
    # fallback: if sport exists in map
    if sport in SPORTS_MAP:
        return await analyze_team_sport(game_id, sport)
    raise HTTPException(status_code=400, detail="Esporte não suportado")

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int = Query(...), sport: str = Query(...)):
    # por enquanto usa pre-game como fallback conservador
    return await analyze_pre_game_endpoint(game_id=game_id, sport=sport)

@app.get("/health")
async def health():
    return {"status": "ok"}
