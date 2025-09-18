# Filename: sports_betting_analyzer.py
# Versão 5.2 - Todos os Esportes Habilitados

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer Multi-Esportivo", version="5.2")

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

    # Mapa completo de esportes e seus respectivos endpoints e hosts
    sport_map = {
        "futebol": {"endpoint": "/fixtures", "host": "v3.football.api-sports.io", "base_url": "https://v3.football.api-sports.io"},
        "basquete": {"endpoint": "/games", "host": "v3.basketball.api-sports.io", "base_url": "https://v3.basketball.api-sports.io"},
        "nfl": {"endpoint": "/games", "host": "v3.american-football.api-sports.io", "base_url": "https://v3.american-football.api-sports.io"},
        "baseball": {"endpoint": "/games", "host": "v3.baseball.api-sports.io", "base_url": "https://v3.baseball.api-sports.io"},
        "formula1": {"endpoint": "/races", "host": "v3.formula-1.api-sports.io", "base_url": "https://v3.formula-1.api-sports.io"},
        "handball": {"endpoint": "/games", "host": "v3.handball.api-sports.io", "base_url": "https://v3.handball.api-sports.io"},
        "hockey": {"endpoint": "/games", "host": "v3.hockey.api-sports.io", "base_url": "https://v3.hockey.api-sports.io"},
        "mma": {"endpoint": "/fights", "host": "v3.mma.api-sports.io", "base_url": "https://v3.mma.api-sports.io"},
        "rugby": {"endpoint": "/games", "host": "v3.rugby.api-sports.io", "base_url": "https://v3.rugby.api-sports.io"},
        "volleyball": {"endpoint": "/games", "host": "v3.volleyball.api-sports.io", "base_url": "https://v3.volleyball.api-sports.io"},
    }

    if sport not in sport_map:
        return {"Erro": [GameInfo(home="Esporte inválido ou não suportado.", away="", time="")]}

    try:
        config = sport_map[sport]
        today = datetime.now().strftime("%Y-%m-%d")
        url = config["base_url"] + config["endpoint"]
        
        # Parâmetros de busca podem variar por esporte
        if sport == 'formula1':
            querystring = {"season": datetime.now().strftime("%Y"), "type": "Race"}
        else:
            querystring = {"date": today}
        
        headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("results", 0) == 0:
            return {"Info": [GameInfo(home=f"Nenhum evento de {sport} encontrado para hoje.", away="", time="")]}

        for item in data.get("response", []):
            league_name = item.get("league", {}).get("name", item.get("competition", {}).get("name", "Outros"))
            
            # Adapta a extração de dados para a estrutura de cada esporte
            if sport in ['futebol', 'basquete', 'nfl', 'baseball', 'handball', 'hockey', 'rugby', 'volleyball']:
                home_team = item.get("teams", {}).get("home", {}).get("name", "Time da Casa")
                away_team = item.get("teams", {}).get("away", {}).get("name", "Time Visitante")
                timestamp = item.get("timestamp", item.get("fixture", {}).get("timestamp"))
            elif sport == 'formula1':
                home_team = item.get("circuit", {}).get("name", "GP")
                away_team = item.get("competition", {}).get("name", "")
                timestamp = item.get("timestamp")
            elif sport == 'mma':
                home_team = item.get("fighters", {}).get("fighter_1", {}).get("name", "Lutador 1")
                away_team = item.get("fighters", {}).get("fighter_2", {}).get("name", "Lutador 2")
                timestamp = item.get("timestamp")
            else:
                continue

            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            if league_name not in games_by_league:
                games_by_league[league_name] = []
            
            games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time))
            
        return games_by_league

    except Exception as e:
        print(f"Erro ao contatar a API para o esporte {sport}: {e}")
        return {"Erro": [GameInfo(home="Falha ao buscar dados da API de esportes.", away="Verifique a chave ou o plano da API.", time="")]}


# --- Endpoint da API ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint(sport: str = "futebol"):
    games = get_daily_games_from_api(sport.lower())
    return games
