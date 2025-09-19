# Filename: sports_betting_analyzer.py
# Versão 6.0 - Multi-Esportivo com Ligas Dinâmicas

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer Multi-Esportivo", version="6.0")

# Configuração CORS (permite frontend chamar o backend)
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# MODELO DE DADOS
# ============================
class GameInfo(BaseModel):
    home: str
    away: str
    time: str

# ============================
# MAPA DE ESPORTES E ENDPOINTS
# ============================
SPORTS_MAP = {
    "football": {"endpoint_games": "/fixtures", "endpoint_leagues": "/leagues", "host": "v3.football.api-sports.io"},
    "basketball": {"endpoint_games": "/games", "endpoint_leagues": "/leagues", "host": "v1.basketball.api-sports.io"},
    "nfl": {"endpoint_games": "/games", "endpoint_leagues": "/leagues", "host": "v1.american-football.api-sports.io"},
    "nba": {"endpoint_games": "/games", "endpoint_leagues": "/leagues", "host": "v2.nba.api-sports.io"},
    "baseball": {"endpoint_games": "/games", "endpoint_leagues": "/leagues", "host": "v1.baseball.api-sports.io"},
    "formula-1": {"endpoint_games": "/races", "endpoint_leagues": "/races", "host": "v1.formula-1.api-sports.io"},
    "handball": {"endpoint_games": "/games", "endpoint_leagues": "/leagues", "host": "v1.handball.api-sports.io"},
    "hockey": {"endpoint_games": "/games", "endpoint_leagues": "/leagues", "host": "v1.hockey.api-sports.io"},
    "mma": {"endpoint_games": "/fights", "endpoint_leagues": "/leagues", "host": "v1.mma.api-sports.io"},
    "rugby": {"endpoint_games": "/games", "endpoint_leagues": "/leagues", "host": "v1.rugby.api-sports.io"},
    "volleyball": {"endpoint_games": "/games", "endpoint_leagues": "/leagues", "host": "v1.volleyball.api-sports.io"},
}


# ============================
# FUNÇÃO: BUSCAR LIGAS
# ============================
@app.get("/ligas", response_model=List[str])
def get_leagues_endpoint(sport: str = "football"):
    sport = sport.lower()
    api_key = os.getenv("API_KEY")
    if not api_key:
        return ["Chave da API não configurada."]

    if sport not in SPORTS_MAP:
        return ["Esporte inválido ou não suportado."]

    try:
        config = SPORTS_MAP[sport]
        url = f"https://{config['host']}{config['endpoint_leagues']}"
        headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        leagues = []
        for item in data.get("response", []):
            if sport == "formula-1":
                leagues.append(item.get("competition", {}).get("name"))
            elif sport == "mma":
                leagues.append(item.get("league", {}).get("name"))
            else:
                leagues.append(item.get("league", {}).get("name"))

        return list(set(filter(None, leagues)))  # remove duplicados/None

    except Exception as e:
        print(f"Erro ao buscar ligas do esporte {sport}: {e}")
        return ["Falha ao buscar ligas."]


# ============================
# FUNÇÃO: BUSCAR JOGOS DO DIA
# ============================
def get_daily_games_from_api(sport: str, league: Optional[str] = None) -> Dict[str, List[GameInfo]]:
    games_by_league = {}
    api_key = os.getenv("API_KEY")
    if not api_key:
        return {"Erro": [GameInfo(home="Chave da API não configurada no servidor.", away="", time="")]}

    if sport not in SPORTS_MAP:
        return {"Erro": [GameInfo(home="Esporte inválido ou não suportado.", away="", time="")]}

    try:
        config = SPORTS_MAP[sport]
        base_url = f"https://{config['host']}{config['endpoint_games']}"
        today = datetime.now().strftime("%Y-%m-%d")

        # Query dinâmica
        if sport == "formula-1":
            querystring = {"season": datetime.now().strftime("%Y"), "type": "Race", "next": "10"}
        else:
            querystring = {"date": today}

        # Filtro por liga, se fornecido
        if league:
            querystring["league"] = league

        headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
        response = requests.get(base_url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("results", 0) == 0:
            return {"Info": [GameInfo(home=f"Nenhum evento de {sport} encontrado.", away="", time="")]}

        for item in data.get("response", []):
            league_name = "Outros"
            home_team, away_team, timestamp = "N/A", "N/A", None

            if sport == 'football':
                league_name = item.get("league", {}).get("name", "Outros")
                home_team = item.get("teams", {}).get("home", {}).get("name")
                away_team = item.get("teams", {}).get("away", {}).get("name")
                timestamp = item.get("fixture", {}).get("timestamp")
            elif sport in ['basketball', 'nba', 'nfl', 'baseball', 'handball', 'hockey', 'rugby', 'volleyball']:
                league_name = item.get("league", {}).get("name", "Outros")
                home_team = item.get("teams", {}).get("home", {}).get("name")
                away_team = item.get("teams", {}).get("away", {}).get("name")
                timestamp = item.get("timestamp")
            elif sport == 'formula-1':
                league_name = item.get("competition", {}).get("name", "Fórmula 1")
                home_team = item.get("circuit", {}).get("name")
                away_team = f"({item.get('type', 'Race')})"
                timestamp = item.get("timestamp")
            elif sport == 'mma':
                league_name = item.get("league", {}).get("name", "MMA Event")
                fights = item.get("fights", [])
                if fights:
                    home_team = fights[0].get("fighters", {}).get("home", {}).get("name")
                    away_team = fights[0].get("fighters", {}).get("away", {}).get("name")
                timestamp = item.get("timestamp")

            if not home_team or not away_team:
                continue

            game_time = (
                datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M')
                if sport == 'formula-1'
                else datetime.fromtimestamp(timestamp).strftime('%H:%M')
                if timestamp else "N/A"
            )

            if league_name not in games_by_league:
                games_by_league[league_name] = []

            games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time))

        return games_by_league

    except Exception as e:
        print(f"Erro na API para o esporte {sport}: {e}")
        return {"Erro": [GameInfo(home="Falha ao buscar dados da API.", away="", time="")]}


# ============================
# ENDPOINT: JOGOS DO DIA
# ============================
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint(sport: str = "football", league: Optional[str] = None):
    return get_daily_games_from_api(sport.lower(), league)
