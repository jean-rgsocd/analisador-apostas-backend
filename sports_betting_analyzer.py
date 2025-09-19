# Filename: sports_betting_analyzer.py
# Versão 15.1 - Corrigido o erro 'app is not defined'

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import time
import asyncio

# --- CORREÇÃO AQUI: A linha mais importante que estava faltando ---
app = FastAPI(title="Sports Betting Analyzer - Versão Definitiva", version="15.1")

# --- O resto do seu código, que já estava ótimo ---
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

# --- NOVOS ENDPOINTS PARA FILTROS DINÂMICOS ---
@app.get("/paises")
async def get_countries():
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    url = "https://v3.football.api-sports.io/countries"
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    async with httpx.AsyncClient() as client:
        data = await fetch_api_data_async(client, {}, headers, url)
    return [{"name": c.get("name"), "code": c.get("code")} for c in data if c.get("code")]

@app.get("/ligas")
async def get_leagues_by_country(country_code: str):
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    url = "https://v3.football.api-sports.io/leagues"
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    querystring = {"code": country_code, "season": str(datetime.now().year)}
    async with httpx.AsyncClient() as client:
        data = await fetch_api_data_async(client, querystring, headers, url)
    return [{"id": l.get("league", {}).get("id"), "name": l.get("league", {}).get("name")} for l in data]

@app.get("/jogos")
async def get_games_by_filter(league_id: int, date: Optional[str] = None):
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    if not date: date = datetime.now().strftime("%Y-%m-%d")
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    querystring = {"league": str(league_id), "season": str(datetime.now().year), "date": date}
    async with httpx.AsyncClient() as client:
        fixtures_data = await fetch_api_data_async(client, querystring, headers, url)
    games_list = []
    if not fixtures_data: return []
    for item in fixtures_data:
        home_team, away_team = item.get("teams", {}).get("home", {}).get("name", "N/A"), item.get("teams", {}).get("away", {}).get("name", "N/A")
        game_id, status = item.get("fixture", {}).get("id", 0), item.get("fixture", {}).get("status", {}).get("short", "N/A")
        timestamp = item.get("fixture", {}).get("timestamp")
        game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
        games_list.append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    return games_list

# --- LÓGICA DE ANÁLISE (O seu código original, que está perfeito) ---
async def analyze_pre_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    # ... (seu código de análise pré-jogo aqui, sem alterações)
    return [TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados pré-jogo não apontam um favoritismo claro.", confidence=0)] # Exemplo

async def analyze_live_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    # ... (seu código de análise ao-vivo aqui, sem alterações)
    return [TipInfo(market="Análise Ao Vivo", suggestion="Aguardar", justification="Jogo sem oportunidades claras no momento.", confidence=0)] # Exemplo

# --- Endpoints de Análise ---
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return await analyze_pre_game(game_id, api_key, headers)

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return await analyze_live_game(game_id, api_key, headers)
