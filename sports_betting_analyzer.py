# sports_betting_analyzer.py
# Versão: Tipster multi-esporte com analisadores específicos por modalidade.
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

app = FastAPI(title="Sports Betting Analyzer - MultiSport Tipster", version="2.0")

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
# Config
# -------------------------
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY não definida no ambiente. Configure a variável de ambiente API_KEY.")

# Headers compatíveis com diferentes planos
DEFAULT_HEADERS = {"x-rapidapi-key": API_KEY, "x-apisports-key": API_KEY}
TIMEOUT = 30  # segundos
RECENT_LAST = 10  # número de jogos para avaliar forma

# -------------------------
# Sports map (host + tipo)
# tipo: 'fixtures' (football) or 'games' (others) or custom
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
# Helpers
# -------------------------
def safe_get_response(json_obj: dict) -> list:
    """Return list contained in 'response' key or []"""
    if not json_obj:
        return []
    if isinstance(json_obj, dict) and "response" in json_obj:
        resp = json_obj.get("response") or []
        # normalize single object to list
        if isinstance(resp, dict):
            return [resp]
        return resp
    return []


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0


def _get_winner_id_from_game_generic(game: Dict) -> Optional[int]:
    """Extract winner id robustly from various formats."""
    teams = game.get("teams", {}) or {}
    scores = game.get("scores", {}) or {}
    # flags
    try:
        if teams.get("home", {}).get("winner") is True:
            return teams.get("home", {}).get("id")
        if teams.get("away", {}).get("winner") is True:
            return teams.get("away", {}).get("id")
    except Exception:
        pass
    # numeric scores
    home_score = scores.get("home")
    away_score = scores.get("away")
    if home_score is None or away_score is None:
        # try nested points
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


async def _get_json_async(url: str, params: dict = None, headers: dict = None) -> dict:
    headers = headers or DEFAULT_HEADERS
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError:
        return {}
    except Exception:
        return {}

# -------------------------
# Generic utilities to fetch lists
# -------------------------
async def fetch_game_by_id(host: str, kind: str, game_id: int, headers: dict) -> Optional[dict]:
    """Fetch a fixture/game by id, return first item or None"""
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    res = await _get_json_async(f"https://{host}{endpoint}", params={"id": game_id}, headers=headers)
    lst = safe_get_response(res)
    return lst[0] if lst else None

async def fetch_h2h(host: str, kind: str, home_id: int, away_id: int, headers: dict) -> list:
    """Fetch head-to-head list; football uses dedicated endpoint"""
    if kind == "fixtures":  # football
        res = await _get_json_async(f"https://{host}/fixtures/headtohead", params={"h2h": f"{home_id}-{away_id}"}, headers=headers)
    else:
        res = await _get_json_async(f"https://{host}/games", params={"h2h": f"{home_id}-{away_id}"}, headers=headers)
    return safe_get_response(res)

async def fetch_recent_for_team(host: str, kind: str, team_id: int, last: int, headers: dict) -> list:
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    res = await _get_json_async(f"https://{host}{endpoint}", params={"team": team_id, "last": last}, headers=headers)
    return safe_get_response(res)

# -------------------------
# Analyzer per sport
# -------------------------
# 1) Team sports generic with specializations
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
                tips.append(TipInfo(
                    market="Vencedor (H2H)",
                    suggestion=f"Vitória do {home_name}",
                    justification=f"{home_name} tem vantagem no confronto direto ({home_wins}/{total}).",
                    confidence=min(confidence, 95)
                ))
                return tips
            elif away_wins > home_wins:
                confidence = 50 + int((away_wins / total) * 30)
                tips.append(TipInfo(
                    market="Vencedor (H2H)",
                    suggestion=f"Vitória do {away_name}",
                    justification=f"{away_name} tem vantagem no confronto direto ({away_wins}/{total}).",
                    confidence=min(confidence, 95)
                ))
                return tips
    except Exception:
        pass

    # Recent form
    try:
        recent_home = await fetch_recent_for_team(host, kind, home_id, RECENT_LAST, headers)
        recent_away = await fetch_recent_for_team(host, kind, away_id, RECENT_LAST, headers)
    except Exception:
        recent_home, recent_away = [], []

    # If sport is basketball or nba -> compare points average
    if sport in ("basketball", "nba"):
        # compute avg points for/against in recent
        def avg_points(glist, side='home'):
            pts_for = []
            pts_against = []
            for g in glist:
                scores = g.get("scores", {}) or {}
                # try both shapes
                if isinstance(scores.get(side), dict):
                    pts_for.append(_safe_int(scores.get(side, {}).get("points", 0)))
                else:
                    pts_for.append(_safe_int(scores.get(side)))
                # opponent side
                opp = 'away' if side == 'home' else 'home'
                if isinstance(scores.get(opp), dict):
                    pts_against.append(_safe_int(scores.get(opp, {}).get("points", 0)))
                else:
                    pts_against.append(_safe_int(scores.get(opp)))
            if not pts_for:
                return 0.0, 0.0
            return sum(pts_for) / len(pts_for), (sum(pts_against) / len(pts_against)) if pts_against else 0.0

        home_for, home_against = avg_points(recent_home, 'home')
        away_for, away_against = avg_points(recent_away, 'home')  # note: API shape varies; heuristic
        # compare offensive strength
        score_diff = (home_for - away_for)
        if score_diff >= 6:
            confidence = 50 + int(min(score_diff * 2, 45))
            tips.append(TipInfo(
                market="Vencedor (Forma/Basquetebol)",
                suggestion=f"Vitória do {home_name}",
                justification=f"{home_name} tem média de pontos superior ({home_for:.1f} vs {away_for:.1f}).",
                confidence=min(confidence, 95)
            ))
            return tips
        elif score_diff <= -6:
            confidence = 50 + int(min(abs(score_diff) * 2, 45))
            tips.append(TipInfo(
                market="Vencedor (Forma/Basquetebol)",
                suggestion=f"Vitória do {away_name}",
                justification=f"{away_name} tem média de pontos superior ({away_for:.1f} vs {home_for:.1f}).",
                confidence=min(confidence, 95)
            ))
            return tips

    # Baseball: runs scored/allowed
    if sport == "baseball":
        def avg_runs(glist, side='home'):
            runs_for = []
            runs_against = []
            for g in glist:
                scores = g.get("scores", {}) or {}
                # many baseball responses use 'home'/'away' numeric
                runs_for.append(_safe_int(scores.get(side)))
                opp = 'away' if side == 'home' else 'home'
                runs_against.append(_safe_int(scores.get(opp)))
            if not runs_for:
                return 0.0, 0.0
            return sum(runs_for) / len(runs_for), sum(runs_against) / len(runs_against)
        home_runs_for, home_runs_against = avg_runs(recent_home, 'home')
        away_runs_for, away_runs_against = avg_runs(recent_away, 'home')
        diff = home_runs_for - away_runs_for
        if diff >= 1.5:
            tips.append(TipInfo(
                market="Vencedor (Baseball)",
                suggestion=f"Vitória do {home_name}",
                justification=f"{home_name} tem média de corridas maior ({home_runs_for:.2f} vs {away_runs_for:.2f}).",
                confidence=60
            ))
            return tips
        elif diff <= -1.5:
            tips.append(TipInfo(
                market="Vencedor (Baseball)",
                suggestion=f"Vitória do {away_name}",
                justification=f"{away_name} tem média de corridas maior ({away_runs_for:.2f} vs {home_runs_for:.2f}).",
                confidence=60
            ))
            return tips

    # Hockey: average goals
    if sport == "hockey":
        def avg_goals(glist):
            goals = []
            for g in glist:
                scores = g.get("scores", {}) or {}
                # attempt combine
                goals.append(_safe_int(scores.get("home")) + _safe_int(scores.get("away")))
            return (sum(goals) / len(goals)) if goals else 0.0
        home_g = avg_goals(recent_home)
        away_g = avg_goals(recent_away)
        if home_g - away_g >= 1.0:
            tips.append(TipInfo(market="Vencedor (Hóquei)", suggestion=f"Vitória do {home_name}", justification="Diferença significativa nas médias de gols recentes.", confidence=60))
            return tips
        elif away_g - home_g >= 1.0:
            tips.append(TipInfo(market="Vencedor (Hóquei)", suggestion=f"Vitória do {away_name}", justification="Diferença significativa nas médias de gols recentes.", confidence=60))
            return tips

    # Rugby / Handball / Volleyball / AFL / American football: use wins %
    if sport in ("rugby", "handball", "volleyball", "afl", "american-football"):
        def win_pct(glist, team_id):
            wins = 0
            tot = 0
            for g in glist:
                winner = _get_winner_id_from_game_generic(g)
                if winner is None:
                    continue
                tot += 1
                if winner == team_id:
                    wins += 1
            return (wins / tot * 100) if tot else 0.0
        hp = win_pct(recent_home, home_id)
        ap = win_pct(recent_away, away_id)
        margin = hp - ap
        if margin >= 12:
            tips.append(TipInfo(market="Vencedor (Forma)", suggestion=f"Vitória do {home_name}", justification=f"{home_name} superior em vitórias recentes ({hp:.0f}% vs {ap:.0f}%).", confidence=65))
            return tips
        elif margin <= -12:
            tips.append(TipInfo(market="Vencedor (Forma)", suggestion=f"Vitória do {away_name}", justification=f"{away_name} superior em vitórias recentes ({ap:.0f}% vs {hp:.0f}%).", confidence=65))
            return tips

    # Odds influence (generic)
    try:
        odds_res = await _get_json_async(f"https://{host}/odds", params={"fixture": game_id}, headers=headers)
        odds_list = safe_get_response(odds_res)
        if odds_list:
            # heuristic: find smallest odd
            best = None
            for o in odds_list:
                # different providers vary; search recursively
                if isinstance(o, dict):
                    # common structure: bookmakers -> bets -> values
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
                tips.append(TipInfo(market="Odds (Mercado)", suggestion=f"{selection}", justification=f"Odds indicam favorito com odd {odd_val}.", confidence=implied))
                return tips
    except Exception:
        pass

    # final fallback: home advantage
    tips.append(TipInfo(
        market="Tendência Geral",
        suggestion=f"Leve vantagem para {home_name}",
        justification="Sem evidência estatística forte; usar vantagem de casa como critério conservador.",
        confidence=55
    ))
    return tips

# 2) Football specialized wrapper (uses team analyzer but kept for clarity)
async def analyze_football(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "football")

# 3) Basketball wrapper
async def analyze_basketball(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "basketball")

# 4) Baseball wrapper
async def analyze_baseball(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "baseball")

# 5) Hockey wrapper
async def analyze_hockey(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "hockey")

# 6) Handball / Volleyball / Rugby wrappers (grouped)
async def analyze_handball(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "handball")

async def analyze_volleyball(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "volleyball")

async def analyze_rugby(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "rugby")

# 7) American Football / AFL
async def analyze_american_football(game_id: int) -> List[TipInfo]:
    return await analyze_team_sport(game_id, "american-football")

# 8) Formula-1 (specialized)
async def analyze_formula1(race_id: int) -> List[TipInfo]:
    host = "v1.formula-1.api-sports.io"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    base = f"https://{host}"
    tips: List[TipInfo] = []

    grid = safe_get_response(await _get_json_async(f"{base}/rankings/starting_grid", params={"race": race_id}, headers=headers))
    standings = safe_get_response(await _get_json_async(f"{base}/rankings/drivers", params={"season": datetime.now().year}, headers=headers))

    if grid:
        pole = next((g for g in grid if _safe_int(g.get("position")) == 1), None)
        if pole:
            driver = pole.get("driver", {}).get("name", "Pole")
            tips.append(TipInfo(market="Vencedor (Pole)", suggestion=f"Vitória de {driver}", justification="Piloto na pole tem vantagem estatística.", confidence=70))
    if standings:
        leader = next((d for d in standings if _safe_int(d.get("position")) == 1), None)
        if leader:
            driver = leader.get("driver", {}).get("name", "Líder")
            tips.append(TipInfo(market="Top3 (Campeonato)", suggestion=f"{driver} deve ir ao pódio (Top 3)", justification="Líder do campeonato com consistência.", confidence=65))

    if not tips:
        tips.append(TipInfo(market="Análise", suggestion="Aguardar", justification="Dados insuficientes para previsão robusta.", confidence=0))
    return tips

# 9) MMA - attempt richer analysis
async def analyze_mma(fight_id: int) -> List[TipInfo]:
    host = "v1.mma.api-sports.io"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    base = f"https://{host}"
    tips: List[TipInfo] = []

    # many MMA providers expose fight card and fighters with records
    res = await _get_json_async(f"{base}/events", params={"id": fight_id}, headers=headers)
    items = safe_get_response(res)
    if not items:
        return [TipInfo(market="MMA", suggestion="Indefinido", justification="Dados da luta não encontrados.", confidence=0)]
    fight = items[0]
    # attempt to extract fighters
    fighters = fight.get("fighters") or []
    if len(fighters) >= 2:
        f1 = fighters[0]
        f2 = fighters[1]
        # basic metrics if available: wins, losses, ko, sub, age
        def parse_record(f):
            wins = f.get("wins") or f.get("record", {}).get("wins") or 0
            losses = f.get("losses") or f.get("record", {}).get("losses") or 0
            ko = f.get("ko") or 0
            sub = f.get("sub") or 0
            total = int(wins) + int(losses) if (wins is not None and losses is not None) else 0
            win_pct = (int(wins) / total * 100) if total else 0
            return {"wins": int(wins) if wins else 0, "losses": int(losses) if losses else 0, "win_pct": win_pct, "ko": int(ko) if ko else 0, "sub": int(sub) if sub else 0}
        r1 = parse_record(f1)
        r2 = parse_record(f2)
        # prefer fighter with higher win_pct and more finishes
        if r1["win_pct"] - r2["win_pct"] >= 15:
            tips.append(TipInfo(market="Vencedor (MMA)", suggestion=f"{f1.get('name', 'Fighter 1')}", justification=f"Maior taxa de vitórias ({r1['win_pct']:.0f}% vs {r2['win_pct']:.0f}%).", confidence=65))
            return tips
        if r2["win_pct"] - r1["win_pct"] >= 15:
            tips.append(TipInfo(market="Vencedor (MMA)", suggestion=f"{f2.get('name', 'Fighter 2')}", justification=f"Maior taxa de vitórias ({r2['win_pct']:.0f}% vs {r1['win_pct']:.0f}%).", confidence=65))
            return tips
    # fallback
    return [TipInfo(market="MMA", suggestion="Indefinido", justification="Dados insuficientes para previsão. Placeholder retornado.", confidence=0)]


# -------------------------
# Public endpoints
# -------------------------
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int = Query(...), sport: str = Query(...)):
    """
    Retorna lista de dicas para um jogo pré-jogo.
    Ex: /analisar-pre-jogo?game_id=123&sport=football
    """
    sport = sport.lower()
    # Routing to specialized analyzers
    if sport == "football":
        return await analyze_football(game_id)
    if sport in ("basketball", "nba"):
        return await analyze_basketball(game_id)
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

    # default fallback: try generic team analyzer if sport present in map
    if sport in SPORTS_MAP:
        return await analyze_team_sport(game_id, sport)

    raise HTTPException(status_code=400, detail="Esporte não suportado")


@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int = Query(...), sport: str = Query(...)):
    """
    Análise ao vivo placeholder: usa pre-game analyzer as conservative fallback.
    Futuro: implementar leitura de estatísticas ao vivo, momentum e odds live.
    """
    sport = sport.lower()
    # Prefer to return live-tailored analysis when implemented; for now fallback
    return await analyze_pre_game_endpoint(game_id=game_id, sport=sport)


@app.get("/health")
async def health():
    return {"status": "ok"}

# -------------------------
# Notes:
# - Configure Render to run: uvicorn sports_betting_analyzer:app --host 0.0.0.0 --port $PORT
# - API_KEY must be set in environment (name: API_KEY)
# - Este arquivo usa heurísticas para cada esporte. Se quiser, podemos
#   ajustar thresholds (margins, RECENT_LAST) conforme liga/esporte.
# -------------------------
