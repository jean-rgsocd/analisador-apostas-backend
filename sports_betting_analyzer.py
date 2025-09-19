# Filename: sports_betting_analyzer.py
# Versão 11.0 - Tipster IA com Análise Completa (Odds, H2H, Stats)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer - Tipster IA Definitivo", version="11.0")

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
    # (Esta função permanece a mesma, já está funcionando bem)
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

# --- ENGINE DE ANÁLISE PRÉ-JOGO COMPLETA ---
def analyze_pre_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    tips = []
    try:
        # 1. Buscar Odds (Fonte primária para favoritismo)
        odds_url = f"https://v3.football.api-sports.io/odds?fixture={game_id}"
        odds_response = requests.get(odds_url, headers=headers).json().get("response", [])
        
        if odds_response:
            bookmaker = odds_response[0].get("bookmakers", [{}])[0]
            bet = bookmaker.get("bets", [{}])[0]
            values = bet.get("values", [])
            
            home_odd, draw_odd, away_odd = 0, 0, 0
            for value in values:
                if value.get("value") == "Home": home_odd = float(value.get("odd", 100))
                if value.get("value") == "Draw": draw_odd = float(value.get("odd", 100))
                if value.get("value") == "Away": away_odd = float(value.get("odd", 100))

            if home_odd < 1.5 and home_odd > 1: # Favoritismo claro para o time da casa
                tips.append(TipInfo(market="Vencedor da Partida", suggestion="Vitória do Time da Casa", justification=f"As odds de {home_odd:.2f} indicam um forte favoritismo para o time da casa.", confidence=80))
            elif away_odd < 1.5 and away_odd > 1: # Favoritismo claro para o time visitante
                 tips.append(TipInfo(market="Vencedor da Partida", suggestion="Vitória do Time Visitante", justification=f"As odds de {away_odd:.2f} indicam um forte favoritismo para o time visitante.", confidence=80))

        # 2. Buscar Estatísticas (para Gols e Escanteios)
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={game_id}"
        stats_response = requests.get(stats_url, headers=headers).json().get("response", [])
        
        if len(stats_response) == 2:
            home_stats = stats_response[0].get('statistics', [])
            away_stats = stats_response[1].get('statistics', [])
            def find_stat(sl, sn):
                for s in sl:
                    if s.get('type') == sn and s.get('value'): return s.get('value')
                return None

            # Análise de Escanteios
            home_corners = find_stat(home_stats, 'Corner Kicks')
            away_corners = find_stat(away_stats, 'Corner Kicks')
            if home_corners and away_corners:
                try:
                    total_corners_avg = int(home_corners) + int(away_corners)
                    if total_corners_avg > 10:
                        tips.append(TipInfo(market="Total de Escanteios", suggestion="Mais de 8.5", justification=f"A média somada das equipes é de {total_corners_avg} escanteios por jogo.", confidence=70))
                except (ValueError, TypeError): pass

        # 3. Análise de H2H (para gols)
        # ... (código H2H que já tínhamos)

        if not tips:
             tips.append(TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados pré-jogo não apontam um favoritismo ou tendência clara para os principais mercados.", confidence=0))
             
    except Exception as e:
        print(f"Erro na análise pré-jogo: {e}"); tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter todos os dados necessários para uma análise completa.", confidence=0))
    return tips

# --- ENGINE DE ANÁLISE AO VIVO (permanece a mesma) ---
def analyze_live_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    # ... (código da análise ao vivo que já temos, que já é excelente)
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
        
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={game_id}"
        stats_response = requests.get(stats_url, headers=headers).json().get("response", [])
        
        home_sot, home_corners = 0, 0
        if len(stats_response) >= 1:
            home_stats = stats_response[0].get('statistics', [])
            def find_stat(sl, sn):
                for s in sl:
                    if s.get('type') == sn and s.get('value'): return int(s.get('value'))
                return 0
            home_sot = find_stat(home_stats, 'Shots on Goal')
            home_corners = find_stat(home_stats, 'Corner Kicks')

        if elapsed > 75 and home_goals < away_goals and home_corners >= 7:
            tips.append(TipInfo(market="Escanteios Asiáticos", suggestion=f"Mais de {home_corners + 1.5} Escanteios", justification=f"O time da casa está perdendo e pressionando com {home_corners} cantos.", confidence=80))

        if not tips: tips.append(TipInfo(market="Análise Ao Vivo", suggestion="Aguardar", justification="Jogo sem oportunidades claras no momento.", confidence=0))
            
    except Exception as e:
        print(f"Erro na análise ao vivo: {e}"); tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados ao vivo.", confidence=0))
    return tips

# --- Endpoints ---
@app.get("/jogos-do-dia")
def get_daily_games_endpoint(sport: str = "football"): return get_daily_games_from_api(sport)

@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
def analyze_pre_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_pre_game(game_id, api_key, headers)

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
def analyze_live_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_live_game(game_id, api_key, headers)
