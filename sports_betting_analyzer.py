# Filename: sports_betting_analyzer.py
# Versão 5.5 - URLs Corretas da API

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer Multi-Esportivo", version="5.5")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str
    away: str
    time: str

# --- Lógica da API ---
def get_daily_games_from_api(sport: str) -> Dict[str, List[GameInfo]]:
    games_by_league = {}
    api_key = os.getenv("API_KEY")
    if not api_key:
        return {"Erro": [GameInfo(home="Chave da API não configurada no servidor.", away="", time="")]}

    # **MAPA CORRIGIDO COM AS URLS E HOSTS EXATOS QUE VOCÊ RECEBEU**
    sport_map = {
        "football": {"endpoint": "/fixtures", "host": "v3.football.api-sports.io", "base_url": "https://v3.football.api-sports.io"},
        "basketball": {"endpoint": "/games", "host": "v1.basketball.api-sports.io", "base_url": "https://v1.basketball.api-sports.io"},
        "nfl": {"endpoint": "/games", "host": "v1.american-football.api-sports.io", "base_url": "https://v1.american-football.api-sports.io"},
        "baseball": {"endpoint": "/games", "host": "v1.baseball.api-sports.io", "base_url": "https://v1.baseball.api-sports.io"},
        "formula-1": {"endpoint": "/races", "host": "v1.formula-1.api-sports.io", "base_url": "https://v1.formula-1.api-sports.io"},
        "handball": {"endpoint": "/games", "host": "v1.handball.api-sports.io", "base_url": "https://v1.handball.api-sports.io"},
        "hockey": {"endpoint": "/games", "host": "v1.hockey.api-sports.io", "base_url": "https://v1.hockey.api-sports.io"},
        "mma": {"endpoint": "/fights", "host": "v1.mma.api-sports.io", "base_url": "https://v1.mma.api-sports.io"},
        "rugby": {"endpoint": "/games", "host": "v1.rugby.api-sports.io", "base_url": "https://v1.rugby.api-sports.io"},
        "volleyball": {"endpoint": "/games", "host": "v1.volleyball.api-sports.io", "base_url": "https://v1.volleyball.api-sports.io"},
    }

    if sport not in sport_map:
        return {"Erro": [GameInfo(home="Esporte inválido ou não suportado.", away="", time="")]}

    try:
        config = sport_map[sport]
        today = datetime.now().strftime("%Y-%m-%d")
        url = config["base_url"] + config["endpoint"]
        
        if sport == 'formula-1':
            querystring = {"season": datetime.now().strftime("%Y"), "type": "Race"}
        else:
            querystring = {"date": today}
        
        headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("results", 0) == 0:
            return {"Info": [GameInfo(home=f"Nenhum evento de {sport} encontrado.", away="", time="")]}

        for item in data.get("response", []):
            league_name = item.get("league", {}).get("name", item.get("competition", {}).get("name", "Outros"))
            
            home_team, away_team, timestamp = "N/A", "N/A", item.get("timestamp")
            
            if 'teams' in item:
                home_team = item.get("teams", {}).get("home", {}).get("name")
                away_team = item.get("teams", {}).get("away", {}).get("name")
                if sport == 'football': timestamp = item.get("fixture", {}).get("timestamp")
            elif sport == 'formula-1':
                home_team = item.get("circuit", {}).get("name")
                away_team = f"({item.get('competition', {}).get('location', {}).get('country', '')})"
            elif sport == 'mma':
                home_team = item.get("fighters", {}).get("fighter_1", {}).get("name")
                away_team = item.get("fighters", {}).get("fighter_2", {}).get("name")

            if not home_team: continue
            
            game_time = datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M') if sport == 'formula-1' else datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            
            if league_name not in games_by_league:
                games_by_league[league_name] = []
            
            games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time))
            
        return games_by_league
    except Exception as e:
        print(f"Erro na API para o esporte {sport}: {e}")
        return {"Erro": [GameInfo(home="Falha ao buscar dados da API.", away="", time="")]}

@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint(sport: str = "football"):
    return get_daily_games_from_api(sport.lower())
