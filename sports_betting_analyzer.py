# Filename: sports_betting_analyzer.py
# Versão 3.0 - Otimizada para Rate Limit do Plano Gratuito

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - API Otimizada V3.0")

# --- CONFIGURAÇÕES GERAIS ---
cache: Dict[str, Any] = {}
CACHE_DURATION_MINUTES = 30

origins = ["https://jean-rgsocd.github.io", "http://127.0.0.1:5500", "http://localhost:5500"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO DA API-SPORTS ---
API_SPORTS_KEY = "7baa5e00c8ae61790c6840dd" # Inserindo a chave correta da imagem
HEADERS = {"x-rapidapi-key": API_SPORTS_KEY}

API_URLS = {
    "football": "https://api-football-v1.p.rapidapi.com/v3",
    "basketball": "https://api-nba-v1.p.rapidapi.com",
    "american-football": "https://api-american-football.p.rapidapi.com"
}

# --- FUNÇÕES AUXILIARES ---
def get_season() -> str:
    """Retorna a temporada atual no formato YYYY."""
    # Para futebol, a temporada geralmente atravessa o ano (ex: 2024-2025)
    now = datetime.now()
    if now.month >= 8: # Início da temporada europeia
        return str(now.year)
    else:
        return str(now.year - 1)

def is_cache_valid(key: str) -> bool:
    """Verifica se um item no cache ainda é válido."""
    return key in cache and datetime.now() < cache[key]["expiry"]

def api_request(url: str, params: dict) -> List[Dict[Any, Any]]:
    """Função centralizada para fazer requisições à API-Sports."""
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        return response.json().get("response", [])
    except requests.RequestException as e:
        print(f"Erro na chamada da API para {url}: {e}")
        return []

# --- LISTA DE PAÍSES OTIMIZADA ---
# Removida a chamada de API para países para evitar Rate Limit e economizar cota.
# A lista foi adicionada diretamente aqui.
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
        {"name": "World", "code": "WW"} # Para competições internacionais
    ]

# --- ENDPOINTS DA API ---

@app.get("/paises/football", response_model=List[Dict[str, str]])
def get_football_countries():
    """Retorna uma lista de países pré-definida para economizar chamadas de API."""
    return get_hardcoded_countries()

@app.get("/ligas/{sport}", response_model=List[Dict[str, Any]])
def get_leagues(sport: str, country_code: str = None):
    """Retorna ligas para um esporte."""
    if sport not in API_URLS:
        raise HTTPException(status_code=400, detail="Esporte não suportado.")

    if sport == "football":
        if not country_code:
            raise HTTPException(status_code=400, detail="O parâmetro 'country_code' é obrigatório para futebol.")
        cache_key = f"leagues_football_{country_code.lower()}"
        params = {"code": country_code}
        url = f"{API_URLS['football']}/leagues"
    elif sport == "basketball":
        return [{"id": "12", "name": "NBA"}]
    elif sport == "american-football":
        return [{"id": "1", "name": "NFL"}]

    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    data = api_request(url, params)
    leagues = sorted(
        [{"id": l["league"]["id"], "name": l["league"]["name"]} for l in data if l.get("league")],
        key=lambda x: x["name"]
    )

    cache[cache_key] = {"data": leagues, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
    return leagues

@app.get("/partidas/{sport}/{league_id}", response_model=List[Dict[str, Any]])
def get_games(sport: str, league_id: str):
    """Retorna as próximas partidas de uma liga específica."""
    if sport not in API_URLS:
        raise HTTPException(status_code=400, detail="Esporte não suportado.")

    season = get_season()
    cache_key = f"games_{sport}_{league_id}_{season}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    games_data = []
    if sport == "football":
        params = {"league": league_id, "season": season, "next": "30"}
        data = api_request(f"{API_URLS['football']}/fixtures", params)
        games_data = [
            {"game_id": g["fixture"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["fixture"]["date"], "status": g["fixture"]["status"]["short"]}
            for g in data
        ]
    elif sport == "basketball":
        params = {"league": league_id, "season": season}
        data = api_request(f"{API_URLS['basketball']}/games", params)
        games_data = [
            {"game_id": g["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["visitors"]["name"], "time": g["date"]["start"], "status": g["status"]["short"]}
            for g in data
        ]
    elif sport == "american-football":
        params = {"league": league_id, "season": season}
        data = api_request(f"{API_URLS['american-football']}/games", params)
        games_data = [
            {"game_id": g["game"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["game"]["date"]["date"], "status": g["game"]["status"]["short"]}
            for g in data
        ]

    cache[cache_key] = {"data": games_data, "expiry": datetime.now() + timedelta(minutes=5)}
    return games_data
