# Filename: sports_betting_analyzer.py
# Versão 16.0 - Suporte Multi-Esportes (Futebol, Basquete, NFL)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import asyncio

app = FastAPI(title="Sports Betting Analyzer - Multi-Sport", version="16.0")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- MODELOS ---
class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int

# --- MAPA DE ESPORTES ATUALIZADO ---
# Adicionamos Basketball e NFL com seus respectivos hosts
SPORTS_MAP = {
    "football": {"host": "v3.football.api-sports.io"},
    "basketball": {"host": "v1.basketball.api-sports.io"},
    "nfl": {"host": "v1.nfl.api-sports.io"}
}

# --- FUNÇÕES AUXILIARES (sem alteração) ---
async def fetch_api_data_async(client: httpx.AsyncClient, querystring: dict, headers: dict, url: str) -> List:
    try:
        response = await client.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()
        # Algumas APIs retornam 'errors' como uma lista ou dict, vamos tratar isso
        if data.get("errors") and (isinstance(data["errors"], list) and len(data["errors"]) > 0 or isinstance(data["errors"], dict) and len(data["errors"].keys()) > 0):
             print(f"Erro da API externa: {data['errors']}")
             return []
        return data.get("response", [])
    except httpx.RequestError as e:
        print(f"Erro em uma chamada da API com httpx: {e}")
        return []

# --- ENDPOINTS ATUALIZADOS PARA ACEITAR 'sport' ---

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
async def get_leagues_by_country(sport: str, country_code: str):
    api_key = os.getenv("API_KEY")
    config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido ou API Key não configurada.")
    
    url = f"https://{config['host']}/leagues"
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    querystring = {"country_code": country_code, "season": str(datetime.now().year)} # Ajustado para country_code
    
    # NFL não usa 'country_code', então podemos buscar todas as ligas
    if sport == 'nfl':
        querystring = {"season": str(datetime.now().year)}

    async with httpx.AsyncClient() as client:
        data = await fetch_api_data_async(client, querystring, headers, url)
        
    return [{"id": l.get("id"), "name": l.get("name")} for l in data]

@app.get("/jogos")
async def get_games_by_filter(sport: str, league_id: int, date: Optional[str] = None):
    api_key = os.getenv("API_KEY")
    config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido ou API Key não configurada.")
    
    if not date: date = datetime.now().strftime("%Y-%m-%d")
    
    url = f"https://{config['host']}/games" # Endpoint para jogos é '/games' para a maioria dos outros esportes
    if sport == 'football':
        url = f"https://{config['host']}/fixtures" # Futebol usa '/fixtures'
        
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    querystring = {"league": str(league_id), "season": str(datetime.now().year), "date": date}

    async with httpx.AsyncClient() as client:
        fixtures_data = await fetch_api_data_async(client, querystring, headers, url)

    games_list = []
    if not fixtures_data: return []

    for item in fixtures_data:
        # A estrutura da resposta da API pode variar um pouco entre os esportes
        if sport == 'football':
            home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = item.get("fixture", {}).get("id", 0)
            status = item.get("fixture", {}).get("status", {}).get("short", "N/A")
            timestamp = item.get("fixture", {}).get("timestamp")
        else: # Basquete, NFL, etc.
            home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = item.get("id", 0)
            status = item.get("status", {}).get("short", "N/A")
            timestamp = item.get("timestamp")

        game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
        games_list.append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    
    return games_list

# OBS: Os endpoints de análise (/analisar-pre-jogo e /analisar-ao-vivo) ainda estão com a lógica de futebol.
# Precisaríamos de mais detalhes da API para criar análises para outros esportes. Por enquanto, eles retornarão um resultado padrão.

@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int):
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification="Análise detalhada disponível apenas para futebol no momento.", confidence=0)]

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int):
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification="Análise detalhada disponível apenas para futebol no momento.", confidence=0)]
