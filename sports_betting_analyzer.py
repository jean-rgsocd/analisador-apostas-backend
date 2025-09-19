# Filename: sports_betting_analyzer.py
# Versão 12.2 - Visão de Futuro (Ao Vivo + Próximos 2 Dias)

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime, timedelta
import asyncio

app = FastAPI(title="Sports Betting Analyzer - Tipster IA Definitivo", version="12.2")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int

SPORTS_MAP = {"football": {"endpoint_games": "/fixtures", "host": "v3.football.api-sports.io"}}

# Função auxiliar para fazer uma única chamada à API
def fetch_api_data(querystring: dict, headers: dict, url: str) -> List:
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        return response.json().get("response", [])
    except Exception as e:
        print(f"Erro em uma chamada da API: {e}")
        return []

def get_future_games_from_api(sport: str) -> Dict[str, List[GameInfo]]:
    games_by_league = {}
    api_key = os.getenv("API_KEY")
    if not api_key: return {"Erro": []}
    
    config = SPORTS_MAP.get(sport.lower())
    if not config: return {"Erro": []}

    url = f"https://{config['host']}{config['endpoint_games']}"
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    
    # Define as datas
    today = datetime.now()
    dates_to_fetch = [today.strftime("%Y-%m-%d"), 
                      (today + timedelta(days=1)).strftime("%Y-%m-%d"), 
                      (today + timedelta(days=2)).strftime("%Y-%m-%d")]

    all_fixtures = []
    
    # Busca jogos ao vivo
    live_fixtures = fetch_api_data({"live": "all"}, headers, url)
    all_fixtures.extend(live_fixtures)
    
    # Busca jogos agendados para os próximos dias
    for date_str in dates_to_fetch:
        day_fixtures = fetch_api_data({"date": date_str}, headers, url)
        all_fixtures.extend(day_fixtures)
        
    # Remove duplicados usando o ID do jogo
    unique_fixtures = {fixture['fixture']['id']: fixture for fixture in all_fixtures}.values()

    if not unique_fixtures:
        return {"Info": [GameInfo(home="Nenhum jogo encontrado (Ao vivo ou nos próximos 2 dias).", away="", time="")]}

    for item in unique_fixtures:
        league_name = item.get("league", {}).get("name", "Outros")
        home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
        away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
        game_id = item.get("fixture", {}).get("id", 0)
        status = item.get("fixture", {}).get("status", {}).get("short", "N/A")
        timestamp = item.get("fixture", {}).get("timestamp")
        
        # Formata a data e hora para jogos futuros
        if status == 'NS': # Not Started
            game_time = datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M') if timestamp else "N/A"
        else: # Jogos ao vivo
            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"

        if league_name not in games_by_league: games_by_league[league_name] = []
        games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    
    return games_by_league

# ... (o resto do código, com as engines de análise, permanece o mesmo) ...

def analyze_pre_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    # (código da análise pré-jogo que já temos)
    tips = []; 
    try:
        odds_url = f"https://v3.football.api-sports.io/odds?fixture={game_id}"
        odds_response = requests.get(odds_url, headers=headers).json().get("response", [])
        if odds_response:
            bet = odds_response[0].get("bookmakers", [{}])[0].get("bets", [{}])[0]
            values = bet.get("values", [])
            home_odd, away_odd = 0, 0
            for value in values:
                if value.get("value") == "Home": home_odd = float(value.get("odd", 100))
                if value.get("value") == "Away": away_odd = float(value.get("odd", 100))
            if home_odd < 1.6 and home_odd > 1:
                tips.append(TipInfo(market="Vencedor da Partida", suggestion="Vitória do Time da Casa", justification=f"As odds de {home_odd:.2f} indicam forte favoritismo.", confidence=80))
            elif away_odd < 1.6 and away_odd > 1:
                 tips.append(TipInfo(market="Vencedor da Partida", suggestion="Vitória do Time Visitante", justification=f"As odds de {away_odd:.2f} indicam forte favoritismo.", confidence=80))
        if not tips: tips.append(TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados não apontam um favoritismo claro.", confidence=0))
    except Exception as e:
        print(f"Erro na análise pré-jogo: {e}"); tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter os dados necessários.", confidence=0))
    return tips

def analyze_live_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    # (código da análise ao vivo que já temos)
    tips = []
    try:
        fixture_url = f"https://v3.football.api-sports.io/fixtures?id={game_id}"
        fixture_response = requests.get(fixture_url, headers=headers).json().get("response", [])
        if not fixture_response: raise ValueError("Dados do fixture não encontrados.")
        fixture = fixture_response[0]
        elapsed = fixture.get("fixture", {}).get("status", {}).get("elapsed", 0)
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={game_id}"
        stats_response = requests.get(stats_url, headers=headers).json().get("response", [])
        home_sot, away_sot = 0, 0
        if len(stats_response) == 2:
            home_stats = stats_response[0].get('statistics', [])
            away_stats = stats_response[1].get('statistics', [])
            def find_stat(sl, sn):
                for s in sl:
                    if s.get('type') == sn and s.get('value'): return int(s.get('value'))
                return 0
            home_sot = find_stat(home_stats, 'Shots on Goal')
            away_sot = find_stat(away_stats, 'Shots on Goal')
        if not tips: tips.append(TipInfo(market="Análise Ao Vivo", suggestion="Aguardar", justification="Jogo sem oportunidades claras no momento.", confidence=0))
    except Exception as e:
        print(f"Erro na análise ao vivo: {e}"); tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados ao vivo.", confidence=0))
    return tips

@app.get("/jogos-do-dia")
def get_daily_games_endpoint(sport: str = "football"): return get_future_games_from_api(sport)
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
def analyze_pre_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_pre_game(game_id, api_key, headers)
@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
def analyze_live_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_live_game(game_id, api_key, headers)
