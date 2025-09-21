# Filename: sports_betting_analyzer.py
# Versão 6.0 - GOLD STANDARD (Autenticação Direta API-Sports)

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - API Definitiva V6.0")

# --- CONFIGURAÇÕES GERAIS ---
origins = ["https://jean-rgsocd.github.io", "http://127.0.0.1:5500", "http://localhost:5500", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO DA API-SPORTS (MÉTODO DE AUTENTICAÇÃO DIRETO) ---
# CORREÇÃO CRÍTICA: Usando o cabeçalho 'x-apisports-key' para acesso direto
API_SPORTS_KEY = "7baa5e00c8ae61790c6840dd"
HEADERS = {"x-apisports-key": API_SPORTS_KEY}

# CORREÇÃO CRÍTICA: Usando as URLs diretas da API-Sports
API_URLS = {
    "football": "https://v3.football.api-sports.io",
    "basketball": "https://v2.nba.api-sports.io",
    "american-football": "https://v1.american-football.api-sports.io"
}

# --- FUNÇÕES AUXILIARES ---
def get_season(sport: str) -> str:
    now = datetime.now()
    if sport == 'basketball':
        return f"{now.year - 1}-{now.year}" if now.month < 10 else f"{now.year}-{now.year + 1}"
    return str(now.year)

def api_request(sport: str, endpoint: str, params: dict) -> List[Dict[Any, Any]]:
    if sport not in API_URLS:
        return []
    
    url = f"{API_URLS[sport]}/{endpoint}"
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=20)
        response.raise_for_status()
        return response.json().get("response", [])
    except requests.RequestException as e:
        print(f"ERRO na chamada para {url} com params {params}. Erro: {e}")
        return []

# --- ENDPOINTS DA API ---
@app.get("/paises/football", response_model=List[Dict[str, str]])
def get_countries():
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
        params = {"league": "12", "season": season}
        data = api_request(sport, 'games', params)
        games_data = [
            {"game_id": g["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["visitors"]["name"], "time": g["date"]["start"]}
            for g in data
        ]
    elif sport == "american-football":
        params = {"league": "1", "season": season}
        data = api_request(sport, 'games', params)
        games_data = [
            {"game_id": g["game"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["game"]["date"]["date"]}
            for g in data
        ]
    
    return games_data
