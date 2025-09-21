# Filename: sports_betting_analyzer.py
# Versão 10.0 - FINAL E TESTÁVEL

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - API de Teste V10.0")

# --- CONFIGURAÇÕES GERAIS ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO DA API-SPORTS (SEGUINDO A DOCUMENTAÇÃO) ---
API_SPORTS_KEY = "7baa5e00c8ae61790c6840dd"

# --- ROTA DE TESTE NA RAIZ ---
@app.get("/")
def read_root():
    return {"status": "Tipster IA Backend está online!"}

# --- FUNÇÃO CENTRAL DE REQUISIÇÃO ---
def fetch_api_data(url: str, host: str, params: dict) -> List[Dict[Any, Any]]:
    headers = {
        'x-rapidapi-key': API_SPORTS_KEY,
        'x-rapidapi-host': host
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get("response", [])
    except requests.RequestException as e:
        print(f"ERRO CRÍTICO na chamada para {url}: {e}")
        return []

# --- ROTA PARA FUTEBOL ---
@app.get("/futebol", response_model=List[Dict[str, Any]])
def get_football_games():
    today = datetime.now()
    all_games = []
    # Busca jogos de hoje e dos próximos 5 dias
    for i in range(6):
        date_str = (today + timedelta(days=i)).strftime('%Y-%m-%d')
        params = {"date": date_str}
        url = "https://v3.football.api-sports.io/fixtures"
        host = "v3.football.api-sports.io"
        games_of_the_day = fetch_api_data(url, host, params)
        all_games.extend([
            {"game_id": g["fixture"]["id"], "text": f"{g['teams']['home']['name']} vs {g['teams']['away']['name']} ({datetime.strptime(g['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z').strftime('%d/%m %H:%M')})"}
            for g in games_of_the_day
        ])
    return sorted(all_games, key=lambda x: x['text'])

# --- ROTA PARA NBA ---
@app.get("/nba", response_model=List[Dict[str, Any]])
def get_nba_games():
    today = datetime.now()
    all_games = []
    season = f"{today.year - 1}-{today.year}" if today.month < 10 else f"{today.year}-{today.year + 1}"
    
    params = {"league": "12", "season": season} # ID 12 é o da NBA
    url = "https://v2.nba.api-sports.io/games"
    host = "v2.nba.api-sports.io"
    data = fetch_api_data(url, host, params)
    
    # Filtra jogos a partir de hoje
    upcoming_games = [g for g in data if datetime.strptime(g['date']['start'], '%Y-%m-%dT%H:%M:%S.%fZ') >= today]
    
    all_games.extend([
        {"game_id": g["id"], "text": f"{g['teams']['home']['name']} vs {g['teams']['visitors']['name']} ({datetime.strptime(g['date']['start'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d/%m %H:%M')})"}
        for g in upcoming_games
    ])
    return sorted(all_games, key=lambda x: x['text'])[:50] # Limita a 50 jogos

# --- ROTA PARA NFL ---
@app.get("/nfl", response_model=List[Dict[str, Any]])
def get_nfl_games():
    today = datetime.now()
    all_games = []
    season = str(today.year)

    params = {"league": "1", "season": season} # ID 1 é o da NFL
    url = "https://v1.american-football.api-sports.io/games"
    host = "v1.american-football.api-sports.io"
    data = fetch_api_data(url, host, params)

    # Filtra jogos a partir de hoje
    upcoming_games = [g for g in data if datetime.strptime(g['game']['date']['date'], '%Y-%m-%d') >= today.date()]

    all_games.extend([
         {"game_id": g["game"]["id"], "text": f"{g['teams']['home']['name']} vs {g['teams']['away']['name']} ({datetime.strptime(g['game']['date']['date'], '%Y-%m-%d').strftime('%d/%m')})"}
        for g in upcoming_games
    ])
    return sorted(all_games, key=lambda x: x['text'])[:50] # Limita a 50 jogos
