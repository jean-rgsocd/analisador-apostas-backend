# Filename: sports_betting_analyzer.py
# Versão 8.0 - Tipster IA com Análise Heurística Real

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer - Tipster IA", version="8.0")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int

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
            timestamp = item.get("fixture", {}).get("timestamp")
            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            if league_name not in games_by_league: games_by_league[league_name] = []
            games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id))
        return games_by_league
    except Exception as e:
        print(f"Erro ao buscar jogos: {e}"); return {"Erro": []}

# --- A NOVA ENGINE DE ANÁLISE REAL ---
def get_fixture_statistics(fixture_id: int, api_key: str, headers: dict) -> dict:
    stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
    response = requests.get(stats_url, headers=headers)
    if response.status_code == 200 and response.json().get("response"):
        return response.json()["response"]
    return []

def analyze_game_with_raw_stats(game_id: int, api_key: str) -> List[TipInfo]:
    tips = []
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    stats = get_fixture_statistics(game_id, api_key, headers)

    if not stats or len(stats) < 2:
        return [TipInfo(market="Dados Insuficientes", suggestion="Aguardar ao vivo", justification="Não há estatísticas detalhadas disponíveis para esta partida para uma análise pré-jogo.", confidence=0)]

    team_home_stats = stats[0].get('statistics', [])
    team_away_stats = stats[1].get('statistics', [])

    # Função auxiliar para encontrar uma estatística específica
    def find_stat(stat_list, stat_name):
        for stat in stat_list:
            if stat.get('type') == stat_name:
                return stat.get('value')
        return 0

    # --- ANÁLISE DE ESCANTEIOS ---
    home_corners_str = find_stat(team_home_stats, 'Corner Kicks')
    away_corners_str = find_stat(team_away_stats, 'Corner Kicks')
    if home_corners_str and away_corners_str:
        try:
            total_corners = int(home_corners_str) + int(away_corners_str)
            if total_corners > 9:
                tips.append(TipInfo(market="Total de Escanteios", suggestion="Mais de 8.5", justification=f"A média somada das equipes é de {total_corners} escanteios por jogo.", confidence=70))
        except (ValueError, TypeError):
            pass # Ignora se o valor não for um número

    # --- ANÁLISE DE GOLS ---
    home_goals_str = find_stat(team_home_stats, 'Goals')
    away_goals_str = find_stat(team_away_stats, 'Goals')
    if home_goals_str and away_goals_str:
        try:
            avg_goals = float(home_goals_str) + float(away_goals_str)
            if avg_goals > 2.8:
                 tips.append(TipInfo(market="Total de Gols", suggestion="Mais de 2.5", justification=f"A média de gols somada das equipes é de {avg_goals:.2f} por jogo.", confidence=75))
            elif avg_goals > 1.8:
                 tips.append(TipInfo(market="Total de Gols", suggestion="Mais de 1.5", justification=f"A média de gols somada das equipes é de {avg_goals:.2f} por jogo.", confidence=80))
        except (ValueError, TypeError):
            pass

    # --- ANÁLISE DE CARTÕES ---
    home_cards_str = find_stat(team_home_stats, 'Yellow Cards')
    away_cards_str = find_stat(team_away_stats, 'Yellow Cards')
    if home_cards_str and away_cards_str:
        try:
            total_cards = int(home_cards_str) + int(away_cards_str)
            if total_cards > 4:
                tips.append(TipInfo(market="Total de Cartões", suggestion="Mais de 3.5", justification=f"A média de cartões somada das equipes é de {total_cards} por jogo.", confidence=65))
        except (ValueError, TypeError):
            pass

    if not tips:
        tips.append(TipInfo(market="Análise Conclusiva", suggestion="Aguardar ao vivo", justification="Os dados pré-jogo não indicam uma vantagem clara para nenhum mercado.", confidence=0))
        
    return tips

# --- Endpoints da API ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint(sport: str = "football"):
    return get_daily_games_from_api(sport)

@app.get("/analisar-jogo", response_model=List[TipInfo]])
def analyze_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    # Usamos a nova função de análise com estatísticas brutas
    return analyze_game_with_raw_stats(game_id, api_key)
