# Filename: sports_betting_analyzer.py
# Versão FINALÍSSIMA - Autenticação 100% correta

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - API Definitiva")

# --- CONFIGURAÇÕES GERAIS ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAÇÃO DA API-SPORTS (SEGUINDO A DOCUMENTAÇÃO OFICIAL) ---
API_SPORTS_KEY = "7baa5e00c8ae61790c6840dd"

API_HOSTS = {
    "football": "v3.football.api-sports.io",
    "basketball": "v2.nba.api-sports.io",
    "american-football": "v1.american-football.api-sports.io"
}

API_URLS = {
    "football": "https://v3.football.api-sports.io",
    "basketball": "https://v2.nba.api-sports.io",
    "american-football": "https://v1.american-football.api-sports.io"
}

# --- FUNÇÃO CENTRAL DE REQUISIÇÃO ---
def fetch_api_data(sport: str, endpoint: str, params: dict) -> List[Dict[Any, Any]]:
    if sport not in API_URLS:
        return []
    
    # CORREÇÃO DEFINITIVA: Adicionando os DOIS cabeçalhos obrigatórios
    headers = {
        'x-rapidapi-key': API_SPORTS_KEY,
        'x-rapidapi-host': API_HOSTS[sport]
    }
    url = f"{API_URLS[sport]}/{endpoint}"
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        json_response = response.json()
        
        if "response" in json_response and json_response["response"]:
            return json_response["response"]
        else:
            print(f"Resposta da API para {url} não continha dados válidos: {json_response}")
            return []
            
    except requests.RequestException as e:
        print(f"ERRO CRÍTICO na chamada para {url}: {e}")
        return []

# --- ROTA PARA FUTEBOL (HOJE + 5 DIAS) ---
@app.get("/futebol", response_model=List[Dict[str, Any]])
def get_football_games():
    today = datetime.now()
    all_games = []
    
    for i in range(6): # Pega hoje e os próximos 5 dias
        date_str = (today + timedelta(days=i)).strftime('%Y-%m-%d')
        params = {"date": date_str}
        games_of_the_day = fetch_api_data('football', 'fixtures', params)
        all_games.extend([
            {
                "game_id": g["fixture"]["id"], 
                "text": f"{g['teams']['home']['name']} vs {g['teams']['away']['name']} ({datetime.strptime(g['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z').strftime('%d/%m %H:%M')})"
            }
            for g in games_of_the_day
        ])
        
    return sorted(all_games, key=lambda x: x['text'])

# --- ROTA PARA NBA (HOJE + 5 DIAS) ---
@app.get("/nba", response_model=List[Dict[str, Any]])
def get_nba_games():
    today_date = datetime.now().date()
    all_games = []
    
    for i in range(6):
        date_str = (today_date + timedelta(days=i)).strftime('%Y-%m-%d')
        params = {"date": date_str}
        games_of_the_day = fetch_api_data('basketball', 'games', params)
        all_games.extend([
            {
                "game_id": g["id"], 
                "text": f"{g['teams']['home']['name']} vs {g['teams']['visitors']['name']} ({datetime.strptime(g['date']['start'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d/%m %H:%M')})"
            }
            for g in games_of_the_day
        ])

    return sorted(all_games, key=lambda x: x['text'])

# --- ROTA PARA NFL (HOJE + 5 DIAS) ---
@app.get("/nfl", response_model=List[Dict[str, Any]])
def get_nfl_games():
    today = datetime.now().date()
    all_games = []
    season = str(today.year)

    params = {"league": "1", "season": season}
    data = fetch_api_data('american-football', 'games', params)
    
    for g in data:
        game_date_str = g.get("game", {}).get("date", {}).get("date")
        if game_date_str:
            game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
            if today <= game_date <= (today + timedelta(days=5)):
                all_games.append({
                    "game_id": g["game"]["id"], 
                    "text": f"{g['teams']['home']['name']} vs {g['teams']['away']['name']} ({datetime.strftime(game_date, '%d/%m')})"
                })

    return sorted(all_games, key=lambda x: x['text'])
