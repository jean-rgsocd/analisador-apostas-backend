# Filename: sports_betting_analyzer.py
# Versão 9.0 - Tipster com Análise Pré-Jogo e Ao Vivo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer - Tipster IA", version="9.0")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str
    away: str
    time: str
    game_id: int
    status: str # Status do jogo (ex: NS, 1H, HT, FT)

class TipInfo(BaseModel):
    market: str
    suggestion: str
    justification: str
    confidence: int

# --- Lógica da API ---
SPORTS_MAP = {"football": {"endpoint_games": "/fixtures", "host": "v3.football.api-sports.io"}}

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
            status = item.get("fixture", {}).get("status", {}).get("short", "N/A")
            timestamp = item.get("fixture", {}).get("timestamp")
            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            
            if league_name not in games_by_league: games_by_league[league_name] = []
            games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
            
        return games_by_league
    except Exception as e:
        print(f"Erro ao buscar jogos: {e}")
        return {"Erro": []}

# --- ENGINE DE ANÁLISE PRÉ-JOGO ---
def analyze_pre_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    # (Esta é a nossa engine anterior, que usa prognósticos)
    tips = []
    try:
        url = f"https://v3.football.api-sports.io/predictions?fixture={game_id}"
        pred_response = requests.get(url, headers=headers, timeout=20)
        pred_response.raise_for_status()
        data = pred_response.json().get("response", [])
        if not data: raise ValueError("Sem prognósticos.")
        
        prediction = data[0]
        winner = prediction.get("predictions", {}).get("winner", {})
        advice = prediction.get("predictions", {}).get("advice", "N/A")
        percent = prediction.get("predictions", {}).get("percent", {})
        
        if winner and winner.get("name"):
            confidence = max(int(percent.get('home', '0%')[:-1]), int(percent.get('away', '0%')[:-1]))
            if confidence > 65:
                tips.append(TipInfo(market="Vencedor da Partida", suggestion=f"Vitória do {winner['name']}", justification=f"Análise da API sugere: '{advice}'.", confidence=confidence))
        
        # Adicione mais regras pré-jogo aqui se desejar
        if not tips:
            tips.append(TipInfo(market="Análise Conclusiva", suggestion="Aguardar ao vivo", justification="Os dados pré-jogo não indicam uma vantagem clara.", confidence=0))
    except Exception as e:
        print(f"Erro na análise pré-jogo: {e}")
        tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados detalhados para esta partida.", confidence=0))
    return tips

# --- NOVA ENGINE DE ANÁLISE AO VIVO ---
def analyze_live_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    tips = []
    try:
        url = f"https://v3.football.api-sports.io/fixtures?id={game_id}"
        live_response = requests.get(url, headers=headers, timeout=20)
        live_response.raise_for_status()
        data = live_response.json().get("response", [])
        if not data: raise ValueError("Sem dados ao vivo.")
        
        fixture_data = data[0]
        elapsed = fixture_data.get("fixture", {}).get("status", {}).get("elapsed", 0)
        home_goals = fixture_data.get("goals", {}).get("home", 0)
        away_goals = fixture_data.get("goals", {}).get("away", 0)
        
        # Busca estatísticas ao vivo
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={game_id}"
        stats_response = requests.get(stats_url, headers=headers)
        stats_data = stats_response.json().get("response", [])
        
        home_corners, away_corners = 0, 0
        if len(stats_data) == 2:
            for stat in stats_data[0].get('statistics', []):
                if stat.get('type') == 'Corner Kicks' and stat.get('value'): home_corners = int(stat.get('value'))
            for stat in stats_data[1].get('statistics', []):
                if stat.get('type') == 'Corner Kicks' and stat.get('value'): away_corners = int(stat.get('value'))

        # REGRA 1 AO VIVO: Gols no Final do Jogo
        if elapsed > 75 and home_goals == away_goals:
            tips.append(TipInfo(market="Gol nos Minutos Finais", suggestion=f"Acima de {home_goals + away_goals + 0.5} Gols", justification=f"O jogo está empatado aos {elapsed} minutos, ambos os times devem buscar o ataque.", confidence=65))

        # REGRA 2 AO VIVO: Escanteios
        total_corners = home_corners + away_corners
        if elapsed > 60 and total_corners < 8:
            tips.append(TipInfo(market="Escanteios Asiáticos", suggestion=f"Menos de {total_corners + 2.5} escanteios", justification=f"O jogo tem uma média baixa de escanteios ({total_corners} aos {elapsed} min), indicando tendência de under.", confidence=70))

        if not tips:
            tips.append(TipInfo(market="Análise Ao Vivo", suggestion="Mercado sem valor", justification="O jogo está se desenrolando sem criar oportunidades claras de aposta no momento.", confidence=0))

    except Exception as e:
        print(f"Erro na análise ao vivo: {e}")
        tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados ao vivo para esta partida.", confidence=0))
    return tips

# --- Endpoints da API ---
@app.get("/jogos-do-dia")
def get_daily_games_endpoint(sport: str = "football"):
    return get_daily_games_from_api(sport)

@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
def analyze_pre_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_pre_game(game_id, api_key, headers)

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
def analyze_live_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_live_game(game_id, api_key, headers)
