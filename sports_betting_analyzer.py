# Filename: sports_betting_analyzer.py
# Versão 10.1 - Tipster com Regra de Virada do Usuário

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer - Tipster IA", version="10.1")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int

# --- Lógica da API ---
SPORTS_MAP = {"football": {"endpoint_games": "/fixtures", "host": "v3.football.api-sports.io"}}

def get_daily_games_from_api(sport: str) -> Dict[str, List[GameInfo]]:
    # (Esta função permanece a mesma)
    games_by_league = {}; api_key = os.getenv("API_KEY")
    if not api_key: return {"Erro": []}
    config = SPORTS_MAP.get(sport.lower())
    if not config: return {"Erro": []}
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://{config['host']}{config['endpoint_games']}"
    querystring = {"date": today}
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status(); data = response.json()
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
        print(f"Erro ao buscar jogos: {e}"); return {"Erro": []}

def analyze_pre_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    # (Esta função permanece a mesma)
    tips = []
    try:
        h2h_url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={game_id}-{game_id}"
        h2h_response = requests.get(h2h_url, headers=headers).json().get("response", [])
        if not h2h_response: raise ValueError("Dados de H2H não disponíveis.")
        total_goals = 0
        for match in h2h_response[:5]: total_goals += match.get("goals", {}).get("home", 0) + match.get("goals", {}).get("away", 0)
        avg_goals = total_goals / len(h2h_response) if h2h_response else 2.5
        if avg_goals > 2.7:
            tips.append(TipInfo(market="Total de Gols", suggestion="Mais de 2.5 Gols", justification=f"A média de gols nos últimos {len(h2h_response)} confrontos diretos é de {avg_goals:.2f}.", confidence=75))
        if not tips: tips.append(TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados históricos não apontam um favoritismo claro.", confidence=0))
    except Exception as e:
        print(f"Erro na análise pré-jogo: {e}"); tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados detalhados.", confidence=0))
    return tips

def analyze_live_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    tips = []
    try:
        fixture_url = f"https://v3.football.api-sports.io/fixtures?id={game_id}"
        fixture_response = requests.get(fixture_url, headers=headers).json().get("response", [])
        if not fixture_response: raise ValueError("Dados do fixture não encontrados.")
        
        fixture = fixture_response[0]
        elapsed = fixture.get("fixture", {}).get("status", {}).get("elapsed", 0)
        home_goals = fixture.get("goals", {}).get("home", 0)
        away_goals = fixture.get("goals", {}).get("away", 0)
        home_team_name = fixture.get("teams", {}).get("home", {}).get("name", "Time da Casa")
        away_team_name = fixture.get("teams", {}).get("away", {}).get("name", "Time Visitante")
        
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={game_id}"
        stats_response = requests.get(stats_url, headers=headers).json().get("response", [])
        
        home_sot, away_sot, home_corners, home_possession = 0, 0, 0, 0
        if len(stats_response) == 2:
            home_stats = stats_response[0].get('statistics', [])
            away_stats = stats_response[1].get('statistics', [])
            def find_stat(sl, sn):
                for s in sl:
                    if s.get('type') == sn and s.get('value'):
                        # Remove '%' e converte para int
                        return int(str(s.get('value')).replace('%',''))
                return 0
            home_sot = find_stat(home_stats, 'Shots on Goal')
            away_sot = find_stat(away_stats, 'Shots on Goal')
            home_corners = find_stat(home_stats, 'Corner Kicks')
            home_possession = find_stat(home_stats, 'Ball Possession')

        # REGRA 1: Gol no 1º Tempo (Sua Regra)
        if elapsed < 45 and home_goals == 0 and away_goals == 0 and (home_sot + away_sot) >= 3:
            tips.append(TipInfo(market="Gols no 1º Tempo", suggestion="Mais de 0.5 Gols (HT)", justification=f"O jogo está 0x0 mas já tem {home_sot+away_sot} chutes a gol, indicando pressão.", confidence=70))

        # REGRA 2: Virada no 2º Tempo (Sua Regra)
        if 50 <= elapsed <= 65:
            # Caso 1: Time da casa perdendo mas amassando
            if home_goals < away_goals and home_possession > 65 and home_sot > (away_sot + 3):
                tips.append(TipInfo(market="Resultado
