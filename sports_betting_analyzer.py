# Filename: sports_betting_analyzer.py
# Versão 9.0 - NOVA LÓGICA (Jogos de Hoje + 5 Dias)

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - Nova Lógica V9.0")

# --- CONFIGURAÇÕES GERAIS ---
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- CONFIGURAÇÃO DA API-SPORTS ---
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

# --- FUNÇÃO AUXILIAR DE REQUISIÇÃO ---
def api_request(sport: str, endpoint: str, params: dict) -> List[Dict[Any, Any]]:
    if sport not in API_URLS: return []
    
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
        return []

# --- ENDPOINT PRINCIPAL ---
@app.get("/jogos-agendados/{sport}", response_model=List[Dict[str, Any]])
def get_scheduled_games(sport: str):
    """
    Busca jogos de hoje e dos próximos 5 dias para o esporte selecionado.
    """
    all_games = []
    
    # Gera a lista de datas (hoje + 5 dias)
    today = datetime.now()
    date_list = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6)]

    for date in date_list:
        print(f"Buscando jogos para o dia {date}...")
        if sport == "football":
            params = {"date": date}
            data = api_request(sport, 'fixtures', params)
            all_games.extend([
                {"game_id": g["fixture"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["fixture"]["date"]}
                for g in data
            ])
        elif sport == "basketball":
            params = {"date": date}
            data = api_request(sport, 'games', params)
            all_games.extend([
                {"game_id": g["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["visitors"]["name"], "time": g["date"]["start"]}
                for g in data
            ])
        elif sport == "american-football":
            # A API de NFL pode não suportar busca por data, então buscamos pela temporada e filtramos
            season = str(today.year)
            params = {"league": "1", "season": season}
            data = api_request(sport, 'games', params)
            # Este é um exemplo, a filtragem real dependeria da estrutura da resposta
            games_for_date = [
                g for g in data if g.get("game", {}).get("date", {}).get("date", "").startswith(date)
            ]
            all_games.extend([
                {"game_id": g["game"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["game"]["date"]["date"]}
                for g in games_for_date
            ])

    # Ordena todos os jogos por data
    return sorted(all_games, key=lambda x: x['time'])
