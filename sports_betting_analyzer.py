# Filename: sports_betting_analyzer.py
# Versão 5.1 - Correção da Lógica Multi-Esportiva

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer Multi-Esportivo", version="5.1")

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

    sport_endpoints = {
        "futebol": "https://v3.football.api-sports.io/fixtures",
        "basquete": "https://v3.basketball.api-sports.io/games",
        "nfl": "https://v3.american-football.api-sports.io/games"
    }

    sport_hosts = {
        "futebol": "v3.football.api-sports.io",
        "basquete": "v3.basketball.api-sports.io",
        "nfl": "v3.american-football.api-sports.io"
    }

    if sport not in sport_endpoints:
        return {"Erro": [GameInfo(home="Esporte inválido ou não suportado.", away="", time="")]}

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = sport_endpoints[sport]
        host = sport_hosts[sport]
        
        querystring = {"date": today}
        
        headers = {
            'x-rapidapi-host': host,
            'x-rapidapi-key': api_key
        }

        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("results", 0) == 0:
            return {"Info": [GameInfo(home=f"Nenhum jogo de {sport} encontrado para hoje.", away="", time="")]}

        for fixture in data.get("response", []):
            # **A CORREÇÃO ESTÁ AQUI**
            # A lógica agora se adapta para cada esporte
            
            if sport == 'futebol':
                league_name = fixture.get("league", {}).get("name", "Outros")
                home_team = fixture.get("teams", {}).get("home", {}).get("name", "Time da Casa")
                away_team = fixture.get("teams", {}).get("away", {}).get("name", "Time Visitante")
                timestamp = fixture.get("fixture", {}).get("timestamp")
            else: # Lógica para Basquete, NFL, etc.
                league_name = fixture.get("league", {}).get("name", "Outros")
                home_team = fixture.get("teams", {}).get("home", {}).get("name", "Time da Casa")
                away_team = fixture.get("teams", {}).get("away", {}).get("name", "Time Visitante")
                timestamp = fixture.get("timestamp")

            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            
            if league_name not in games_by_league:
                games_by_league[league_name] = []
                
            game_info = GameInfo(home=home_team, away=away_team, time=game_time)
            games_by_league[league_name].append(game_info)
            
        return games_by_league

    except Exception as e:
        print(f"Erro ao contatar a API-Football para o esporte {sport}: {e}")
        return {"Erro": [GameInfo(home="Falha ao buscar dados da API de esportes.", away="Verifique a chave ou o plano da API.", time="")]}


# --- Endpoint da API (Agora aceita um parâmetro de esporte) ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint(sport: str = "futebol"):
    games = get_daily_games_from_api(sport.lower()) # Adicionado .lower() para segurança
    return games
