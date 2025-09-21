# Filename: sports_betting_analyzer.py
# VERSÃO FINAL SIMPLIFICADA - SEM ANÁLISE, FOCO TOTAL EM BUSCAR DADOS

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - Data Collector V1")

# --- CACHE E CORS ---
cache: Dict[str, Any] = {}
CACHE_DURATION_MINUTES = 60
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- CONFIGURAÇÕES ---
API_SPORTS_KEY = "85741d1d66385996de506a07e3f527d1"
HEADERS = {"x-apisports-key": API_SPORTS_KEY}

def get_season_for_sport(sport: str) -> str:
    now = datetime.now()
    year = now.year
    if sport == "basketball":
        return f"{year - 1}-{year}" if now.month < 10 else f"{year}-{year + 1}"
    return str(year)

@app.get("/paises/football")
def get_football_countries() -> List[Dict[str, str]]:
    cache_key = "countries_football"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]:
        return cache[cache_key]["data"]
    
    url = "https://v3.football.api-sports.io/countries"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json().get("response", [])
        countries = [{"name": c["name"], "code": c["code"]} for c in data if c.get("code")]
        sorted_countries = sorted(countries, key=lambda x: x["name"])
        
        cache[cache_key] = {"data": sorted_countries, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
        return sorted_countries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar países: {e}")

@app.get("/ligas/football/{country_code}")
def get_leagues_by_country(country_code: str) -> List[Dict[str, Any]]:
    cache_key = f"leagues_football_{country_code.lower()}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]:
        return cache[cache_key]["data"]
    
    url = "https://v3.football.api-sports.io/leagues"
    params = {"code": country_code, "season": get_season_for_sport("football")}
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        data = response.json().get("response", [])
        leagues = [{"id": l["league"]["id"], "name": l["league"]["name"]} for l in data if l.get("league")]
        sorted_leagues = sorted(leagues, key=lambda x: x["name"])
        
        cache[cache_key] = {"data": sorted_leagues, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
        return sorted_leagues
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar ligas: {e}")

@app.get("/partidas/{sport}/{league_id}")
def get_games_by_league(sport: str, league_id: str) -> List[Dict[str, Any]]:
    season = get_season_for_sport(sport)
    cache_key = f"games_{sport}_{league_id}_{season}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]:
        return cache[cache_key]["data"]
    
    try:
        games_data = []
        if sport == "football":
            url = "https://v3.football.api-sports.io/fixtures"
            params = {"league": league_id, "season": season, "next": "50"} # Aumentado para 50
            response = requests.get(url, headers=HEADERS, params=params).json().get("response", [])
            games_data = [{"game_id": g["fixture"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["fixture"]["date"], "status": g["fixture"]["status"]["short"]} for g in response]
        elif sport == "basketball":
            url = "https://v2.nba.api-sports.io/games"
            params = {"league": "standard", "season": season}
            response = requests.get(url, headers=HEADERS, params=params).json().get("response", [])
            games_data = [{"game_id": g["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["visitors"]["name"], "time": g["date"]["start"], "status": g["status"]["short"]} for g in response]
        elif sport == "american-football":
            url = "https://v1.american-football.api-sports.io/fixtures"
            params = {"league": "1", "season": season}
            response = requests.get(url, headers=HEADERS, params=params).json().get("response", [])
            games_data = [{"game_id": g["fixture"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["fixture"]["date"], "status": g["fixture"]["status"]["short"]} for g in response]
        else:
            raise HTTPException(status_code=400, detail="Esporte não suportado")
        
        cache[cache_key] = {"data": games_data, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
        return games_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar jogos: {e}")
