# Filename: sports_betting_analyzer.py
# Versão 4.1 - Buscando todos os jogos do dia (sem filtro de status)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer com API Profissional", version="4.1")

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
def get_daily_games_from_api() -> Dict[str, List[GameInfo]]:
    games_by_league = {}
    
    api_key = os.getenv("API_KEY")
    
    if not api_key:
        print("ERRO: A variável de ambiente API_KEY não foi encontrada.")
        return {"Erro": [GameInfo(home="Chave da API não configurada no servidor.", away="", time="")]}

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = "https://v3.football.api-sports.io/fixtures"
        
        # **A MUDANÇA ESTÁ AQUI: Removemos o filtro 'status' para pegar TODOS os jogos do dia**
        querystring = {"date": today} 
        
        headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': api_key
        }

        response = requests.get(url, headers=headers, params=querystring, timeout=20)
        response.raise_for_status()
        data = response.json()

        if data.get("results", 0) == 0:
            return {"Info": [GameInfo(home="Nenhum jogo encontrado para hoje na API.", away="", time="")]}

        for fixture in data.get("response", []):
            league_name = fixture.get("league", {}).get("name", "Outros")
            home_team = fixture.get("teams", {}).get("home", {}).get("name", "Time da Casa")
            away_team = fixture.get("teams", {}).get("away", {}).get("name", "Time Visitante")
            
            timestamp = fixture.get("fixture", {}).get("timestamp")
            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            
            if league_name not in games_by_league:
                games_by_league[league_name] = []
                
            game_info = GameInfo(home=home_team, away=away_team, time=game_time)
            games_by_league[league_name].append(game_info)
            
        return games_by_league

    except Exception as e:
        print(f"Erro ao contatar a API-Football: {e}")
        error_details = data.get("errors") if 'data' in locals() else "Sem detalhes"
        print(f"Detalhes do erro da API: {error_details}")
        return {"Erro": [GameInfo(home="Fal
