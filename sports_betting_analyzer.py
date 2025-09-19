# sports_betting_analyzer.py
# Versão final: endpoints frontend + tipster multi-esporte completo + tratamento 429

import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from collections import Counter

# -------------------------
# App + CORS
# -------------------------
app = FastAPI(title="Sports Betting Analyzer", version="1.0")

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
    raise RuntimeError("API_KEY não definida no ambiente. Configure API_KEY no Render.")

# Headers: mantenho compatibilidade com x-rapidapi-key e x-apisports-key
DEFAULT_HEADERS = {"x-rapidapi-key": API_KEY, "x-apisports-key": API_KEY}
TIMEOUT = 30
RECENT_LAST = 10  # número de jogos para avaliar forma recente

# SPORTS_MAP: host + tipo (fixtures/games/races/events)
SPORTS_MAP: Dict[str, Dict[str, str]] = {
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
# HTTP Helpers (async)
# -------------------------
async def _get_json_async(url: str, params: dict = None, headers: dict = None) -> dict:
    headers = headers or DEFAULT_HEADERS
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, params=params, headers=headers)
            # Detect limit
            if resp.status_code == 429:
                return {"error": "limit", "status": 429}
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return {}
    except httpx.HTTPStatusError as exc:
        # Return minimal info to caller
        return {"error": "http", "status": getattr(exc.response, "status_code", None), "text": str(exc)}
    except Exception as exc:
        return {"error": "request", "text": str(exc)}

def safe_get_response(json_obj: dict) -> List[Any]:
    """
    Normaliza a resposta típica das APIs api-sports:
    - Se json_obj vazia -> []
    - Se contains error 'limit' -> [{"error":"limit"}]
    - Se tem key 'response' retorna lista (normaliza dict->list)
    """
    if not json_obj:
        return []
    if json_obj.get("error") == "limit":
        return [{"error": "limit"}]
    resp = json_obj.get("response")
    if resp is None:
        return []
    if isinstance(resp, dict):
        return [resp]
    return resp

def timestamp_to_str(ts: Optional[int]) -> str:
    if not ts:
        return "N/A"
    try:
        dt = datetime.utcfromtimestamp(int(ts))
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return "N/A"

def normalize_game(item: dict) -> GameInfo:
    """Normaliza diferentes formatos de retorno em GameInfo"""
    # futebol normalmente tem key 'fixture'
    if "fixture" in item:
        fixture = item.get("fixture", {})
        teams = item.get("teams", {})
        home = teams.get("home", {}).get("name", "N/A")
        away = teams.get("away", {}).get("name", "N/A")
        game_id = fixture.get("id") or item.get("id") or 0
        timestamp = fixture.get("timestamp")
        status = fixture.get("status", {}).get("short", "N/A")
    else:
        teams = item.get("teams", {})
        home = teams.get("home", {}).get("name", "N/A")
        away = teams.get("away", {}).get("name", "N/A")
        game_id = item.get("id") or 0
        timestamp = item.get("timestamp") or (item.get("time", {}) or {}).get("timestamp")
        status = (item.get("status") or {}).get("short") if item.get("status") else (item.get("time") or {}).get("status", "N/A")
    return GameInfo(home=home, away=away, time=timestamp_to_str(timestamp), game_id=int(game_id), status=status)

def _safe_int(v) -> int:
    try:
        return int(v)
    except Exception:
        return 0

def _get_winner_id_from_game_generic(game: dict) -> Optional[int]:
    """
    Tenta extrair o id do vencedor do jogo em formatos variados.
    """
    try:
        teams = game.get("teams", {}) or {}
        # check winner flag
        if teams.get("home", {}).get("winner") is True:
            return teams.get("home", {}).get("id")
        if teams.get("away", {}).get("winner") is True:
            return teams.get("away", {}).get("id")
        # numeric scores
        scores = game.get("scores", {}) or {}
        home_score = scores.get("home")
        away_score = scores.get("away")
        # fallback nested points
        if isinstance(home_score, dict):
            home_score = home_score.get("points")
        if isinstance(away_score, dict):
            away_score = away_score.get("points")
        if home_score is None or away_score is None:
            return None
        h = _safe_int(home_score)
        a = _safe_int(away_score)
        if h > a:
            return teams.get("home", {}).get("id")
        if a > h:
            return teams.get("away", {}).get("id")
        return None
    except Exception:
        return None

# -------------------------
# Generic fetchers used by analyzers
# -------------------------
async def fetch_game_by_id(host: str, kind: str, game_id: int, headers: dict) -> Optional[dict]:
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    res = await _get_json_async(f"https://{host}{endpoint}", params={"id": game_id}, headers=headers)
    lst = safe_get_response(res)
    return lst[0] if lst else None

async def fetch_h2h(host: str, kind: str, home_id: int, away_id: int, headers: dict) -> List[dict]:
    # football has dedicated headtohead endpoint
    if kind == "fixtures":
        res = await _get_json_async(f"https://{host}/fixtures/headtohead", params={"h2h": f"{home_id}-{away_id}"}, headers=headers)
    else:
        res = await _get_json_async(f"https://{host}/games", params={"h2h": f"{home_id}-{away_id}"}, headers=headers)
    return safe_get_response(res)

async def fetch_recent_for_team(host: str, kind: str, team_id: int, last: int, headers: dict) -> List[dict]:
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    res = await _get_json_async(f"https://{host}{endpoint}", params={"team": team_id, "last": last}, headers=headers)
    return safe_get_response(res)

# -------------------------
# Endpoints para Frontend
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
    if data and data[0].get("error") == "limit":
        return {"erro": "Limite diário atingido para este esporte. Tente novamente após 00:00 UTC."}
    return [{"name": c.get("name"), "code": c.get("code")} for c in data if c.get("code")]

@app.get("/ligas")
async def get_leagues(sport: str, country_code: Optional[str] = None):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    url = f"https://{host}/leagues"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    params = {}
    if sport == "football":
        if not country_code:
            raise HTTPException(status_code=400, detail="País obrigatório para futebol")
        params = {"season": datetime.utcnow().year, "country_code": country_code}
    data = safe_get_response(await _get_json_async(url, params=params, headers=headers))
    if data and data[0].get("error") == "limit":
        return {"erro": "Limite diário atingido para este esporte. Tente novamente após 00:00 UTC."}
    return [{"id": l.get("id"), "name": l.get("name")} for l in data]

@app.get("/jogos-por-liga")
async def get_games_by_league(sport: str, league_id: int, days: int = 1):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    kind = config["type"]
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    today = datetime.utcnow()
    end_date = today + timedelta(days=days)
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    url = f"https://{host}{endpoint}"
    params = {"league": league_id, "season": today.year, "from": today.strftime("%Y-%m-%d"), "to": end_date.strftime("%Y-%m-%d")}
    data = safe_get_response(await _get_json_async(url, params=params, headers=headers))
    if data and data[0].get("error") == "limit":
        return {"erro": "Limite diário atingido para este esporte. Tente novamente após 00:00 UTC."}
    games: List[GameInfo] = []
    for item in data:
        try:
            games.append(normalize_game(item))
        except Exception:
            continue
    # sort by time (string compare OK for dd/mm HH:MM)
    games.sort(key=lambda g: g.time)
    return games

@app.get("/jogos-por-esporte")
async def get_games_by_sport(sport: str, days: int = 1):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    kind = config["type"]
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    url = f"https://{host}{endpoint}"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    today = datetime.utcnow()
    end_date = today + timedelta(days=days)
    params_list = [{"date": today.strftime("%Y-%m-%d")}, {"date": end_date.strftime("%Y-%m-%d")}]
    results: List[GameInfo] = []
    for params in params_list:
        data = safe_get_response(await _get_json_async(url, params=params, headers=headers))
        if data and data[0].get("error") == "limit":
            return {"erro": "Limite diário atingido para este esporte. Tente novamente após 00:00 UTC."}
        for item in data:
            try:
                results.append(normalize_game(item))
            except Exception:
                continue
    results.sort(key=lambda g: g.time)
    return results

@app.get("/live")
async def get_live_games(sport: str):
    """
    Jogos ao vivo para um esporte.
    """
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    # endpoint live param differs but many support 'live=all'
    endpoint = "/fixtures" if config["type"] == "fixtures" else "/games"
    url = f"https://{host}{endpoint}"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    data = safe_get_response(await _get_json_async(url, params={"live": "all"}, headers=headers))
    if data and data[0].get("error") == "limit":
        return {"erro": "Limite diário atingido para este esporte. Tente novamente após 00:00 UTC."}
    return [normalize_game(item) for item in data]

# -------------------------
# Odds / Events / Statistics endpoints
# -------------------------
@app.get("/odds")
async def get_odds(sport: str, fixture_id: int):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    url = f"https://{host}/odds"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    data = await _get_json_async(url, params={"fixture": fixture_id}, headers=headers)
    if data.get("error") == "limit":
        return {"erro": "Limite diário atingido para este esporte. Tente novamente após 00:00 UTC."}
    return data

@app.get("/events")
async def get_events(sport: str, fixture_id: int):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    url = f"https://{host}/fixtures/events" if config["type"] == "fixtures" else f"https://{host}/games/events"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    data = await _get_json_async(url, params={"fixture": fixture_id}, headers=headers)
    if data.get("error") == "limit":
        return {"erro": "Limite diário atingido para este esporte. Tente novamente após 00:00 UTC."}
    return data

@app.get("/statistics")
async def get_statistics(sport: str, fixture_id: int):
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    host = config["host"]
    # football: /fixtures/statistics?fixture=, other sports may vary but try similar
    url = f"https://{host}/fixtures/statistics" if config["type"] == "fixtures" else f"https://{host}/games/statistics"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    data = await _get_json_async(url, params={"fixture": fixture_id}, headers=headers)
    if data.get("error") == "limit":
        return {"erro": "Limite diário atingido para este esporte. Tente novamente após 00:00 UTC."}
    return data

# -------------------------
# Tipster analyzers
# -------------------------
async def analyze_team_sport(game_id: int, sport: str) -> List[TipInfo]:
    """
   TIPSTER_PROFILES_DETAILED = {
    "football": {
        "indicators": [
            "Last 5 home/away matches for each team",
            "Last 5 head-to-head encounters",
            "Average goals scored/conceded (last 5 matches)",
            "Average corners (last 5 matches)",
            "Average cards (last 5 matches)",
            "Shots on target — total and 1st half (last 5 matches)",
            "Average xG (if available)",
            "Key formations/injuries and pre-match odds"
        ],
        "pre_game": [
            "Recent form, home advantage, xG vs actual goals, historical over/under, odds movement"
        ],
        "in_play_triggers": [
            "Possession >65% over last 15', 2+ shots on target within <10', accumulated fouls >X → card bet"
        ],
        "typical_picks": [
            "Home/Away win",
            "Over 1.5/2.5 goals (1st half or full match)",
            "Over corners",
            "Over cards",
            "Both teams to score (BTTS)"
        ],
        "required_data": [
            "Match results",
            "Match events (corners, cards, shots)",
            "xG if possible"
        ]
    },
    "basketball": {
        "indicators": [
            "Last 5 matches per team (including +/- per player)",
            "Points per quarter (last 5 matches average)",
            "Shooting percentages (FG%, 3P%, FT%)",
            "Rebounds (offensive/defensive), assists, turnovers",
            "Pace (possessions per game) and offensive/defensive efficiency",
            "Key player injuries (minutes impact)"
        ],
        "pre_game": [
            "Defense vs offense matchup, bench advantage, back-to-back, travel"
        ],
        "in_play_triggers": [
            "Pace variations, starter fouls, scoring runs (>10 points)"
        ],
        "typical_picks": [
            "Moneyline win",
            "Over/Under total points",
            "Handicap (spread)",
            "Player points over",
            "Quarter totals (1st Q Over)"
        ],
        "required_data": [
            "Boxscore per game",
            "Play-by-play for live triggers"
        ]
    },
    "nba": {
        "indicators": [
            "Last 5 matches per team (including +/- per player)",
            "Points per quarter",
            "Shooting percentages",
            "Rebounds, assists, turnovers",
            "Pace and offensive/defensive efficiency",
            "Key player injuries"
        ],
        "pre_game": [
            "Defense vs offense matchup, bench advantage, back-to-back, travel"
        ],
        "in_play_triggers": [
            "Pace variation, starter fouls, scoring runs (>10 points)"
        ],
        "typical_picks": [
            "Moneyline win",
            "Over/Under total points",
            "Handicap (spread)"
        ],
        "required_data": [
            "Boxscore per game",
            "Play-by-play for live triggers"
        ]
    },
    "american_football": {
        "indicators": [
            "Last 5 matches (including performance per quarter)",
            "Yards allowed/earned per game (total and pass/run)",
            "Turnovers (last 5 games)",
            "Red zone efficiency, 3rd down conversion",
            "Key QB/skill position injuries"
        ],
        "pre_game": [
            "Offense/defense matchup, weather (outdoor), injuries, estimated possession time"
        ],
        "in_play_triggers": [
            "3rd down failures, sacks, turnover momentum"
        ],
        "typical_picks": [
            "Moneyline",
            "Spread",
            "Over/Under total points",
            "Props (QB yards, TDs)"
        ],
        "required_data": [
            "Drive charts",
            "Play-by-play",
            "Advanced stats (DVOA if available)"
        ]
    },
    "baseball": {
        "indicators": [
            "Last 5 matches (including starting pitcher stats)",
            "Starting pitcher ERA, WHIP, K/BB, FIP",
            "Batter OPS/wOBA",
            "Win probability via simulator (Elo/xStat)",
            "Injuries/closer status"
        ],
        "pre_game": [
            "Pitcher vs lineup matchup (platoon splits L/R), weather/wind"
        ],
        "in_play_triggers": [
            "Pitcher performance per inning, bullpen usage"
        ],
        "typical_picks": [
            "Moneyline",
            "Over/Under runs",
            "Run line (handicap)",
            "Props (total hits/RBI per player)"
        ],
        "required_data": [
            "Boxscore",
            "Pitching lines",
            "Splits L/R"
        ]
    },
    "formula1": {
        "indicators": [
            "Qualifying and race performance last 5 races",
            "Average laps in Top-10 per session",
            "Average lap time, tire degradation, pit strategy",
            "Weather forecast"
        ],
        "pre_game": [
            "Qualifying, setup, circuit history"
        ],
        "in_play_triggers": [
            "Safety car probability, pace after pit, tire wear"
        ],
        "typical_picks": [
            "Podium (top-3) / win",
            "Top-6/Top-10",
            "Fastest lap",
            "Winning strategy (number of pit stops)"
        ],
        "required_data": [
            "Basic telemetry",
            "Sector times",
            "Tire status"
        ]
    },
    "handball": {
        "indicators": [
            "Last 5 matches; average goals scored/conceded",
            "Shooting efficiency (%)",
            "Goalkeeper save %",
            "Turnovers and power-play advantage (2 min)"
        ],
        "pre_game": [
            "Game pace, goalkeeper rotation, fitness"
        ],
        "in_play_triggers": [
            "Goal sequences, numerical advantages"
        ],
        "typical_picks": [
            "Win",
            "Over total goals",
            "Handicap",
            "Over 1st half goals"
        ],
        "required_data": [
            "Stats by period",
            "Goalkeeper efficiency"
        ]
    },
    "hockey": {
        "indicators": [
            "Last 5 matches; average goals",
            "Shots on goal (SOG) per game",
            "Goalie save %, PDO",
            "Powerplay/penalty kill %",
            "Faceoff % (if applicable)"
        ],
        "pre_game": [
            "Projected goalie, special teams"
        ],
        "in_play_triggers": [
            "SOG per 20', goalie stamina/shot volume"
        ],
        "typical_picks": [
            "Moneyline",
            "Over/Under goals",
            "Puck line (handicap)",
            "Over powerplay chances"
        ],
        "required_data": [
            "Boxscore",
            "SOG",
            "PK/PP stats"
        ]
    },
    "mma": {
        "indicators": [
            "Last 5 fights per fighter (stoppages vs decisions)",
            "Strikes per minute, takedown accuracy/defense, control time",
            "Reach, age, layoff time",
            "Injuries and weigh-in issues"
        ],
        "pre_game": [
            "Fighter style matchup (striker vs grappler), camp history, layoff"
        ],
        "in_play_triggers": [
            "Fight pace, clinch dominance, accumulated damage"
        ],
        "typical_picks": [
            "Win by method (KO/TKO, Submission, Decision)",
            "Round total (over/under)",
            "Prop: fight goes to decision / finishes early"
        ],
        "required_data": [
            "Fight metrics (FightMetric)",
            "Stoppage history"
        ]
    },
    "rugby": {
        "indicators": [
            "Last 5 matches; average points scored/conceded",
            "Tries per game, conversions, penalties",
            "Possession %, territory %, tackles missed",
            "Yellow/red cards"
        ],
        "pre_game": [
            "Weather, discipline (cards), scrum/lineout strength"
        ],
        "in_play_triggers": [
            "Try momentum, accumulated penalties"
        ],
        "typical_picks": [
            "Moneyline",
            "Handicap",
            "Over/Under points",
            "Total tries"
        ],
        "required_data": [
            "Phase stats",
            "Penalties"
        ]
    },
    "volleyball": {
        "indicators": [
            "Last 5 matches (sets and points per set)",
            "Attack conversion %, blocks per set, aces per set",
            "Serve and reception errors (efficiency)",
            "Rotation and presence of opposites/key players"
        ],
        "pre_game": [
            "Serve advantage, block, injuries"
        ],
        "in_play_triggers": [
            "Point runs, tactical substitutions"
        ],
        "typical_picks": [
            "Win",
            "Handicap (sets)",
            "Over/Under points per set/match",
            "Total aces/blocks"
        ],
        "required_data": [
            "Set-by-set stats",
            "Efficiency metrics"
        ]
    }
}


# -------------------------
# Roteador simples: dicionário de analisadores
# -------------------------
ANALYZERS: Dict[str, Callable[[int], asyncio.Future]] = {
    "football": lambda gid: analyze_team_sport(gid, "football"),
    "basketball": lambda gid: analyze_team_sport(gid, "basketball"),
    "nba": lambda gid: analyze_team_sport(gid, "nba"),
    "baseball": lambda gid: analyze_team_sport(gid, "baseball"),
    "handball": lambda gid: analyze_team_sport(gid, "handball"),
    "hockey": lambda gid: analyze_team_sport(gid, "hockey"),
    "rugby": lambda gid: analyze_team_sport(gid, "rugby"),
    "volleyball": lambda gid: analyze_team_sport(gid, "volleyball"),
    "afl": lambda gid: analyze_team_sport(gid, "afl"),
    "american-football": lambda gid: analyze_team_sport(gid, "american-football"),
    "formula-1": analyze_formula1,
    "mma": analyze_mma,
}

@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game(game_id: int = Query(...), sport: str = Query(...)):
    sport = sport.lower()
    if sport not in ANALYZERS:
        raise HTTPException(status_code=400, detail="Esporte não suportado")
    return await ANALYZERS[sport](game_id)

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live(game_id: int = Query(...), sport: str = Query(...)):
    # por enquanto, fallback conservador: usa pré-jogo; futuro: implementar análise baseada em /statistics & /events (live)
    return await analyze_pre_game(game_id=game_id, sport=sport)

@app.get("/health")
async def health():
    return {"status": "ok"}
