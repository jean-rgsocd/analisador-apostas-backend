# Filename: sports_betting_analyzer.py
# Versão 5.0 - PLATINUM (Correção do Header 'x-rapidapi-host')

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - API Definitiva V5.0")

# --- CONFIGURAÇÕES GERAIS ---
origins = ["https://jean-rgsocd.github.io", "http://127.0.0.1:5500", "http://localhost:5500", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO DA API-SPORTS ---
API_SPORTS_KEY = "7baa5e00c8ae61790c6840dd"

# URLs base para cada esporte
API_URLS = {
    "football": "https://api-football-v1.p.rapidapi.com/v3",
    "basketball": "https://api-nba-v1.p.rapidapi.com",
    "american-football": "https://api-american-football.p.rapidapi.com"
}

# Hosts para o cabeçalho obrigatório da RapidAPI
API_HOSTS = {
    "football": "api-football-v1.p.rapidapi.com",
    "basketball": "api-nba-v1.p.rapidapi.com",
    "american-football": "api-american-football.p.rapidapi.com"
}

# --- FUNÇÕES AUXILIARES ---
def get_season(sport: str) -> str:
    now = datetime.now()
    if sport == 'basketball': # Formato YYYY-YYYY
        return f"{now.year - 1}-{now.year}" if now.month < 10 else f"{now.year}-{now.year + 1}"
    return str(now.year) # Formato YYYY para Futebol e NFL

def api_request(sport: str, endpoint: str, params: dict) -> List[Dict[Any, Any]]:
    if sport not in API_URLS:
        return []
    
    # CORREÇÃO CRÍTICA: Adição do header 'x-rapidapi-host'
    headers = {
        'x-rapidapi-key': API_SPORTS_KEY,
        'x-rapidapi-host': API_HOSTS[sport]
    }
    url = f"{API_URLS[sport]}/{endpoint}"
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        return response.json().get("response", [])
    except requests.RequestException as e:
        print(f"ERRO na chamada para {url} com params {params}. Erro: {e}")
        # Retorna lista vazia para o frontend não quebrar
        return []

# --- ENDPOINTS DA API ---
@app.get("/paises/football", response_model=List[Dict[str, str]])
def get_countries():
    # Mantendo a lista local para não gastar cota de API com dados estáticos
    return [
        {"name": "Argentina", "code": "AR"}, {"name": "Australia", "code": "AU"},
        {"name": "Belgium", "code": "BE"}, {"name": "Brazil", "code": "BR"},
        {"name": "England", "code": "GB"}, {"name": "France", "code": "FR"},
        {"name": "Germany", "code": "DE"}, {"name": "Italy", "code": "IT"},
        {"name": "Netherlands", "code": "NL"}, {"name": "Portugal", "code": "PT"},
        {"name": "Spain", "code": "ES"}, {"name": "USA", "code": "US"},
        {"name": "World", "code": "WW"}
    ]

@app.get("/ligas/football", response_model=List[Dict[str, Any]])
def get_football_leagues(country_code: str):
    params = {"code": country_code, "season": get_season('football')}
    data = api_request('football', 'leagues', params)
    return sorted(
        [{"id": l["league"]["id"], "name": l["league"]["name"]} for l in data if l.get("league")],
        key=lambda x: x["name"]
    )

@app.get("/partidas/{sport}", response_model=List[Dict[str, Any]])
def get_games(sport: str, league_id: str = None):
    games_data = []
    season = get_season(sport)

    if sport == "football":
        if not league_id: raise HTTPException(status_code=400, detail="league_id é obrigatório para futebol.")
        params = {"league": league_id, "season": season, "next": "50"}
        data = api_request(sport, 'fixtures', params)
        games_data = [
            {"game_id": g["fixture"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["fixture"]["date"]}
            for g in data
        ]
    elif sport == "basketball":
        params = {"league": "12", "season": season} # ID 12 é NBA
        data = api_request(sport, 'games', params)
        games_data = [
            {"game_id": g["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["visitors"]["name"], "time": g["date"]["start"]}
            for g in data
        ]
    elif sport == "american-football":
        params = {"league": "1", "season": season} # ID 1 é NFL
        data = api_request(sport, 'games', params)
        games_data = [
            {"game_id": g["game"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["game"]["date"]["date"]}
            for g in data
        ]
    
    return games_data
