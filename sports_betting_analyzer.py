# Filename: sports_betting_analyzer.py
# Versão 7.0 - Tipster IA com Análise Real

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer - Tipster IA", version="7.0")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str
    away: str
    time: str
    game_id: int

class TipInfo(BaseModel):
    market: str
    suggestion: str
    justification: str
    confidence: int

# --- MAPA DE ESPORTES ---
SPORTS_MAP = {
    "football": {"endpoint_games": "/fixtures", "host": "v3.football.api-sports.io"},
    # Adicione outros esportes aqui se desejar expandir a análise no futuro
}

# --- FUNÇÃO DE BUSCAR JOGOS (já existente e corrigida) ---
def get_daily_games_from_api(sport: str) -> Dict[str, List[GameInfo]]:
    games_by_league = {}
    api_key = os.getenv("API_KEY")
    if not api_key: return {"Erro": []}
    
    config = SPORTS_MAP.get(sport.lower())
    if not config: return {"Erro": []}

    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://{config['host']}{config['endpoint_games']}"
    querystring = {"date": today}
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()

        for item in data.get("response", []):
            league_name = item.get("league", {}).get("name", "Outros")
            home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = item.get("fixture", {}).get("id", 0)
            timestamp = item.get("fixture", {}).get("timestamp")
            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            
            if league_name not in games_by_league: games_by_league[league_name] = []
            games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id))
            
        return games_by_league
    except Exception as e:
        print(f"Erro ao buscar jogos: {e}")
        return {"Erro": []}

# --- A NOVA ENGINE DE ANÁLISE ---
def analyze_single_game(game_id: int, api_key: str) -> List[TipInfo]:
    tips = []
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    
    try:
        # Busca os prognósticos da API
        url_predictions = f"https://v3.football.api-sports.io/predictions?fixture={game_id}"
        pred_response = requests.get(url_predictions, headers=headers, timeout=20)
        pred_response.raise_for_status()
        data = pred_response.json().get("response", [])
        
        if not data:
            raise ValueError("Não há dados de prognóstico para esta partida.")
            
        prediction_data = data[0]
        
        # REGRA 1: Análise de Vencedor
        winner = prediction_data.get("predictions", {}).get("winner", {})
        advice = prediction_data.get("predictions", {}).get("advice", "N/A")
        percent = prediction_data.get("predictions", {}).get("percent", {})
        
        if winner and winner.get("name"):
            confidence = max(int(percent.get('home', '0%').strip('%')), int(percent.get('away', '0%').strip('%')))
            if confidence > 65: # Só dar a dica se a confiança for alta
                tips.append(TipInfo(
                    market="Vencedor da Partida",
                    suggestion=f"Vitória do {winner['name']}",
                    justification=f"A análise da API sugere: '{advice}'.",
                    confidence=confidence
                ))

        # REGRA 2: Análise de Gols (Over/Under)
        goals_prediction = prediction_data.get("predictions", {}).get("under_over")
        if goals_prediction and float(goals_prediction.replace(" ", "")) > 2.5:
            tips.append(TipInfo(
                market="Total de Gols",
                suggestion=f"Acima de 2.5 Gols",
                justification=f"A previsão estatística indica uma partida com {goals_prediction} gols.",
                confidence=75
            ))
            
        # REGRA 3: Ambas Marcam
        comparison = prediction_data.get("comparison", {})
        if comparison.get("att", {}).get("home", "0%")[:-1] > '70' and comparison.get("att", {}).get("away", "0%")[:-1] > '70':
            tips.append(TipInfo(
                market="Ambas as Equipes Marcam",
                suggestion="Sim",
                justification="Ambos os times têm um forte poder ofensivo e alta probabilidade de marcar.",
                confidence=int(comparison.get("btts", "0%")[:-1])
            ))
            
        if not tips:
            tips.append(TipInfo(market="Análise Conclusiva", suggestion="Aguardar ao vivo", justification="Os dados pré-jogo não indicam uma vantagem clara para nenhum mercado.", confidence=0))

    except Exception as e:
        print(f"Erro ao analisar jogo {game_id}: {e}")
        tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados detalhados para esta partida.", confidence=0))

    return tips

# --- Endpoints da API ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint(sport: str = "football"):
    return get_daily_games_from_api(sport)

@app.get("/analisar-jogo", response_model=List[TipInfo])
def analyze_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    return analyze_single_game(game_id, api_key)
