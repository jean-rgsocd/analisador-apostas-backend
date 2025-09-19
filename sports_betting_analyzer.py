# Filename: sports_betting_analyzer.py
# Versão 30.0 - Adicionada lógica de análise inteligente para a Fórmula 1

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import asyncio
from collections import Counter

app = FastAPI(title="Sports Betting Analyzer - Full Intelligence", version="30.0")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ... (Models e SPORTS_MAP continuam os mesmos) ...
class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int
SPORTS_MAP = {
    "football": {"host": "v3.football.api-sports.io"}, "basketball": {"host": "v1.basketball.api-sports.io"},
    "nba": {"host": "v2.nba.api-sports.io"}, "nfl": {"host": "v1.american-football.api-sports.io"},
    "baseball": {"host": "v1.baseball.api-sports.io"}, "formula-1": {"host": "v1.formula-1.api-sports.io"},
    "handball": {"host": "v1.handball.api-sports.io"}, "hockey": {"host": "v1.hockey.api-sports.io"},
    "mma": {"host": "v1.mma.api-sports.io"}, "rugby": {"host": "v1.rugby.api-sports.io"},
    "volleyball": {"host": "v1.volleyball.api-sports.io"}
}

# ... (Funções de fetch, paises, ligas, e jogos continuam as mesmas) ...
async def fetch_api_data_async(client: httpx.AsyncClient, querystring: dict, headers: dict, url: str) -> List:
    # ... (código omitido para brevidade)
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
    # ... (código omitido para brevidade)
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"https://{config['host']}/leagues"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    if sport == 'football':
        if not country_code: raise HTTPException(status_code=400, detail="País obrigatório para futebol.")
        querystring = {"season": str(datetime.now().year), "country_code": country_code}
    else: querystring = {}
    async with httpx.AsyncClient() as client: data = await fetch_api_data_async(client, querystring, headers, url)
    return [{"id": l.get("id"), "name": l.get("name")} for l in data]

@app.get("/jogos-por-esporte")
async def get_games_by_sport(sport: str):
    # ... (código omitido para brevidade)
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    today = datetime.now(); end_date = today + timedelta(days=1)
    url_endpoint = "/games"
    if sport == 'football': url_endpoint = "/fixtures"
    elif sport in ['formula-1', 'mma']: return []
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
        home_team, away_team, game_id, status, timestamp = item.get("teams", {}).get("home", {}).get("name", "N/A"), item.get("teams", {}).get("away", {}).get("name", "N/A"), item.get("id", item.get("fixture", {}).get("id", 0)), item.get("status", {}).get("short", "N/A"), item.get("timestamp", item.get("fixture", {}).get("timestamp"))
        game_dt = datetime.fromtimestamp(timestamp) if timestamp else None
        game_time = game_dt.strftime('%d/%m %H:%M') if game_dt else "N/A"
        games_list.append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    return games_list
    
# --- LÓGICA DE ANÁLISE DETALHADA ---

async def analyze_football_pre_game(game_id: int, headers: dict) -> List[TipInfo]:
    # ... (lógica de futebol, omitida para brevidade)
    return [TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados pré-jogo não apontam um favoritismo claro.", confidence=0)]

async def analyze_team_sport_h2h(game_id: int, sport: str, headers: dict) -> List[TipInfo]:
    # ... (lógica de esportes de equipe, omitida para brevidade)
    return [TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="O histórico de confrontos não aponta um favorito claro.", confidence=0)]

# --- NOVA LÓGICA DE ANÁLISE PARA F1 ---
async def analyze_f1_pre_race(race_id: int, headers: dict) -> List[TipInfo]:
    tips = []
    base_url = "https://v1.formula-1.api-sports.io"
    season = datetime.now().year
    
    async with httpx.AsyncClient() as client:
        # Busca o grid de largada e o ranking do campeonato em paralelo
        grid_task = client.get(f"{base_url}/rankings/starting_grid?race={race_id}", headers=headers)
        standings_task = client.get(f"{base_url}/rankings/drivers?season={season}", headers=headers)
        grid_res, standings_res = await asyncio.gather(grid_task, standings_task)
        
        grid_data = grid_res.json().get("response", [])
        standings_data = standings_res.json().get("response", [])

    if not grid_data:
        return [TipInfo(market="Análise Indisponível", suggestion="Aguardar", justification="Grid de largada ainda não definido.", confidence=0)]

    # Dica 1: Pole Position
    pole_sitter = next((item for item in grid_data if item.get("position") == 1), None)
    if pole_sitter:
        driver_name = pole_sitter.get("driver", {}).get("name", "Pole Sitter")
        tips.append(TipInfo(market="Vencedor da Corrida", suggestion=f"Vitória de {driver_name}", justification="Larga na Pole Position, a posição mais vantajosa do grid.", confidence=75))

    # Dica 2: Líder do Campeonato no Pódio
    if standings_data:
        championship_leader = next((item for item in standings_data if item.get("position") == 1), None)
        if championship_leader:
            leader_name = championship_leader.get("driver", {}).get("name", "Líder do Campeonato")
            # Evita dica duplicada se o pole for o líder
            if not any(tip.suggestion.endswith(leader_name) for tip in tips):
                tips.append(TipInfo(market="Resultado Final", suggestion=f"{leader_name} no pódio (Top 3)", justification="Líder do campeonato, com alta consistência de resultados.", confidence=70))

    if not tips:
        tips.append(TipInfo(market="Análise Conclusiva", suggestion="Aguardar", justification="Dados insuficientes para uma análise clara.", confidence=0))
        
    return tips

# --- ENDPOINTS DE ANÁLISE PRINCIPAIS (ROTEADOR ATUALIZADO) ---
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int, sport: str):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not config or not api_key: raise HTTPException(status_code=404, detail="Esporte não encontrado ou API Key ausente")
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}

    team_sports = ['nba', 'nfl', 'baseball', 'hockey', 'rugby', 'handball', 'volleyball', 'basketball']

    if sport == "football":
        return await analyze_football_pre_game(game_id, headers)
    elif sport in team_sports:
        return await analyze_team_sport_h2h(game_id, sport, headers)
    elif sport == "formula-1":
        return await analyze_f1_pre_race(game_id, headers)
    
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification=f"Análise detalhada para {sport.capitalize()} ainda não foi implementada.", confidence=0)]

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int, sport: str):
    # ... (lógica de análise ao vivo, omitida para brevidade)
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification=f"Análise ao vivo para {sport.capitalize()} ainda não foi implementada.", confidence=0)]
