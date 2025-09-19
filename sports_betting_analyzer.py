# Filename: sports_betting_analyzer.py
# Versão 22.0 - Otimizada a busca de ligas (remove filtro de 'season' para esportes não-futebol)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import asyncio
from collections import Counter

app = FastAPI(title="Sports Betting Analyzer - Multi-Sport Final", version="22.0")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int

SPORTS_MAP = {
    "football": {"host": "v3.football.api-sports.io"},
    "basketball": {"host": "v1.basketball.api-sports.io"},
    "nba": {"host": "v2.nba.api-sports.io"},
    "nfl": {"host": "v1.american-football.api-sports.io"},
    "baseball": {"host": "v1.baseball.api-sports.io"},
    "formula-1": {"host": "v1.formula-1.api-sports.io"},
    "handball": {"host": "v1.handball.api-sports.io"},
    "hockey": {"host": "v1.hockey.api-sports.io"},
    "mma": {"host": "v1.mma.api-sports.io"},
    "rugby": {"host": "v1.rugby.api-sports.io"},
    "volleyball": {"host": "v1.volleyball.api-sports.io"}
}

async def fetch_api_data_async(client: httpx.AsyncClient, querystring: dict, headers: dict, url: str) -> List:
    try:
        response = await client.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("errors") and (isinstance(data["errors"], list) and len(data["errors"]) > 0 or isinstance(data["errors"], dict) and len(data["errors"].keys()) > 0):
            print(f"Erro da API externa para {url} com params {querystring}: {data['errors']}")
            return []
        return data.get("response", [])
    except httpx.RequestError as e:
        print(f"Erro em uma chamada da API com httpx: {e}")
        return []

@app.get("/paises")
async def get_countries(sport: str):
    # ... (código sem alterações)
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"https://{config['host']}/countries"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    async with httpx.AsyncClient() as client: data = await fetch_api_data_async(client, {}, headers, url)
    return [{"name": c.get("name"), "code": c.get("code")} for c in data if c.get("code")]


# --- ATUALIZAÇÃO IMPORTANTE NA BUSCA DE LIGAS ---
@app.get("/ligas")
async def get_leagues(sport: str, country_code: Optional[str] = None):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"https://{config['host']}/leagues"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    
    # Apenas para futebol vamos manter a busca pela temporada atual para otimizar
    if sport == 'football':
        if not country_code: raise HTTPException(status_code=400, detail="País obrigatório para futebol.")
        querystring = {"season": str(datetime.now().year), "country_code": country_code}
    else:
        # Para todos os outros esportes, buscamos todas as ligas sem filtro de temporada
        querystring = {}
        
    async with httpx.AsyncClient() as client: data = await fetch_api_data_async(client, querystring, headers, url)
    return [{"id": l.get("id"), "name": l.get("name")} for l in data]

@app.get("/jogos")
async def get_games_by_filter(sport: str, league_id: int):
    # ... (código sem alterações)
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    today = datetime.now(); end_date = today + timedelta(days=2)
    url_endpoint = "/games"
    if sport == 'football': url_endpoint = "/fixtures"
    elif sport == 'formula-1': url_endpoint = "/races"
    url = f"https://{config['host']}{url_endpoint}"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    querystring = {"league": str(league_id), "season": str(datetime.now().year), "from": today.strftime('%Y-%m-%d'), "to": end_date.strftime('%Y-%m-%d')}
    if sport == 'formula-1':
        querystring.pop('from', None); querystring.pop('to', None)
    async with httpx.AsyncClient() as client: all_fixtures = await fetch_api_data_async(client, querystring, headers, url)
    all_fixtures.sort(key=lambda x: x.get('fixture', x).get('timestamp', x.get('date', 0)))
    games_list = []
    for item in all_fixtures:
        home_team, away_team, game_id, status, timestamp = "N/A", "N/A", 0, "N/A", None
        if sport == 'football': home_team, away_team, game_id, status, timestamp = item.get("teams", {}).get("home", {}).get("name", "N/A"), item.get("teams", {}).get("away", {}).get("name", "N/A"), item.get("fixture", {}).get("id", 0), item.get("fixture", {}).get("status", {}).get("short", "N/A"), item.get("fixture", {}).get("timestamp")
        elif sport == 'formula-1': home_team, away_team, game_id, status = item.get('competition', {}).get('name', 'Grande Prêmio'), item.get('circuit', {}).get('name', 'N/A'), item.get("id", 0), item.get("status", "N/A"); timestamp = int(datetime.strptime(item.get("date"), "%Y-%m-%dT%H:%M:%S%z").timestamp()) if item.get("date") else None
        else: home_team, away_team, game_id, status, timestamp = item.get("teams", {}).get("home", {}).get("name", "N/A"), item.get("teams", {}).get("away", {}).get("name", "N/A"), item.get("id", 0), item.get("status", {}).get("short", "N/A"), item.get("timestamp")
        game_dt = datetime.fromtimestamp(timestamp) if timestamp else None
        if game_dt: game_time = game_dt.strftime('%d/%m %H:%M') if game_dt.date() != today.date() and status in ['NS', ''] else game_dt.strftime('%H:%M')
        else: game_time = "N/A"
        games_list.append(GameInfo(home=home_team, away_team=away_team, time=game_time, game_id=game_id, status=status))
    return games_list

# O restante do código de análise continua igual...
# --- LÓGICA DE ANÁLISE DETALHADA ---
def find_stat(stat_list: List[Dict], stat_name: str) -> int:
# ... (código completo omitido para brevidade, mas deve ser mantido)
    return 0
async def analyze_football_pre_game(game_id: int, headers: dict) -> List[TipInfo]:
# ... (código completo omitido para brevidade, mas deve ser mantido)
    return []
async def analyze_football_live_game(game_id: int, headers: dict) -> List[TipInfo]:
# ... (código completo omitido para brevidade, mas deve ser mantido)
    return []
async def analyze_nba_pre_game(game_id: int, headers: dict) -> List[TipInfo]:
# ... (código completo omitido para brevidade, mas deve ser mantido)
    return []
# --- ENDPOINTS DE ANÁLISE PRINCIPAIS ---
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int, sport: str):
# ... (código completo omitido para brevidade, mas deve ser mantido)
    return []
@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int, sport: str):
# ... (código completo omitido para brevidade, mas deve ser mantido)
    return []
