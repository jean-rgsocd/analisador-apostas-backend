# Filename: sports_betting_analyzer.py
# Versão 4.0 - Usando a API-Football (método profissional)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os # Biblioteca para ler variáveis de ambiente
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer com API Profissional", version="4.0")

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
    
    # Pega a chave da API que guardamos no ambiente do Render
    api_key = os.getenv("API_KEY")
    
    if not api_key:
        print("ERRO: A variável de ambiente API_KEY não foi encontrada.")
        return {"Erro": [GameInfo(home="Chave da API não configurada no servidor.", away="", time="")]}

    try:
        # Pega a data de hoje no formato YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")
        
        # URL do endpoint "fixtures" (partidas) da API-Football
        url = "https://v3.football.api-sports.io/fixtures"
        
        # NS = Not Started (Apenas jogos que ainda não começaram)
        querystring = {"date": today, "status": "NS"} 
        
        headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': api_key
        }

        response = requests.get(url, headers=headers, params=querystring, timeout=20) # Adicionado timeout
        response.raise_for_status() # Lança um erro se a resposta não for 200 OK
        data = response.json()

        if data.get("results", 0) == 0:
            # Se não houver jogos futuros, busca os que já aconteceram hoje
            querystring["status"] = "FT-HT-2H-ET-P" # Status de jogos finalizados ou em andamento
            response = requests.get(url, headers=headers, params=querystring, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("results", 0) == 0:
                 return {"Info": [GameInfo(home="Nenhum jogo encontrado para hoje.", away="", time="")]}

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

    except requests.exceptions.Timeout:
        print("Erro de Timeout ao contatar a API-Football.")
        return {"Erro": [GameInfo(home="A API de esportes demorou muito para responder.", away="", time="")]}
    except Exception as e:
        print(f"Erro ao contatar a API-Football: {e}")
        # Analisa a resposta da API em caso de erro para dar mais detalhes
        error_details = data.get("errors") if 'data' in locals() else "Sem detalhes"
        print(f"Detalhes do erro da API: {error_details}")
        return {"Erro": [GameInfo(home="Falha ao buscar dados da API de esportes.", away=f"Detalhe: {error_details}", time="")]}

# --- Endpoint da API ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint():
    games = get_daily_games_from_api()
    return games
