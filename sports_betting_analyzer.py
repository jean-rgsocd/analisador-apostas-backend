# Filename: sports_betting_analyzer.py
# Versão 5.5 - Depuração Final da Resposta da API

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime
import json

app = FastAPI(title="Sports Betting Analyzer Multi-Esportivo", version="5.5")

origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GameInfo(BaseModel):
    home: str
    away: str
    time: str

@app.get("/jogos-do-dia")
def get_daily_games_endpoint(sport: str = "futebol"):
    """
    Busca na API-Sports e retorna uma lista de jogos do dia para o esporte especificado.
    Esta versão inclui logs detalhados da resposta da API para depuração.
    """
    print(f"--- INICIANDO BUSCA PARA O ESPORTE: {sport.upper()} ---")
    
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("ERRO FATAL: Chave da API não encontrada no ambiente.")
        raise HTTPException(status_code=500, detail="Chave da API não configurada no servidor.")

    sport_map = {
        "football": {"endpoint": "/fixtures", "host": "v3.football.api-sports.io"},
        "basketball": {"endpoint": "/games", "host": "v3.basketball.api-sports.io"},
        # Adicione outros esportes aqui se necessário para teste
    }

    if sport.lower() not in sport_map:
        print(f"ERRO: Esporte '{sport}' não é válido.")
        raise HTTPException(status_code=400, detail=f"Esporte '{sport}' inválido.")

    config = sport_map[sport.lower()]
    base_url = f"https://{config['host']}"
    today = datetime.now().strftime("%Y-%m-%d")
    url = base_url + config["endpoint"]
    querystring = {"date": today}
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}

    try:
        print(f"Fazendo requisição para a URL: {url} com os parâmetros: {querystring}")
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        
        # **A PARTE MAIS IMPORTANTE DA DEPURAÇÃO**
        # Imprime a resposta bruta da API diretamente nos logs
        raw_response_data = response.json()
        print("\n--- RESPOSTA BRUTA DA API-SPORTS ---")
        print(json.dumps(raw_response_data, indent=2))
        print("--- FIM DA RESPOSTA BRUTA ---\n")

        # O resto do código tenta processar a resposta
        games_by_league = {}
        if raw_response_data.get("results", 0) == 0:
            return {"Info": [GameInfo(home=f"Nenhum evento de {sport} encontrado.", away="", time="")]}

        for item in raw_response_data.get("response", []):
            league_name = item.get("league", {}).get("name", "Outros")
            home_team = item.get("teams", {}).get("home", {}).get("name", "Time A")
            away_team = item.get("teams", {}).get("away", {}).get("name", "Time B")
            timestamp = item.get("timestamp", item.get("fixture", {}).get("timestamp"))
            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            if league_name not in games_by_league:
                games_by_league[league_name] = []
            games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time))
            
        return games_by_league

    except Exception as e:
        print(f"ERRO CRÍTICO DURANTE A REQUISIÇÃO: {e}")
        raise HTTPException(status_code=500, detail="Falha ao processar a requisição para a API de esportes.")
