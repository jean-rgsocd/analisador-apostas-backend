# Filename: sports_betting_analyzer.py
# Versão 31.0 - Lógica de análise robusta ("Sempre Dê uma Resposta")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from datetime import datetime, timedelta
import asyncio
from collections import Counter

app = FastAPI(title="Sports Betting Analyzer - Full Intelligence", version="31.0")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GameInfo(BaseModel): home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel): market: str; suggestion: str; justification: str; confidence: int

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
        response = await client.get(url, headers=headers, params=querystring, timeout=45)
        response.raise_for_status()
        data = response.json()
        if not data.get("response"): return []
        if data.get("errors") and (isinstance(data["errors"], list) and len(data["errors"]) > 0 or isinstance(data["errors"], dict) and len(data["errors"].keys()) > 0): return []
        return data.get("response", [])
    except httpx.RequestError: return []

# ... (Endpoints de busca /paises, /ligas, /jogos-por-esporte sem alterações) ...

# --- LÓGICA DE ANÁLISE DETALHADA ---

def _get_winner_id_from_game(game: Dict) -> Optional[int]:
    """Função auxiliar para encontrar o ID do vencedor em diferentes estruturas de API."""
    if game.get("teams", {}).get("home", {}).get("winner") is True:
        return game.get("teams", {}).get("home", {}).get("id")
    if game.get("teams", {}).get("away", {}).get("winner") is True:
        return game.get("teams", {}).get("away", {}).get("id")

    home_score = game.get("scores", {}).get("home", 0)
    away_score = game.get("scores", {}).get("away", 0)
    
    # Adaptação para diferentes nomes de pontuação
    if home_score is None or away_score is None:
        home_score = game.get("scores", {}).get("home", {}).get("points", 0) or 0
        away_score = game.get("scores", {}).get("away", {}).get("points", 0) or 0

    if home_score > away_score:
        return game.get("teams", {}).get("home", {}).get("id")
    if away_score > home_score:
        return game.get("teams", {}).get("away", {}).get("id")
        
    return None

async def analyze_team_sport_detailed(game_id: int, sport: str, headers: dict) -> List[TipInfo]:
    tips = []
    config = SPORTS_MAP.get(sport)
    if not config: return []
    base_url = f"https://{config['host']}"
    
    async with httpx.AsyncClient() as client:
        game_res = await client.get(f"{base_url}/games?id={game_id}", headers=headers)
        game_data = game_res.json().get("response", [])
    if not game_data: return [TipInfo(market="Erro", suggestion="Dados do jogo não encontrados.", justification="", confidence=0)]

    game = game_data[0]
    home_team_id = game.get("teams", {}).get("home", {}).get("id")
    away_team_id = game.get("teams", {}).get("away", {}).get("id")
    home_team_name = game.get("teams", {}).get("home", {}).get("name", "Time da Casa")
    away_team_name = game.get("teams", {}).get("away", {}).get("name", "Visitante")

    # Camada 1: Análise de H2H
    async with httpx.AsyncClient() as client:
        h2h_data = await fetch_api_data_async(client, {"h2h": f"{home_team_id}-{away_team_id}"}, headers, f"{base_url}/games")
    
    if h2h_data:
        winner_ids = [_get_winner_id_from_game(g) for g in h2h_data]
        win_counts = Counter(winner_ids)
        home_wins, away_wins = win_counts.get(home_team_id, 0), win_counts.get(away_team_id, 0)

        if home_wins > away_wins:
            confidence = 50 + int((home_wins / len(h2h_data)) * 25)
            tips.append(TipInfo(market="Vencedor (H2H)", suggestion=f"Vitória do {home_team_name}", justification=f"Leva vantagem no confronto direto com {home_wins} vitórias contra {away_wins} nos últimos jogos.", confidence=confidence))
            return tips
        elif away_wins > home_wins:
            confidence = 50 + int((away_wins / len(h2h_data)) * 25)
            tips.append(TipInfo(market="Vencedor (H2H)", suggestion=f"Vitória do {away_team_name}", justification=f"Leva vantagem no confronto direto com {away_wins} vitórias contra {home_wins} nos últimos jogos.", confidence=confidence))
            return tips

    # Camada 2: Análise de Momento (Forma Recente)
    async with httpx.AsyncClient() as client:
        home_form_task = client.get(f"{base_url}/games?team={home_team_id}&last=10", headers=headers)
        away_form_task = client.get(f"{base_url}/games?team={away_team_id}&last=10", headers=headers)
        home_res, away_res = await asyncio.gather(home_form_task, away_form_task)
        home_form_data, away_form_data = home_res.json().get("response", []), away_res.json().get("response", [])
    
    if home_form_data and away_form_data:
        home_form_wins = sum(1 for g in home_form_data if _get_winner_id_from_game(g) == home_team_id)
        away_form_wins = sum(1 for g in away_form_data if _get_winner_id_from_game(g) == away_team_id)

        if home_form_wins > away_form_wins:
            confidence = 50 + (home_form_wins - away_form_wins) * 3
            tips.append(TipInfo(market="Vencedor (Forma)", suggestion=f"Vitória do {home_team_name}", justification=f"Time em melhor momento, com {home_form_wins} vitórias nos últimos 10 jogos (contra {away_form_wins} do adversário).", confidence=confidence))
            return tips
        elif away_form_wins > home_form_wins:
            confidence = 50 + (away_form_wins - home_form_wins) * 3
            tips.append(TipInfo(market="Vencedor (Forma)", suggestion=f"Vitória do {away_team_name}", justification=f"Time em melhor momento, com {away_form_wins} vitórias nos últimos 10 jogos (contra {home_form_wins} do adversário).", confidence=confidence))
            return tips
            
    # Camada 3: Fallback final
    tips.append(TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Nenhum favoritismo claro encontrado nas estatísticas de H2H ou Forma Recente.", confidence=0))
    return tips

# ... (outras funções de análise para F1, MMA, Futebol que já estão no seu código) ...

# --- ENDPOINTS DE ANÁLISE PRINCIPAIS (ROTEADOR) ---
@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
async def analyze_pre_game_endpoint(game_id: int, sport: str):
    api_key = os.getenv("API_KEY"); config = SPORTS_MAP.get(sport)
    if not config or not api_key: raise HTTPException(status_code=404, detail="Esporte não encontrado ou API Key ausente")
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}

    team_sports = ['nba', 'nfl', 'baseball', 'hockey', 'rugby', 'handball', 'volleyball', 'basketball']

    if sport == "football":
        # return await analyze_football_pre_game(game_id, headers)
        return await analyze_team_sport_detailed(game_id, sport, headers) # Usando a nova lógica para tudo
    elif sport in team_sports:
        return await analyze_team_sport_detailed(game_id, sport, headers)
    # elif sport == "formula-1": ...
    # elif sport == "mma": ...
    
    return [TipInfo(market="Análise Padrão", suggestion="Não disponível", justification=f"Análise detalhada para {sport.capitalize()} ainda não foi implementada.", confidence=0)]

# ... (endpoint /analisar-ao-vivo sem alterações) ...
