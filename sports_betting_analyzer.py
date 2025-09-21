# sports_betting_analyzer.py
# Tipster IA - unificado (Futebol v3, NBA v2, NFL v2)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests, traceback

app = FastAPI(title="Tipster IA - API")

# CORS (liberar para frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

API_SPORTS_KEY = "7baa5e00c8ae57d0e6240f790c6840dd"

API_CONFIG = {
    "football": {
        "url": "https://v3.football.api-sports.io",
        "host": "v3.football.api-sports.io",
        "endpoints": {"games": "fixtures"}
    },
    "nba": {
        "url": "https://v2.nba.api-sports.io",
        "host": "v2.nba.api-sports.io",
        "endpoints": {"games": "games"}
    },
    "nfl": {
        "url": "https://v2.nfl.api-sports.io",
        "host": "v2.nfl.api-sports.io",
        "endpoints": {"games": "games"}
    }
}

def fetch_api(sport: str, endpoint: str, params: dict) -> List[Dict[str, Any]]:
    cfg = API_CONFIG[sport]
    headers = {
        "x-rapidapi-key": API_SPORTS_KEY,
        "x-rapidapi-host": cfg["host"]
    }
    url = f"{cfg['url']}/{cfg['endpoints'][endpoint]}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("response", [])
    except Exception as e:
        print(f"Erro API {sport}: {e}")
        print(traceback.format_exc())
        return []

def get_dates_list(days: int = 2) -> List[str]:
    today = datetime.utcnow().date()
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days + 1)]

# -------- FUTEBOL --------
@app.get("/futebol")
def futebol_games():
    results = []

    # Ao vivo
    live = fetch_api("football", "games", {"live": "all"})
    for g in live:
        results.append({
            "game_id": g["fixture"]["id"],
            "date": g["fixture"]["date"],
            "league": g["league"]["name"],
            "teams": g["teams"],
            "status": g["fixture"]["status"],
            "type": "live"
        })

    # Hoje + próximos 2 dias
    for d in get_dates_list(2):
        data = fetch_api("football", "games", {"date": d})
        for g in data:
            results.append({
                "game_id": g["fixture"]["id"],
                "date": g["fixture"]["date"],
                "league": g["league"]["name"],
                "teams": g["teams"],
                "status": g["fixture"]["status"],
                "type": "scheduled"
            })

    return sorted(results, key=lambda x: x["date"])

# -------- NBA --------
@app.get("/nba")
def nba_games():
    results = []

    # Ao vivo
    live = fetch_api("nba", "games", {"live": "all"})
    for g in live:
        results.append({
            "game_id": g.get("id"),
            "date": g.get("date"),
            "league": g.get("league", {}).get("name", "NBA"),
            "teams": g.get("teams"),
            "status": g.get("status"),
            "type": "live"
        })

    # Hoje + próximos 2 dias
    for d in get_dates_list(2):
        data = fetch_api("nba", "games", {"date": d})
        for g in data:
            results.append({
                "game_id": g.get("id"),
                "date": g.get("date"),
                "league": g.get("league", {}).get("name", "NBA"),
                "teams": g.get("teams"),
                "status": g.get("status"),
                "type": "scheduled"
            })

    return sorted(results, key=lambda x: x["date"] or "")

# -------- NFL --------
@app.get("/nfl")
def nfl_games():
    results = []

    # Ao vivo
    live = fetch_api("nfl", "games", {"live": "all"})
    for g in live:
        results.append({
            "game_id": g.get("id"),
            "date": g.get("date"),
            "league": g.get("league", {}).get("name", "NFL"),
            "teams": g.get("teams"),
            "status": g.get("status"),
            "type": "live"
        })

    # Hoje + próximos 2 dias
    for d in get_dates_list(2):
        data = fetch_api("nfl", "games", {"date": d})
        for g in data:
            results.append({
                "game_id": g.get("id"),
                "date": g.get("date"),
                "league": g.get("league", {}).get("name", "NFL"),
                "teams": g.get("teams"),
                "status": g.get("status"),
                "type": "scheduled"
            })

    return sorted(results, key=lambda x: x["date"] or "")
