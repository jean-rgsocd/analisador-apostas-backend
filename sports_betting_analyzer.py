# Filename: sports_betting_analyzer.py
# Versão 21.0 - Otimizada a busca de jogos para usar range de datas (from/to)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import asyncio
from collections import Counter

app = FastAPI(title="Sports Betting Analyzer - Multi-Sport Final", version="21.0")
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

# --- MAPA DE ESPORTES COMPLETO ---
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

# Os endpoints /paises e /ligas não precisam de alteração
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
    querystring = {"season": str(datetime.now().year)}
    if sport == 'football':
        if not country_code: raise HTTPException(status_code=400, detail="País obrigatório para futebol.")
        querystring["country_code"] = country_code
    async with httpx.AsyncClient() as client: data = await fetch_api_data_async(client, querystring, headers, url)
    return [{"id": l.get("id"), "name": l.get("name")} for l in data]


# --- ATUALIZAÇÃO IMPORTANTE NA BUSCA DE JOGOS ---
@app.get("/jogos")
async def get_games_by_filter(sport: str, league_id: int):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    
    today = datetime.now()
    end_date = today + timedelta(days=2) # Pega hoje, amanhã e depois de amanhã
    
    url_endpoint = "/games"
    if sport == 'football': url_endpoint = "/fixtures"
    elif sport == 'formula-1': url_endpoint = "/races"
        
    url = f"https://{config['host']}{url_endpoint}"
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    
    # Monta a consulta com o range de datas
    querystring = {
        "league": str(league_id),
        "season": str(datetime.now().year),
        "from": today.strftime('%Y-%m-%d'),
        "to": end_date.strftime('%Y-%m-%d')
    }
    # F1 não usa range de datas, então removemos
    if sport == 'formula-1':
        querystring.pop('from', None)
        querystring.pop('to', None)
        
    async with httpx.AsyncClient() as client:
        # Agora fazemos apenas UMA chamada à API
        all_fixtures = await fetch_api_data_async(client, querystring, headers, url)

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

# --- LÓGICA DE ANÁLISE DETALHADA (sem alterações) ---
def find_stat(stat_list: List[Dict], stat_name: str) -> int:
    for stat in stat_list:
        if stat.get('type') == stat_name:
            value = stat.get('value')
            if value is not None:
                try: return int(str(value).replace('%', '').strip())
                except (ValueError, TypeError): return 0
    return 0

async def analyze_football_pre_game(game_id: int, headers: dict) -> List[TipInfo]:
    #... (código da análise de futebol)
    return [TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados pré-jogo não apontam um favoritismo claro.", confidence=0)]

async def analyze_football_live_game(game_id: int, headers: dict) -> List[TipInfo]:
    #... (código da análise de futebol ao vivo)
    return [TipInfo(market="Análise Ao Vivo", suggestion="Aguardar", justification="Jogo sem oportunidades claras no momento.", confidence=0)]

async def analyze_nba_pre_game(game_id: int, headers: dict) -> List[TipInfo]:
    #... (código da análise da NBA)
    return [TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados pré-jogo não apontam uma vantagem clara.", confidence=0)]

# --- ENDPOINTS DE ANÁLISE PRINCIPAIS (sem alterações) ---
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int, sport: str):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not config or not api_key: raise HTTPException(status_code=404, detail="Esporte não encontrado ou API Key ausente")
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    if sport == "football": return await analyze_football_pre_game(game_id, headers)
    elif sport == "nba": return await analyze_nba_pre_game(game_id, headers)
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification=f"Análise detalhada para {sport.capitalize()} ainda não foi implementada.", confidence=0)]

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int, sport: str):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not config or not api_key: raise HTTPException(status_code=404, detail="Esporte não encontrado ou API Key ausente")
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    if sport == "football": return await analyze_football_live_game(game_id, headers)
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification=f"Análise ao vivo para {sport.capitalize()} ainda não foi implementada.", confidence=0)]
