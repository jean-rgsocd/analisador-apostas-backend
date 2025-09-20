# Filename: sports_analyzer_live.py
# Versão 8.0 - Integração com The Odds API

import os
import requests
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

app = FastAPI(title="Tipster Ao Vivo - The Odds API")

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
# SUA NOVA CHAVE DA THE ODDS API
API_KEY = "d6adc9f70174645bada5a0fb8ad3ac27"
BASE_URL = "https://api.the-odds-api.com/v4/sports"

# Mapeamento de esportes para as chaves da The Odds API
# Adicione mais conforme necessário. Chaves disponíveis na documentação deles.
SPORTS_MAP = {
    "football": "soccer_brazil_campeonato_brasileiro_serie_a",
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba"
}

# -------------------------------
# Função de Requisição (Adaptada para The Odds API)
# -------------------------------
def make_request(sport_key: str) -> dict:
    url = f"{BASE_URL}/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us", # Regiões: us, uk, eu, au. 'us' tem mais bookmakers.
        "markets": "h2h", # h2h = Head-to-Head (Vencedor)
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[make_request] erro: {e}")
        return {} # Retorna um dict vazio em caso de erro

# -------------------------------
# Função de Normalização (Reescrita para The Odds API)
# -------------------------------
def normalize_odds_response(g: dict) -> Dict[str, Any]:
    """Normaliza a resposta da The Odds API para o nosso front-end."""
    # Convertendo a data do formato ISO 8601 para um mais legível
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
        "status": "NS",  # NS = Not Started, já que só buscamos jogos futuros
    }

# -------------------------------
# Endpoint Principal de Partidas
# -------------------------------
@app.get("/partidas/{sport_name}")
def get_upcoming_games(sport_name: str):
    """
    Endpoint único para buscar jogos futuros.
    'sport_name' deve ser 'football', 'nfl', ou 'nba'.
    """
    sport_name = sport_name.lower()
    if sport_name not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    sport_key = SPORTS_MAP[sport_name]
    dados = make_request(sport_key) # A resposta já é uma lista de jogos

    # A resposta da The Odds API já é a lista de jogos, não está aninhada em "response"
    jogos = [normalize_odds_response(g) for g in dados]
    return jogos

# -------------------------------
# ATENÇÃO: Os endpoints abaixo (países, ligas, análises) não funcionarão
# pois foram feitos para a API-Sports e precisam ser reescritos ou removidos.
# Por enquanto, eles estão desativados para evitar erros.
# -------------------------------

# Mantenha os outros endpoints como /perfil-tipster se ainda os usar,
# mas os de análise, estatísticas, etc., precisarão ser refeitos.
