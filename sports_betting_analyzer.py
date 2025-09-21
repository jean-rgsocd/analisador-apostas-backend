# Filename: sports_betting_analyzer.py
# VERSÃO FINAL 2.5 - FORÇANDO MINÚSCULAS E ADICIONANDO ROTA DE TESTE

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - API-Sports V2.5 com Debug")

# --- CACHE, CORS, etc. ---
cache: Dict[str, Any] = {}
CACHE_DURATION_MINUTES = 60
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
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
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]: return cache[cache_key]["data"]
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

@app.get("/ligas/football/{country_name}")
def get_leagues_by_country(country_name: str) -> List[Dict[str, Any]]:
    cache_key = f"leagues_football_{country_name.lower()}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]: return cache[cache_key]["data"]
    url = "https://v3.football.api-sports.io/leagues"
    
    # <-- CORREÇÃO FINAL AQUI: Forçando o nome do país para minúsculas
    params = {"country": country_name.lower(), "season": get_season_for_sport("football")}
    
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

# --- ROTA DE TESTE PARA DEBUG ---
@app.get("/test-leagues/{country_name}")
def test_leagues_endpoint(country_name: str):
    url = "https://v3.football.api-sports.io/leagues"
    params = {"country": country_name.lower(), "season": get_season_for_sport("football")}
    print(f"--- TESTANDO API-SPORTS COM PARÂMETROS: {params} ---")
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"--- STATUS DA RESPOSTA: {response.status_code} ---")
        response_data = response.json()
        print(f"--- DADOS RECEBIDOS: {response_data} ---")
        return response_data
    except Exception as e:
        print(f"--- ERRO NA CHAMADA: {e} ---")
        raise HTTPException(status_code=500, detail=str(e))


# (O resto do código continua o mesmo)
@app.get("/partidas/{sport}/{league_id}")
def get_games_by_league(sport: str, league_id: str) -> List[Dict[str, Any]]:
    season = get_season_for_sport(sport)
    cache_key = f"games_{sport}_{league_id}_{season}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]: return cache[cache_key]["data"]
    try:
        games_data = []
        if sport == "football":
            url = "https://v3.football.api-sports.io/fixtures"
            params = {"league": league_id, "season": season, "next": "30"}
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

def call_any_api(url: str, params: dict):
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("response", [])
    except Exception as e:
        return []

@app.get("/analisar-pre-jogo")
def get_pre_game_analysis(game_id: int, sport: str):
    # (função de análise não muda)
    ...
