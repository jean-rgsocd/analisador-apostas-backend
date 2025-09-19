# Filename: sports_betting_analyzer.py
# Versão 28.1 - Corrigido o bug PydanticValidationError (away vs away_team)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import asyncio

app = FastAPI(title="Sports Betting Analyzer - Final Version", version="28.1")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GameInfo(BaseModel):
    home: str
    away: str
    time: str
    game_id: int
    status: str

class TipInfo(BaseModel):
    market: str
    suggestion: str
    justification: str
    confidence: int

SPORTS_MAP = {
    "football": {"host": "v3.football.api-sports.io"}, "basketball": {"host": "v1.basketball.api-sports.io"},
    "nba": {"host": "v2.nba.api-sports.io"}, "nfl": {"host": "v1.american-football.api-sports.io"},
    "baseball": {"host": "v1.baseball.api-sports.io"}, "formula-1": {"host": "v1.formula-1.api-sports.io"},
    "handball": {"host": "v1.handball.api-sports.io"}, "hockey": {"host": "v1.hockey.api-sports.io"},
    "mma": {"host": "v1.mma.api-sports.io"}, "rugby": {"host": "v1.rugby.api-sports.io"},
    "volleyball": {"host": "v1.volleyball.api-sports.io"}
}

async def fetch_api_data_async(client: httpx.AsyncClient, querystring: dict, headers: dict, url: str) -> List:
    try:
        response = await client.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("errors") and (isinstance(data["errors"], list) and len(data["errors"]) > 0 or isinstance(data["errors"], dict) and len(data["errors"].keys()) > 0):
            return []
        return data.get("response", [])
    except httpx.RequestError:
        return []

@app.get("/paises")
async def get_countries(sport: str):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"https://{config['host']}/countries"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    async with httpx.AsyncClient() as client: data = await fetch_api_data_async(client, {}, headers, url)
    return [{"name": c.get("name"), "code": c.get("code")} for c in data if c.get("code")]

@app.get("/ligas")
async def get_leagues(sport: str, country_code: Optional[str] = None):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"https://{config['host']}/leagues"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    if sport == 'football':
        if not country_code: raise HTTPException(status_code=400, detail="País obrigatório para futebol.")
        querystring = {"season": str(datetime.now().year), "country_code": country_code}
    else:
        querystring = {}
    async with httpx.AsyncClient() as client: data = await fetch_api_data_async(client, querystring, headers, url)
    return [{"id": l.get("id"), "name": l.get("name")} for l in data]

@app.get("/jogos-por-liga")
async def get_games_by_league(sport: str, league_id: int):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    today = datetime.now(); end_date = today + timedelta(days=1)
    url_endpoint = "/fixtures" if sport == 'football' else "/games"
    url = f"https://{config['host']}{url_endpoint}"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    querystring = {"league": str(league_id), "season": str(today.year), "from": today.strftime('%Y-%m-%d'), "to": end_date.strftime('%Y-%m-%d')}
    async with httpx.AsyncClient() as client: all_fixtures = await fetch_api_data_async(client, querystring, headers, url)
    all_fixtures.sort(key=lambda x: x.get('fixture', {}).get('timestamp', 0))
    games_list = []
    for item in all_fixtures:
        home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
        away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
        game_id = item.get("fixture", {}).get("id", 0)
        status = item.get("fixture", {}).get("status", {}).get("short", "N/A")
        timestamp = item.get("fixture", {}).get("timestamp")
        game_dt = datetime.fromtimestamp(timestamp) if timestamp else None
        game_time = game_dt.strftime('%d/%m %H:%M') if game_dt else "N/A"
        games_list.append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    return games_list

@app.get("/jogos-por-esporte")
async def get_games_by_sport(sport: str):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    today = datetime.now(); end_date = today + timedelta(days=1)
    url_endpoint = "/games"
    if sport == 'football': url_endpoint = "/fixtures"
    elif sport in ['formula-1', 'mma']:
        return []
    
    url = f"https://{config['host']}{url_endpoint}"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    querystring_today = {"date": today.strftime('%Y-%m-%d')}
    querystring_tomorrow = {"date": end_date.strftime('%Y-%m-%d')}
    
    async with httpx.AsyncClient() as client:
        today_fixtures = await fetch_api_data_async(client, querystring_today, headers, url)
        tomorrow_fixtures = await fetch_api_data_async(client, querystring_tomorrow, headers, url)

    all_fixtures = today_fixtures + tomorrow_fixtures
    all_fixtures.sort(key=lambda x: x.get('fixture', x).get('timestamp', 0))
    
    games_list = []
    for item in all_fixtures:
        home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
        away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
        game_id = item.get("id", item.get("fixture", {}).get("id", 0))
        status = item.get("status", {}).get("short", "N/A")
        timestamp = item.get("timestamp", item.get("fixture", {}).get("timestamp"))
        game_dt = datetime.fromtimestamp(timestamp) if timestamp else None
        game_time = game_dt.strftime('%d/%m %H:%M') if game_dt else "N/A"
        
        # --- A CORREÇÃO ESTÁ AQUI ---
        games_list.append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    
    return games_list

# ... (As funções de análise e os endpoints de análise continuam os mesmos) ...
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int, sport: str):
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification="Análise detalhada ainda não implementada para este esporte.", confidence=0)]

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int, sport: str):
    return [TipInfo(market="Análise Ao Vivo", suggestion="Não disponível", justification="Análise ao vivo ainda não implementada.", confidence=0)]
