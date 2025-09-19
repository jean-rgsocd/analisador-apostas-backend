# Filename: sports_betting_analyzer.py
# Versão 15.0 - Versão Definitiva (Totalmente Async, Análise Completa)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import time
import asyncio

app = FastAPI(title="Sports Betting Analyzer - Versão Definitiva", version="15.0")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- SISTEMA DE CACHE INTELIGENTE ---
GAMES_CACHE, PREGAME_ANALYSIS_CACHE, LIVE_ANALYSIS_CACHE = {}, {}, {}
CACHE_GAMES_LIST_SECONDS, CACHE_LIVE_ANALYSIS_SECONDS, CACHE_PREGAME_ANALYSIS_SECONDS = 900, 180, 3600

# --- MODELOS E MAPAS ---
class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int
SPORTS_MAP = {"football": {"endpoint_games": "/fixtures", "host": "v3.football.api-sports.io"}}

# --- FUNÇÕES AUXILIARES ---
def find_stat(stat_list: List[Dict], stat_name: str) -> int:
    for stat in stat_list:
        if stat.get('type') == stat_name:
            value = stat.get('value')
            if value is not None:
                try: return int(str(value).replace('%', '').strip())
                except (ValueError, TypeError): return 0
    return 0

async def fetch_api_data_async(client: httpx.AsyncClient, querystring: dict, headers: dict, url: str) -> List:
    try:
        response = await client.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        return response.json().get("response", [])
    except httpx.RequestError as e:
        print(f"Erro em uma chamada da API com httpx: {e}")
        return []

# --- LÓGICA DA API (ASSÍNCRONA) ---
async def get_daily_games_from_api(sport: str) -> Dict[str, List[GameInfo]]:
    current_time = time.time()
    if sport in GAMES_CACHE and (current_time - GAMES_CACHE[sport][0]) < CACHE_GAMES_LIST_SECONDS:
        return GAMES_CACHE[sport][1]

    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    config = SPORTS_MAP.get(sport.lower())
    if not config: raise HTTPException(status_code=400, detail="Esporte inválido.")
    
    url = f"https://{config['host']}{config['endpoint_games']}"
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    today = datetime.now()
    dates_to_fetch = [today.strftime("%Y-%m-%d"), (today + timedelta(days=1)).strftime("%Y-%m-%d")]

    async with httpx.AsyncClient() as client:
        tasks = [fetch_api_data_async(client, {"live": "all"}, headers, url)]
        tasks.extend([fetch_api_data_async(client, {"date": date_str}, headers, url) for date_str in dates_to_fetch])
        results = await asyncio.gather(*tasks)

    all_fixtures = [fixture for result in results for fixture in result]
    unique_fixtures = {fixture['fixture']['id']: fixture for fixture in all_fixtures}.values()
    
    games_by_league = {}
    if not unique_fixtures: return {"Info": []}
    for item in unique_fixtures:
        league_name = item.get("league", {}).get("name", "Outros")
        home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
        away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
        game_id = item.get("fixture", {}).get("id", 0)
        status = item.get("fixture", {}).get("status", {}).get("short", "N/A")
        timestamp = item.get("fixture", {}).get("timestamp")
        game_time = datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M') if status == 'NS' else datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
        if league_name not in games_by_league: games_by_league[league_name] = []
        games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    
    GAMES_CACHE[sport] = (current_time, games_by_league)
    return games_by_league

async def analyze_pre_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    current_time = time.time()
    if game_id in PREGAME_ANALYSIS_CACHE and (current_time - PREGAME_ANALYSIS_CACHE[game_id][0]) < CACHE_PREGAME_ANALYSIS_SECONDS:
        return PREGAME_ANALYSIS_CACHE[game_id][1]
    
    tips = []
    base_url = "https://v3.football.api-sports.io"
    
    async with httpx.AsyncClient() as client:
        tasks = {
            "odds": client.get(f"{base_url}/odds?fixture={game_id}", headers=headers),
            "fixture": client.get(f"{base_url}/fixtures?id={game_id}", headers=headers)
        }
        responses = await asyncio.gather(*tasks.values())
        odds_data = responses[0].json().get("response", [])
        fixture_data = responses[1].json().get("response", [])
    
    if not fixture_data: raise ValueError("Dados do fixture não encontrados.")
    home_team_id = fixture_data[0].get("teams", {}).get("home", {}).get("id")
    away_team_id = fixture_data[0].get("teams", {}).get("away", {}).get("id")
    home_team_name = fixture_data[0].get("teams", {}).get("home", {}).get("name", "Time da Casa")

    if odds_data:
        bet_values = odds_data[0].get("bookmakers", [{}])[0].get("bets", [{}])[0].get("values", [])
        home_odd = next((float(v.get("odd", 100)) for v in bet_values if v.get("value") == "Home"), 100)
        if 1 < home_odd < 1.65: tips.append(TipInfo(market="Vencedor da Partida", suggestion=f"Vitória do {home_team_name}", justification=f"Odds de {home_odd:.2f} indicam forte favoritismo.", confidence=int(100 - (home_odd - 1) * 100)))
    
    # Adicionar aqui a busca assíncrona por H2H se desejar mais detalhes

    if not tips: tips.append(TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados pré-jogo não apontam um favoritismo claro.", confidence=0))
    PREGAME_ANALYSIS_CACHE[game_id] = (current_time, tips)
    return tips

async def analyze_live_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    current_time = time.time()
    if game_id in LIVE_ANALYSIS_CACHE and (current_time - LIVE_ANALYSIS_CACHE[game_id][0]) < CACHE_LIVE_ANALYSIS_SECONDS:
        return LIVE_ANALYSIS_CACHE[game_id][1]
    
    tips = []
    base_url = "https://v3.football.api-sports.io"

    async with httpx.AsyncClient() as client:
        tasks = {
            "fixture": client.get(f"{base_url}/fixtures?id={game_id}", headers=headers),
            "stats": client.get(f"{base_url}/fixtures/statistics?fixture={game_id}", headers=headers)
        }
        responses = await asyncio.gather(*tasks.values())
        fixture_data = responses[0].json().get("response", [])
        stats_data = responses[1].json().get("response", [])
        
    if not fixture_data or len(stats_data) < 2: raise ValueError("Dados ao vivo incompletos.")
    
    fixture = fixture_data[0]
    elapsed = fixture.get("fixture", {}).get("status", {}).get("elapsed", 0)
    home_goals = fixture.get("goals", {}).get("home", 0); away_goals = fixture.get("goals", {}).get("away", 0)
    home_stats, away_stats = stats_data[0].get('statistics', []), stats_data[1].get('statistics', [])
    home_sot = find_stat(home_stats, 'Shots on Goal'); away_sot = find_stat(away_stats, 'Shots on Goal')
    total_sot = home_sot + away_sot
    
    if elapsed > 30 and total_sot > 7 and (home_goals + away_goals < 3):
        tips.append(TipInfo(market="Gols Ao Vivo", suggestion=f"Mais de {home_goals + away_goals + 0.5} Gols", justification=f"Jogo aberto com {total_sot} chutes a gol.", confidence=70))
    
    if not tips: tips.append(TipInfo(market="Análise Ao Vivo", suggestion="Aguardar", justification="Jogo sem oportunidades claras no momento.", confidence=0))
    LIVE_ANALYSIS_CACHE[game_id] = (current_time, tips)
    return tips

# --- Endpoints ---
@app.get("/jogos-do-dia")
async def get_daily_games_endpoint(sport: str = "football"): return await get_daily_games_from_api(sport)

@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return await analyze_pre_game(game_id, api_key, headers)

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return await analyze_live_game(game_id, api_key, headers)
