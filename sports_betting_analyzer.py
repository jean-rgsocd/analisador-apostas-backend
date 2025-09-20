# Filename: sports_analyzer_live.py
# Versão 10.0 (Final e Definitiva)

import os
import requests
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

app = FastAPI(title="Tipster Definitivo - The Odds API")

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

# Mapeamento de esportes para as chaves da The Odds API
# Chaves podem ser encontradas na documentação deles.
SPORTS_MAP = {
    "football": "soccer_epl",  # Usando a Premier League para garantir dados
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba"
}

# -------------------------------
# Função de Requisição (Robusta)
# -------------------------------
def make_request(sport_key: str) -> list:
    """Busca jogos futuros para um esporte específico."""
    url = f"{BASE_URL}/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[make_request] erro para {sport_key}: {e}")
        return []

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
# Endpoint Principal de Partidas
# -------------------------------
@app.get("/partidas/{sport_name}")
def get_upcoming_games_by_sport(sport_name: str):
    """
    Busca jogos futuros para o esporte específico solicitado.
    'sport_name' deve ser 'football', 'nfl', ou 'nba'.
    """
    sport_name = sport_name.lower()
    sport_key = SPORTS_MAP.get(sport_name)
    
    if not sport_key:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    # Chama a API com a chave específica do esporte
    jogos_da_api = make_request(sport_key)
    
    # Normaliza a resposta para o front-end
    jogos_normalizados = [normalize_odds_response(g) for g in jogos_da_api]
    return jogos_normalizados

# -------------------------------
# Endpoint de Análise (Simplificado)
# -------------------------------
# A lógica de análise precisa ser repensada para a The Odds API.
# Por enquanto, este endpoint está desativado para evitar erros.
# A função de análise no front-end precisa ser comentada ou removida.
# -------------------------------
