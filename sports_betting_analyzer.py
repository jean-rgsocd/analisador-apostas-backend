# Filename: sports_betting_analyzer.py
# VERSÃO FINAL COM A NOVA API: THE ODDS API

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - The Odds API")

# --- CACHE, CORS, CONFIGURAÇÕES ---
cache: Dict[str, Any] = {}
CACHE_DURATION_MINUTES = 30 # Cache de 30 minutos
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- NOVA CONFIGURAÇÃO DA API ---
THE_ODDS_API_KEY = "d6adc9f70174645bada5a0fb8ad3ac27"
THE_ODDS_API_URL = "https://api.the-odds-api.com/v4"

# --- ENDPOINTS ---

@app.get("/sports")
def get_available_sports() -> List[Dict[str, str]]:
    cache_key = "sports_list"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]:
        return cache[cache_key]["data"]

    url = f"{THE_ODDS_API_URL}/sports"
    params = {"apiKey": THE_ODDS_API_KEY}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Filtra para incluir apenas os esportes que queremos
        allowed_sports = {
            "soccer_brazil_campeonato": "Futebol (Brasil)",
            "basketball_nba": "Basquete (NBA)",
            "americanfootball_nfl": "Futebol Americano (NFL)"
        }
        
        sports_list = [{"key": s["key"], "title": s["title"]} for s in data if s["key"] in allowed_sports]
        
        cache[cache_key] = {"data": sports_list, "expiry": datetime.now() + timedelta(days=1)}
        return sports_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar esportes: {e}")


@app.get("/upcoming-games/{sport_key}")
def get_upcoming_games(sport_key: str) -> List[Dict[str, Any]]:
    cache_key = f"games_{sport_key}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]:
        return cache[cache_key]["data"]

    url = f"{THE_ODDS_API_URL}/sports/{sport_key}/odds/"
    params = {"apiKey": THE_ODDS_API_KEY, "regions": "uk", "markets": "h2h"}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        games_list = []
        for game in data:
            first_bookmaker = game.get("bookmakers", [{}])[0]
            outcomes = first_bookmaker.get("markets", [{}])[0].get("outcomes", [])
            
            odds = {outcome["name"]: outcome["price"] for outcome in outcomes}

            game_info = {
                "id": game["id"],
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "commence_time": game["commence_time"],
                "odds": odds
            }
            games_list.append(game_info)
            
        cache[cache_key] = {"data": games_list, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
        return games_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar jogos: {e}")
