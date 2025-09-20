# Filename: sports_analyzer_live.py
# Versão 9.0 - Usando o endpoint /upcoming para máxima disponibilidade

import os
import requests
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

app = FastAPI(title="Tipster Ao Vivo - The Odds API (Upcoming)")

# -------------------------------
# CORS
# -------------------------------
origins = [
    "https://jean-rgsocd.github.io",
    "http://localhost:5500",
    "https://analisador-apostas.onrender.com"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Configuração da API
# -------------------------------
API_KEY = "d6adc9f70174645bada5a0fb8ad3ac27"
BASE_URL = "https://api.the-odds-api.com/v4/sports"

# -------------------------------
# Função de Requisição (Adaptada para o endpoint /upcoming)
# -------------------------------
def make_request() -> list:
    """Busca todos os jogos futuros de todos os esportes."""
    url = f"{BASE_URL}/upcoming/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",  # A região 'us' tende a ter mais cobertura
        "markets": "h2h", # h2h = Head-to-Head (Vencedor)
    }
    try:
        # Aumentado o timeout pois a resposta pode ser grande
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()  # Retorna a lista de jogos diretamente
    except requests.RequestException as e:
        print(f"[make_request] erro: {e}")
        return []  # Retorna lista vazia em caso de erro

# -------------------------------
# Função de Normalização
# -------------------------------
def normalize_odds_response(g: dict) -> Dict[str, Any]:
    """Normaliza a resposta da The Odds API para o nosso front-end."""
    try:
        game_time = datetime.fromisoformat(g.get("commence_time").replace("Z", "+00:00"))
        time_str = game_time.strftime('%Y-%m-%d %H:%M')
    except:
        time_str = g.get("commence_time")

    return {
        "game_id": g.get("id"),
        "home": g.get("home_team"),
        "away": g.get("away_team"),
        "time": time_str,
        "status": "NS",
    }

# -------------------------------
# Endpoint Principal de Partidas (Reescrito)
# -------------------------------
@app.get("/partidas/{sport_name}")
def get_upcoming_games_by_sport(sport_name: str):
    """
    Busca todos os jogos futuros e filtra pelo esporte desejado.
    'sport_name' deve ser 'football', 'nfl', ou 'nba'.
    """
    sport_name = sport_name.lower()
    
    # Mapeamento de nome amigável para a 'sport_key' oficial da API
    # Chaves de exemplo: soccer_epl, americanfootball_nfl, basketball_nba
    sport_key_map = {
        "football": "soccer_epl",  # Vamos usar a Premier League como referência para "Futebol"
        "nfl": "americanfootball_nfl",
        "nba": "basketball_nba"
    }
    
    target_sport_key = sport_key_map.get(sport_name)
    if not target_sport_key:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    # Busca TODOS os jogos futuros de TODOS os esportes
    todos_os_jogos = make_request()
    
    # Filtra a lista massiva para retornar apenas os jogos do esporte desejado
    jogos_filtrados = [game for game in todos_os_jogos if game.get("sport_key") == target_sport_key]

    jogos_normalizados = [normalize_odds_response(g) for g in jogos_filtrados]
    return jogos_normalizados

# -------------------------------
# Endpoint de Análise
# -------------------------------
@app.get("/analise/{game_id}")
def get_analysis_for_game(game_id: str):
    """Busca as odds mais recentes para um jogo específico."""
    todos_os_jogos = make_request()
    
    for game in todos_os_jogos:
        if game.get("id") == game_id:
            bookmakers = game.get("bookmakers", [])
            if not bookmakers:
                return {"error": "Nenhuma odd encontrada para este jogo."}
            
            # Pega as odds do primeiro bookmaker disponível
            odds = bookmakers[0].get("markets", [{}])[0].get("outcomes", [])
            return {"odds": odds}
            
    raise HTTPException(status_code=404, detail="Jogo não encontrado")
