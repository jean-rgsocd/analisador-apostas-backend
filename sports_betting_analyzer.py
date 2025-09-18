# Filename: sports_betting_analyzer.py
# Versão 2.2 - Usando extração de JSON embutido (mais robusto)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import requests
import json
import re
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sports Betting Analyzer com Dados Reais", version="2.2")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str
    away: str
    time: str

# --- Lógica de Web Scraping (Nova Versão Robusta) ---
def get_daily_games_from_flashscore_json() -> Dict[str, List[GameInfo]]:
    games_by_league = {}
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', 'X-Requested-With': 'XMLHttpRequest'}
        main_url = "https://www.flashscore.com.br/"
        
        response = requests.get(main_url, headers=headers)
        response.raise_for_status()

        html_content = response.text
        
        # Usa uma expressão regular para encontrar o bloco de dados dos jogos.
        # Procuramos por uma variável JavaScript que contém todos os dados.
        match = re.search(r'var initialData = (\{.*\});', html_content)
        
        if not match:
            # Se o padrão acima falhar, tenta um padrão secundário comum
            match = re.search(r'window\.__INITIAL_DATA__\s*=\s*(\{.*\});', html_content)
            if not match:
                 raise ValueError("Não foi possível encontrar o bloco de dados JSON inicial na página.")

        # Extrai o JSON e o converte para um dicionário Python
        json_data_string = match.group(1)
        data = json.loads(json_data_string)

        # Navega pelo dicionário para encontrar os eventos (jogos)
        # A estrutura exata do JSON pode mudar, esta é a parte que pode precisar de ajuste no futuro
        events = data.get('events', [])
        
        for event in events:
            league_name = event.get('tournament', {}).get('name', 'Outros')
            country_name = event.get('tournament', {}).get('country', {}).get('name', '')
            
            full_league_name = f"{country_name}: {league_name}" if country_name else league_name
            
            home_team = event.get('homeTeam', {}).get('name', 'Time da Casa')
            away_team = event.get('awayTeam', {}).get('name', 'Time Visitante')
            time_unix = event.get('startTime') # O tempo vem em formato Unix timestamp
            
            # Converte o tempo para um formato legível (requer datetime, mas vamos simplificar)
            from datetime import datetime
            game_time = datetime.fromtimestamp(time_unix).strftime('%H:%M') if time_unix else "N/A"

            if full_league_name not in games_by_league:
                games_by_league[full_league_name] = []

            game_info = GameInfo(
                home=home_team,
                away=away_team,
                time=game_time
            )
            games_by_league[full_league_name].append(game_info)
            
        return games_by_league
        
    except Exception as e:
        print(f"Erro ao buscar jogos do dia no Flashscore: {e}")
        return {"Erro": [GameInfo(home="Não foi possível carregar os jogos", away="A estrutura do site pode ter mudado.", time="")]}


# --- Endpoint Principal da API ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint():
    games = get_daily_games_from_flashscore_json()
    if not games:
        return {"Info": [GameInfo(home="Nenhum jogo encontrado para hoje.", away="", time="")]}
    return games
