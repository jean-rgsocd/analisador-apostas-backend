# Filename: sports_betting_analyzer.py
# Versão 18.0 - Suporte total a esportes, busca em múltiplas datas e lógica de país opcional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import asyncio

app = FastAPI(title="Sports Betting Analyzer - Multi-Sport Final", version="18.0")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int

# --- MAPA DE ESPORTES ATUALIZADO COM TODAS AS INFORMAÇÕES CORRETAS ---
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
    api_key = os.getenv("API_KEY")
    config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido ou API Key não configurada.")
    url = f"https://{config['host']}/countries"
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    async with httpx.AsyncClient() as client:
        data = await fetch_api_data_async(client, {}, headers, url)
    return [{"name": c.get("name"), "code": c.get("code")} for c in data if c.get("code")]

@app.get("/ligas")
async def get_leagues(sport: str, country_code: Optional[str] = None):
    api_key = os.getenv("API_KEY")
    config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido ou API Key não configurada.")
    
    url = f"https://{config['host']}/leagues"
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    querystring = {"season": str(datetime.now().year)}

    if sport == 'football':
        if not country_code:
            raise HTTPException(status_code=400, detail="Para futebol, o código do país é obrigatório.")
        querystring["country_code"] = country_code
    
    async with httpx.AsyncClient() as client:
        data = await fetch_api_data_async(client, querystring, headers, url)
        
    return [{"id": l.get("id"), "name": l.get("name")} for l in data]

@app.get("/jogos")
async def get_games_by_filter(sport: str, league_id: int):
    api_key = os.getenv("API_KEY")
    config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido ou API Key não configurada.")
    
    today = datetime.now()
    dates_to_fetch = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
    
    url_endpoint = "/games"
    if sport == 'football':
        url_endpoint = "/fixtures"
    elif sport == 'formula-1':
        url_endpoint = "/races"
    
    url = f"https://{config['host']}{url_endpoint}"
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    
    async with httpx.AsyncClient() as client:
        tasks = []
        for date_str in dates_to_fetch:
            querystring = {"league": str(league_id), "season": str(datetime.now().year)}
            if sport != 'formula-1': # F1 não usa filtro de data
                querystring["date"] = date_str
            
            # Evita adicionar tasks duplicadas para F1
            if sport == 'formula-1' and len(tasks) > 0:
                continue
                
            tasks.append(fetch_api_data_async(client, querystring, headers, url))
        
        results = await asyncio.gather(*tasks)

    all_fixtures = [fixture for result in results for fixture in result]
    all_fixtures.sort(key=lambda x: x.get('fixture', x).get('timestamp', x.get('date', 0)))

    games_list = []
    for item in all_fixtures:
        home_team = "N/A"; away_team = "N/A"; game_id = 0; status = "N/A"; timestamp = None
        
        if sport == 'football':
            home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = item.get("fixture", {}).get("id", 0)
            status = item.get("fixture", {}).get("status", {}).get("short", "N/A")
            timestamp = item.get("fixture", {}).get("timestamp")
        elif sport == 'formula-1':
            home_team = item.get('competition', {}).get('name', 'Grande Prêmio')
            away_team = item.get('circuit', {}).get('name', 'N/A')
            game_id = item.get("id", 0)
            status = item.get("status", "N/A")
            timestamp = int(datetime.strptime(item.get("date"), "%Y-%m-%dT%H:%M:%S%z").timestamp()) if item.get("date") else None
        else: 
            home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = item.get("id", 0)
            status = item.get("status", {}).get("short", "N/A")
            timestamp = item.get("timestamp")
        
        game_dt = datetime.fromtimestamp(timestamp) if timestamp else None
        if game_dt:
            if game_dt.date() != today.date() and status in ['NS', '']:
                game_time = game_dt.strftime('%d/%m %H:%M')
            else:
                game_time = game_dt.strftime('%H:%M')
        else:
            game_time = "N/A"

        games_list.append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    
    return games_list
    
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int):
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification="Análise detalhada disponível apenas para futebol no momento.", confidence=0)]

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int):
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification="Análise detalhada disponível apenas para futebol no momento.", confidence=0)]
