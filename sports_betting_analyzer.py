# Filename: sports_betting_analyzer.py
# Versão 4.0 - Correção Final de Parâmetros e Fluxo

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - API Corrigida V4.0")

# --- CONFIGURAÇÕES GERAIS ---
cache: Dict[str, Any] = {}
CACHE_DURATION_MINUTES = 60

origins = ["https://jean-rgsocd.github.io", "http://127.0.0.1:5500", "http://localhost:5500"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO DA API-SPORTS ---
API_SPORTS_KEY = "7baa5e00c8ae61790c6840dd"
HEADERS = {"x-rapidapi-key": API_SPORTS_KEY}

API_URLS = {
    "football": "https://api-football-v1.p.rapidapi.com/v3",
    "basketball": "https://api-nba-v1.p.rapidapi.com",
    "american-football": "https://api-american-football.p.rapidapi.com"
}

# --- FUNÇÕES AUXILIARES DE DATA E TEMPORADA ---
def get_football_season() -> str:
    """Retorna a temporada atual para futebol no formato YYYY."""
    return str(datetime.now().year)

def get_nba_season() -> str:
    """Retorna a temporada da NBA no formato YYYY-YYYY."""
    now = datetime.now()
    if now.month >= 10:  # A temporada da NBA geralmente começa em outubro
        return f"{now.year}-{now.year + 1}"
    else:
        return f"{now.year - 1}-{now.year}"

def is_cache_valid(key: str) -> bool:
    return key in cache and datetime.now() < cache[key]["expiry"]

def api_request(url: str, params: dict) -> List[Dict[Any, Any]]:
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=20)
        response.raise_for_status()
        return response.json().get("response", [])
    except requests.RequestException as e:
        print(f"Erro na chamada da API para {url} com params {params}. Erro: {e}")
        return []

# --- LISTA DE PAÍSES OTIMIZADA ---
def get_hardcoded_countries():
    return [
        {"name": "Argentina", "code": "AR"}, {"name": "Australia", "code": "AU"},
        {"name": "Belgium", "code": "BE"}, {"name": "Brazil", "code": "BR"},
        {"name": "Chile", "code": "CL"}, {"name": "Colombia", "code": "CO"},
        {"name": "England", "code": "GB"}, {"name": "France", "code": "FR"},
        {"name": "Germany", "code": "DE"}, {"name": "Italy", "code": "IT"},
        {"name": "Japan", "code": "JP"}, {"name": "Mexico", "code": "MX"},
        {"name": "Netherlands", "code": "NL"}, {"name": "Portugal", "code": "PT"},
        {"name": "Saudi Arabia", "code": "SA"}, {"name": "Spain", "code": "ES"},
        {"name": "Turkey", "code": "TR"}, {"name": "USA", "code": "US"},
        {"name": "World", "code": "WW"}
    ]

# --- ENDPOINTS DA API ---

@app.get("/paises/football", response_model=List[Dict[str, str]])
def get_football_countries_endpoint():
    return get_hardcoded_countries()

@app.get("/ligas/football", response_model=List[Dict[str, Any]])
def get_football_leagues_endpoint(country_code: str):
    season = get_football_season()
    cache_key = f"leagues_football_{country_code.lower()}_{season}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    # CORREÇÃO: Adicionado o parâmetro 'season' obrigatório
    params = {"code": country_code, "season": season}
    data = api_request(f"{API_URLS['football']}/leagues", params)
    
    leagues = sorted(
        [{"id": l["league"]["id"], "name": l["league"]["name"]} for l in data if l.get("league")],
        key=lambda x: x["name"]
    )
    cache[cache_key] = {"data": leagues, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
    return leagues

@app.get("/partidas/{sport}", response_model=List[Dict[str, Any]])
def get_games_endpoint(sport: str, league_id: str = None):
    if sport not in API_URLS:
        raise HTTPException(status_code=400, detail="Esporte não suportado.")

    games_data = []
    if sport == "football":
        if not league_id:
            raise HTTPException(status_code=400, detail="league_id é obrigatório para futebol.")
        season = get_football_season()
        params = {"league": league_id, "season": season, "next": "50"}
        data = api_request(f"{API_URLS['football']}/fixtures", params)
        games_data = [
            {"game_id": g["fixture"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["fixture"]["date"], "status": g["fixture"]["status"]["short"]}
            for g in data
        ]
    elif sport == "basketball":
        season = get_nba_season()
        # CORREÇÃO: Usando a season no formato correto 'YYYY-YYYY'
        params = {"league": "12", "season": season} # ID 12 é o da NBA
        data = api_request(f"{API_URLS['basketball']}/games", params)
        games_data = [
            {"game_id": g["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["visitors"]["name"], "time": g["date"]["start"], "status": g["status"]["short"]}
            for g in data
        ]
    elif sport == "american-football":
        season = get_football_season() # NFL usa temporada YYYY
        params = {"league": "1", "season": season} # ID 1 é o da NFL
        data = api_request(f"{API_URLS['american-football']}/games", params)
        games_data = [
            {"game_id": g["game"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["game"]["date"]["date"], "status": g["game"]["status"]["short"]}
            for g in data
        ]
    
    return games_data
