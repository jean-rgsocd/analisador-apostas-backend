# Filename: sports_betting_analyzer.py
# Versão 20.0 - Versão Definitiva com Análise Inteligente para Futebol e NBA

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import asyncio
from collections import Counter

app = FastAPI(title="Sports Betting Analyzer - Multi-Sport Final", version="20.0")
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

@app.get("/jogos")
async def get_games_by_filter(sport: str, league_id: int):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not api_key or not config: raise HTTPException(status_code=400, detail="Esporte inválido")
    today = datetime.now(); dates_to_fetch = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
    url_endpoint = "/games"
    if sport == 'football': url_endpoint = "/fixtures"
    elif sport == 'formula-1': url_endpoint = "/races"
    url = f"https://{config['host']}{url_endpoint}"; headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    async with httpx.AsyncClient() as client:
        tasks = []
        for date_str in dates_to_fetch:
            querystring = {"league": str(league_id), "season": str(datetime.now().year)}
            if sport != 'formula-1': querystring["date"] = date_str
            if sport == 'formula-1' and len(tasks) > 0: continue
            tasks.append(fetch_api_data_async(client, querystring, headers, url))
        results = await asyncio.gather(*tasks)
    all_fixtures = [fixture for result in results for fixture in result]; all_fixtures.sort(key=lambda x: x.get('fixture', x).get('timestamp', x.get('date', 0)))
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

# --- LÓGICA DE ANÁLISE DETALHADA ---

def find_stat(stat_list: List[Dict], stat_name: str) -> int:
    for stat in stat_list:
        if stat.get('type') == stat_name:
            value = stat.get('value')
            if value is not None:
                try: return int(str(value).replace('%', '').strip())
                except (ValueError, TypeError): return 0
    return 0
    
async def analyze_football_pre_game(game_id: int, headers: dict) -> List[TipInfo]:
    tips = []
    base_url = "https://v3.football.api-sports.io"
    async with httpx.AsyncClient() as client:
        tasks = { "odds": client.get(f"{base_url}/odds?fixture={game_id}", headers=headers), "fixture": client.get(f"{base_url}/fixtures?id={game_id}", headers=headers) }
        responses = await asyncio.gather(*tasks.values())
        odds_data, fixture_data = responses[0].json().get("response", []), responses[1].json().get("response", [])
    
    if not fixture_data: return [TipInfo(market="Erro", suggestion="Não foi possível obter dados do jogo.", justification="", confidence=0)]
    home_team_name = fixture_data[0].get("teams", {}).get("home", {}).get("name", "Time da Casa")

    if odds_data and odds_data[0].get("bookmakers"):
        bet_values = odds_data[0].get("bookmakers", [{}])[0].get("bets", [{}])[0].get("values", [])
        home_odd = next((float(v.get("odd", 100)) for v in bet_values if v.get("value") == "Home"), 100)
        if 1.01 < home_odd < 1.65:
            confidence = int(100 - (home_odd - 1) * 100)
            tips.append(TipInfo(market="Vencedor da Partida", suggestion=f"Vitória do {home_team_name}", justification=f"Odds de {home_odd:.2f} indicam forte favoritismo.", confidence=confidence))

    if not tips: tips.append(TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados pré-jogo não apontam um favoritismo claro.", confidence=0))
    return tips

async def analyze_football_live_game(game_id: int, headers: dict) -> List[TipInfo]:
    tips = []
    base_url = "https://v3.football.api-sports.io"
    async with httpx.AsyncClient() as client:
        tasks = { "fixture": client.get(f"{base_url}/fixtures?id={game_id}", headers=headers), "stats": client.get(f"{base_url}/fixtures/statistics?fixture={game_id}", headers=headers) }
        responses = await asyncio.gather(*tasks.values())
        fixture_data, stats_data = responses[0].json().get("response", []), responses[1].json().get("response", [])
        
    if not fixture_data or len(stats_data) < 2: return [TipInfo(market="Análise Ao Vivo", suggestion="Aguardar", justification="Estatísticas ao vivo ainda não disponíveis.", confidence=0)]
    
    fixture = fixture_data[0]
    elapsed = fixture.get("fixture", {}).get("status", {}).get("elapsed", 0)
    home_goals, away_goals = fixture.get("goals", {}).get("home", 0), fixture.get("goals", {}).get("away", 0)
    home_stats, away_stats = stats_data[0].get('statistics', []), stats_data[1].get('statistics', [])
    home_sot, away_sot = find_stat(home_stats, 'Shots on Goal'), find_stat(away_stats, 'Shots on Goal')
    total_sot = home_sot + away_sot
    
    if elapsed > 25 and total_sot > 5 and (home_goals + away_goals < 3):
        tips.append(TipInfo(market="Gols Ao Vivo", suggestion=f"Mais de {home_goals + away_goals + 0.5} Gols", justification=f"Jogo aberto com {total_sot} chutes a gol.", confidence=70))
    
    if not tips: tips.append(TipInfo(market="Análise Ao Vivo", suggestion="Aguardar", justification="Jogo sem oportunidades claras no momento.", confidence=0))
    return tips

async def analyze_nba_pre_game(game_id: int, headers: dict) -> List[TipInfo]:
    tips = []
    base_url = "https://v2.nba.api-sports.io"
    async with httpx.AsyncClient() as client:
        game_task = client.get(f"{base_url}/games?id={game_id}", headers=headers)
        game_res = await game_task
        game_data = game_res.json().get("response", [])

    if not game_data:
        return [TipInfo(market="Erro", suggestion="Dados do jogo não encontrados.", justification="Não foi possível obter informações para este jogo da NBA.", confidence=0)]

    game = game_data[0]
    home_team_id, away_team_id = game.get("teams", {}).get("home", {}).get("id"), game.get("teams", {}).get("away", {}).get("id")
    home_team_name, away_team_name = game.get("teams", {}).get("home", {}).get("name", "Time da Casa"), game.get("teams", {}).get("away", {}).get("name", "Time Visitante")

    async with httpx.AsyncClient() as client:
        h2h_data = await fetch_api_data_async(client, {"h2h": f"{home_team_id}-{away_team_id}"}, headers, f"{base_url}/games")
    
    if h2h_data:
        winner_ids = [g.get("teams", {}).get("home" if g.get("scores", {}).get("home", {}).get("points", 0) > g.get("scores", {}).get("away", {}).get("points", 0) else "away").get("id") for g in h2h_data]
        win_counts = Counter(winner_ids)
        home_wins, away_wins = win_counts.get(home_team_id, 0), win_counts.get(away_team_id, 0)
        
        if home_wins > away_wins and home_wins / len(h2h_data) >= 0.7:
            tips.append(TipInfo(market="Vencedor (H2H)", suggestion=f"Vitória do {home_team_name}", justification=f"Venceu {home_wins} dos últimos {len(h2h_data)} confrontos diretos.", confidence=75))
        elif away_wins > home_wins and away_wins / len(h2h_data) >= 0.7:
            tips.append(TipInfo(market="Vencedor (H2H)", suggestion=f"Vitória do {away_team_name}", justification=f"Venceu {away_wins} dos últimos {len(h2h_data)} confrontos diretos.", confidence=75))

    if not tips:
        tips.append(TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados pré-jogo não apontam uma vantagem clara.", confidence=0))
    return tips

# --- ENDPOINTS DE ANÁLISE PRINCIPAIS ---
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int, sport: str):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not config or not api_key: raise HTTPException(status_code=404, detail="Esporte não encontrado ou API Key ausente")
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}

    if sport == "football":
        return await analyze_football_pre_game(game_id, headers)
    elif sport == "nba":
        return await analyze_nba_pre_game(game_id, headers)
    
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification=f"Análise detalhada para {sport.capitalize()} ainda não foi implementada.", confidence=0)]

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
async def analyze_live_game_endpoint(game_id: int, sport: str):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not config or not api_key: raise HTTPException(status_code=404, detail="Esporte não encontrado ou API Key ausente")
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    
    if sport == "football":
        return await analyze_football_live_game(game_id, headers)
        
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification=f"Análise ao vivo para {sport.capitalize()} ainda não foi implementada.", confidence=0)]
