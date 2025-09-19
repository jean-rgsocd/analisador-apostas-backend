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
    Inteligência central para esportes de equipe.
    Estratégia:
      1. H2H (se disponível) -> dica forte
      2. Forma recente (últimos RECENT_LAST jogos) -> dica média
      3. Odds (se disponível) -> ajustar confiança / criar dica
      4. Fallback: vantagem casa
    Além disso, aplicamos heurísticas específicas por esporte em alguns casos.
    """
    config = SPORTS_MAP.get(sport)
    if not config:
        raise HTTPException(status_code=400, detail="Esporte não suportado")
    host = config["host"]
    kind = config["type"]
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}

    # 1) buscar jogo
    endpoint = "/fixtures" if kind == "fixtures" else "/games"
    game_res = await _get_json_async(f"https://{host}{endpoint}", params={"id": game_id}, headers=headers)
    game_list = safe_get_response(game_res)
    if not game_list:
        return [TipInfo(market="Erro", suggestion="Indisponível", justification="Jogo não encontrado ou limite da API.", confidence=0)]
    game = game_list[0]

    home = (game.get("teams") or {}).get("home", {}) or {}
    away = (game.get("teams") or {}).get("away", {}) or {}
    home_id = home.get("id")
    away_id = away.get("id")
    home_name = home.get("name", "Casa")
    away_name = away.get("name", "Fora")

    # Container de tips
    tips: List[TipInfo] = []

    # 2) H2H
    try:
        h2h_list = await fetch_h2h(host, kind, home_id, away_id, headers)
        if h2h_list:
            winners = [_get_winner_id_from_game_generic(g) for g in h2h_list]
            counts = Counter(winners)
            home_w = counts.get(home_id, 0)
            away_w = counts.get(away_id, 0)
            total = max(1, len(h2h_list))
            # strong signal
            if home_w > away_w:
                confidence = 50 + int((home_w / total) * 30)
                tips.append(TipInfo(market="Vencedor (H2H)", suggestion=f"Vitória do {home_name}",
                                     justification=f"{home_name} lidera o confronto direto {home_w}/{total}.", confidence=min(confidence, 95)))
                return tips
            if away_w > home_w:
                confidence = 50 + int((away_w / total) * 30)
                tips.append(TipInfo(market="Vencedor (H2H)", suggestion=f"Vitória do {away_name}",
                                     justification=f"{away_name} lidera o confronto direto {away_w}/{total}.", confidence=min(confidence, 95)))
                return tips
    except Exception:
        # não interrompe execução, continua com outros dados
        pass

    # 3) Forma recente
    try:
        recent_home = await fetch_recent_for_team(host, kind, home_id, RECENT_LAST, headers)
        recent_away = await fetch_recent_for_team(host, kind, away_id, RECENT_LAST, headers)
    except Exception:
        recent_home, recent_away = [], []

    # Heurísticas por esporte
    if sport in ("basketball", "nba"):
        # calcular média de pontos feitos (tentativa robusta considerando variações)
        def avg_points(glist, team_home=True):
            pts = []
            for g in glist:
                scores = g.get("scores", {}) or {}
                # Prefer 'home'/'away' numeric or nested points
                key = "home" if team_home else "away"
                sc = scores.get(key)
                if isinstance(sc, dict):
                    sc = sc.get("points")
                pts.append(_safe_int(sc))
            if not pts:
                return 0.0
            return sum(pts) / len(pts)
        home_pts = avg_points(recent_home, team_home=True)
        away_pts = avg_points(recent_away, team_home=False)
        diff = home_pts - away_pts
        if diff >= 6:
            tips.append(TipInfo(market="Vencedor (Basquete)", suggestion=f"Vitória do {home_name}",
                                 justification=f"{home_name} média de pontos {home_pts:.1f} vs {away_pts:.1f}.", confidence=70))
            return tips
        if diff <= -6:
            tips.append(TipInfo(market="Vencedor (Basquete)", suggestion=f"Vitória do {away_name}",
                                 justification=f"{away_name} média de pontos {away_pts:.1f} vs {home_pts:.1f}.", confidence=70))
            return tips

    if sport == "baseball":
        # runs average heuristic
        def avg_runs(glist, side='home'):
            runs = []
            for g in glist:
                scores = g.get("scores", {}) or {}
                sc = scores.get(side)
                if isinstance(sc, dict):
                    sc = sc.get("points") or sc.get("runs") or sc.get("total")
                runs.append(_safe_int(sc))
            return (sum(runs) / len(runs)) if runs else 0.0
        h_runs = avg_runs(recent_home, 'home')
        a_runs = avg_runs(recent_away, 'home')
        if h_runs - a_runs >= 1.5:
            tips.append(TipInfo(market="Vencedor (Baseball)", suggestion=f"Vitória do {home_name}",
                                 justification=f"Média corridas: {h_runs:.2f} vs {a_runs:.2f}.", confidence=65))
            return tips
        if a_runs - h_runs >= 1.5:
            tips.append(TipInfo(market="Vencedor (Baseball)", suggestion=f"Vitória do {away_name}",
                                 justification=f"Média corridas: {a_runs:.2f} vs {h_runs:.2f}.", confidence=65))
            return tips

    if sport == "hockey":
        # goles medials heuristic
        def avg_goals(glist):
            goals = []
            for g in glist:
                scores = g.get("scores", {}) or {}
                h = scores.get("home")
                a = scores.get("away")
                if isinstance(h, dict):
                    h = h.get("points") or h.get("goals")
                if isinstance(a, dict):
                    a = a.get("points") or a.get("goals")
                goals.append(_safe_int(h) + _safe_int(a))
            return (sum(goals) / len(goals)) if goals else 0.0
        hg = avg_goals(recent_home)
        ag = avg_goals(recent_away)
        if hg - ag >= 1.0:
            tips.append(TipInfo(market="Vencedor (Hockey)", suggestion=f"Vitória do {home_name}",
                                 justification="Média de gols recente superior.", confidence=60))
            return tips
        if ag - hg >= 1.0:
            tips.append(TipInfo(market="Vencedor (Hockey)", suggestion=f"Vitória do {away_name}",
                                 justification="Média de gols recente superior.", confidence=60))
            return tips

    # generic wins percentage (used for many sports)
    home_wins = sum(1 for g in recent_home if _get_winner_id_from_game_generic(g) == home_id)
    away_wins = sum(1 for g in recent_away if _get_winner_id_from_game_generic(g) == away_id)
    home_total = max(1, len(recent_home))
    away_total = max(1, len(recent_away))
    home_pct = (home_wins / home_total) * 100
    away_pct = (away_wins / away_total) * 100
    margin = home_pct - away_pct
    if margin >= 12:
        tips.append(TipInfo(market="Vencedor (Forma)", suggestion=f"Vitória do {home_name}",
                             justification=f"{home_name} com {home_wins}/{home_total} recentes.", confidence=65))
        return tips
    if margin <= -12:
        tips.append(TipInfo(market="Vencedor (Forma)", suggestion=f"Vitória do {away_name}",
                             justification=f"{away_name} com {away_wins}/{away_total} recentes.", confidence=65))
        return tips

    # 4) Odds influence (if available)
    try:
        odds_res = await _get_json_async(f"https://{host}/odds", params={"fixture": game_id}, headers=headers)
        if odds_res.get("error") == "limit":
            # do not fail analysis because of limit; just ignore odds
            pass
        else:
            odds_list = safe_get_response(odds_res)
            if odds_list:
                # try find smallest odd for moneyline-like markets
                best = None
                # provider shapes vary; we attempt to find bets/values
                for item in odds_list:
                    if not isinstance(item, dict):
                        continue
                    bookmakers = item.get("bookmakers") or item.get("bookmaker") or []
                    if isinstance(bookmakers, list):
                        for bk in bookmakers:
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
                    tips.append(TipInfo(market="Odds", suggestion=f"{selection}", justification=f"Odds indicam favorito (odd {odd_val}).", confidence=implied))
                    return tips
    except Exception:
        pass

    # 5) fallback: home advantage
    tips.append(TipInfo(market="Tendência", suggestion=f"Leve vantagem para {home_name}", justification="Sem sinal estatístico forte — usar fator casa.", confidence=55))
    return tips

# Formula 1 specialized analyzer
async def analyze_formula1(race_id: int) -> List[TipInfo]:
    host = "v1.formula-1.api-sports.io"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    tips: List[TipInfo] = []
    # starting grid
    grid_res = await _get_json_async(f"https://{host}/rankings/starting_grid", params={"race": race_id}, headers=headers)
    stand_res = await _get_json_async(f"https://{host}/rankings/drivers", params={"season": datetime.utcnow().year}, headers=headers)
    grid = safe_get_response(grid_res)
    standings = safe_get_response(stand_res)
    if grid:
        pole = next((g for g in grid if int(g.get("position", 0)) == 1), None)
        if pole:
            driver = (pole.get("driver") or {}).get("name", "Pole")
            tips.append(TipInfo(market="Vencedor (Pole)", suggestion=f"{driver}", justification="Piloto sai da pole position.", confidence=75))
    if standings:
        leader = next((d for d in standings if int(d.get("position", 0)) == 1), None)
        if leader:
            driver = (leader.get("driver") or {}).get("name", "Líder")
            tips.append(TipInfo(market="Top3 (Campeonato)", suggestion=f"{driver} no pódio (Top 3)", justification="Líder do campeonato consistente.", confidence=70))
    if not tips:
        tips.append(TipInfo(market="F1", suggestion="Aguardar", justification="Dados insuficientes.", confidence=0))
    return tips

# MMA analyzer: attempt to read fighters and record
async def analyze_mma(fight_id: int) -> List[TipInfo]:
    host = "v1.mma.api-sports.io"
    headers = {"x-rapidapi-host": host, **DEFAULT_HEADERS}
    res = await _get_json_async(f"https://{host}/events", params={"id": fight_id}, headers=headers)
    items = safe_get_response(res)
    if not items:
        return [TipInfo(market="MMA", suggestion="Indisponível", justification="Dados da luta não encontrados.", confidence=0)]
    fight = items[0]
    fighters = fight.get("fighters") or []
    if len(fighters) < 2:
        return [TipInfo(market="MMA", suggestion="Indisponível", justification="Fighters info insuficiente.", confidence=0)]
    f1 = fighters[0]
    f2 = fighters[1]
    def parse_fighter(f):
        wins = f.get("wins") or (f.get("record") or {}).get("wins") or 0
        losses = f.get("losses") or (f.get("record") or {}).get("losses") or 0
        ko = f.get("ko") or 0
        sub = f.get("sub") or 0
        total = _safe_int(wins) + _safe_int(losses)
        win_pct = (_safe_int(wins) / total * 100) if total else 0.0
        fin_pct = ((_safe_int(ko) + _safe_int(sub)) / total * 100) if total else 0.0
        return {"name": f.get("name", "Fighter"), "wins": _safe_int(wins), "losses": _safe_int(losses), "win_pct": win_pct, "fin_pct": fin_pct}
    r1 = parse_fighter(f1)
    r2 = parse_fighter(f2)
    # decide by win_pct + finish rate
    if r1["win_pct"] - r2["win_pct"] >= 15:
        return [TipInfo(market="Vencedor (MMA)", suggestion=f"{r1['name']}", justification=f"Maior taxa de vitórias ({r1['win_pct']:.0f}% vs {r2['win_pct']:.0f}%).", confidence=70)]
    if r2["win_pct"] - r1["win_pct"] >= 15:
        return [TipInfo(market="Vencedor (MMA)", suggestion=f"{r2['name']}", justification=f"Maior taxa de vitórias ({r2['win_pct']:.0f}% vs {r1['win_pct']:.0f}%).", confidence=70)]
    # fallback: compare finishes
    if r1["fin_pct"] - r2["fin_pct"] >= 10:
        return [TipInfo(market="Vencedor (MMA)", suggestion=f"{r1['name']}", justification=f"Taxa de finalização maior ({r1['fin_pct']:.0f}% vs {r2['fin_pct']:.0f}%).", confidence=60)]
    if r2["fin_pct"] - r1["fin_pct"] >= 10:
        return [TipInfo(market="Vencedor (MMA)", suggestion=f"{r2['name']}", justification=f"Taxa de finalização maior ({r2['fin_pct']:.0f}% vs {r1['fin_pct']:.0f}%).", confidence=60)]
    return [TipInfo(market="MMA", suggestion="Indefinido", justification="Cartel muito parecido — sem vantagem clara.", confidence=0)]

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
