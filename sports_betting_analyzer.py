# sports_betting_analyzer.py
# Tipster IA - unificado e normalizado (cache simples)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests, time, traceback

app = FastAPI(title="Tipster IA - API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# RECOMENDADO: mover para variável de ambiente no Render
API_SPORTS_KEY = "7baa5e00c8ae57d0e6240f790c6840dd"

API_CONFIG = {
    "football": {"url": "https://v3.football.api-sports.io", "host": "v3.football.api-sports.io", "endpoint": "fixtures"},
    "nba":      {"url": "https://v2.nba.api-sports.io",        "host": "v2.nba.api-sports.io",        "endpoint": "games"},
    "nfl":      {"url": "https://v2.nfl.api-sports.io",        "host": "v2.nfl.api-sports.io",        "endpoint": "games"}
}

# cache simples para reduzir latência e chamadas
CACHE_TTL = 12   # segundos (ajuste conforme necessidade)
_cache: Dict[str, Dict[str, Any]] = {}

def _cache_get(key: str):
    rec = _cache.get(key)
    if not rec: return None
    if time.time() - rec["ts"] > CACHE_TTL:
        _cache.pop(key, None)
        return None
    return rec["data"]

def _cache_set(key: str, data):
    _cache[key] = {"ts": time.time(), "data": data}

def api_fetch(sport: str, params: dict) -> List[Dict[str, Any]]:
    cfg = API_CONFIG[sport]
    headers = {"x-rapidapi-key": API_SPORTS_KEY, "x-rapidapi-host": cfg["host"]}
    url = f"{cfg['url']}/{cfg['endpoint']}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=25)
        resp.raise_for_status()
        return resp.json().get("response", [])
    except Exception as e:
        print(f"[api_fetch] erro {sport} {url} {params}: {e}")
        print(traceback.format_exc())
        return []

def normalize_game(sport: str, raw: dict) -> dict:
    # Normaliza as variações entre APIs para frontend
    # football: fixture, league, teams
    # nba/nfl: might have different keys
    game = {}
    # id & date
    if sport == "football":
        fixture = raw.get("fixture", {})
        game_id = fixture.get("id")
        date = fixture.get("date")
        league = raw.get("league", {}) or {}
        teams = raw.get("teams", {})
        status = fixture.get("status", {})
    else:
        # nba / nfl
        # try common shapes
        game_id = raw.get("id") or raw.get("game", {}).get("id")
        date = raw.get("date") or raw.get("fixture", {}).get("date")
        league = raw.get("league", {}) or {}
        # teams: prefer raw['teams'] else compose
        if "teams" in raw and isinstance(raw["teams"], dict):
            teams = raw["teams"]
        else:
            # some endpoints use home/away or home/visitors
            home = raw.get("home") or raw.get("teams", {}).get("home") or raw.get("teams", {}).get("homeTeam")
            away = raw.get("away") or raw.get("teams", {}).get("away") or raw.get("teams", {}).get("visitors")
            teams = {"home": home or {}, "away": away or {}}
        status = raw.get("status") or raw.get("fixture", {}).get("status", {})

    # ensure league has id/name/country keys (frontend expects league.country in futebol)
    league_obj = {
        "id": league.get("id"),
        "name": league.get("name") or league.get("full_name") or league.get("league"),
        "country": league.get("country") or league.get("country_code") or league.get("countryName"),
        "season": league.get("season")
    }

    game.update({
        "game_id": game_id,
        "date": date,
        "league": league_obj,
        "teams": teams,
        "status": status,
        "type": "live" if (status and status.get("long") and "live" in str(status.get("long")).lower()) or (status and status.get("elapsed")) else "scheduled",
        "raw": raw
    })
    return game

def get_dates(days_forward=2):
    today = datetime.utcnow().date()
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_forward+1)]

@app.get("/futebol")
def futebol_all():
    cache_key = "futebol_all"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = []
    # live
    live = api_fetch("football", {"live": "all"})
    for r in live:
        results.append(normalize_game("football", r))
    # hoje + próximos 2 dias
    for d in get_dates(2):
        data = api_fetch("football", {"date": d})
        for r in data:
            results.append(normalize_game("football", r))

    # ordenar por date (se existir), ao vivo primeiro
    results_sorted = sorted(results, key=lambda x: (0 if x.get("type") == "live" else 1, x.get("date") or ""))
    _cache_set(cache_key, results_sorted)
    return results_sorted

@app.get("/nba")
def nba_all():
    cache_key = "nba_all"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = []
    live = api_fetch("nba", {"live": "all"})
    for r in live:
        results.append(normalize_game("nba", r))
    for d in get_dates(2):
        data = api_fetch("nba", {"date": d})
        for r in data:
            results.append(normalize_game("nba", r))

    results_sorted = sorted(results, key=lambda x: (0 if x.get("type") == "live" else 1, x.get("date") or ""))
    _cache_set(cache_key, results_sorted)
    return results_sorted

@app.get("/nfl")
def nfl_all():
    cache_key = "nfl_all"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = []
    live = api_fetch("nfl", {"live": "all"})
    for r in live:
        results.append(normalize_game("nfl", r))
    for d in get_dates(2):
        data = api_fetch("nfl", {"date": d})
        for r in data:
            results.append(normalize_game("nfl", r))

    results_sorted = sorted(results, key=lambda x: (0 if x.get("type") == "live" else 1, x.get("date") or ""))
    _cache_set(cache_key, results_sorted)
    return results_sorted
