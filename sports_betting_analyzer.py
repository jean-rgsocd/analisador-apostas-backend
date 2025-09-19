# sport_betting_analyzer.py
# Versão Final Integrada - Multi-Esportivo com Perfil Detalhado de Tipster

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import asyncio
import httpx
import os

# ==========================
# Configurações de API Keys
# ==========================
API_KEYS = {
    "football": os.getenv("FOOTBALL_API_KEY"),
    "basketball": os.getenv("BASKETBALL_API_KEY"),
    "nba": os.getenv("NBA_API_KEY"),
    "baseball": os.getenv("BASEBALL_API_KEY"),
    "formula1": os.getenv("F1_API_KEY"),
    "handball": os.getenv("HANDBALL_API_KEY"),
    "hockey": os.getenv("HOCKEY_API_KEY"),
    "mma": os.getenv("MMA_API_KEY"),
    "american_football": os.getenv("AF_API_KEY"),
    "rugby": os.getenv("RUGBY_API_KEY"),
    "volleyball": os.getenv("VOLLEY_API_KEY"),
}

BASE_URLS = {
    "football": "https://v3.football.api-sports.io/",
    "basketball": "https://v1.basketball.api-sports.io/",
    "nba": "https://v2.nba.api-sports.io/",
    "baseball": "https://v1.baseball.api-sports.io/",
    "formula1": "https://v1.formula-1.api-sports.io/",
    "handball": "https://v1.handball.api-sports.io/",
    "hockey": "https://v1.hockey.api-sports.io/",
    "mma": "https://v1.mma.api-sports.io/",
    "american_football": "https://v1.american-football.api-sports.io/",
    "rugby": "https://v1.rugby.api-sports.io/",
    "volleyball": "https://v1.volleyball.api-sports.io/",
}

SPORTS = list(API_KEYS.keys())

# ==========================
# FastAPI App
# ==========================
app = FastAPI(title="Sports Betting Analyzer")

# ==========================
# API Client para os Esportes
# ==========================
class APISportsClient:
    def __init__(self, sport: str):
        self.sport = sport.lower()
        self.base_url = BASE_URLS[self.sport]
        self.api_key = API_KEYS[self.sport]
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.base_url.split("//")[1].rstrip("/"),
        }

    async def get_fixtures(self, league_id: int = None, season: int = None):
        url = f"{self.base_url}fixtures"
        params = {}
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_h2h(self, team1_id: int, team2_id: int):
        url = f"{self.base_url}fixtures/headtohead"
        params = {"h2h": f"{team1_id}-{team2_id}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()
# ==========================
# Modelos Pydantic
# ==========================
class TipsterOutput(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    start_time: datetime
    h2h_raw: List[Dict]
    predicted_pick: str = None
    confidence: float = 0.0
    tipster_profile: Dict = {}

# ==========================
# Funções utilitárias
# ==========================
def _is_number_str(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def evaluate_live_triggers(lhs, operator, rhs):
    """
    Avalia condições >, <, >=, <=, ==, normalizando strings numéricas
    """
    if _is_number_str(lhs):
        lhs = float(lhs)
    if _is_number_str(rhs):
        rhs = float(rhs)
    if operator == ">":
        return lhs > rhs
    if operator == "<":
        return lhs < rhs
    if operator == ">=":
        return lhs >= rhs
    if operator == "<=":
        return lhs <= rhs
    if operator == "==":
        return lhs == rhs
    return False

def parse_h2h(h2h_raw, sport):
    """
    Normaliza H2H para múltiplos esportes
    """
    normalized = []
    for match in h2h_raw:
        home_score = None
        away_score = None

        # Football / Basketball
        if "score" in match:
            home_score = match["score"].get("home")
            away_score = match["score"].get("away")
        # Baseball
        elif "runs_home" in match and "runs_away" in match:
            home_score = match["runs_home"]
            away_score = match["runs_away"]
        # Nested generic
        elif "home" in match and "score" in match["home"]:
            home_score = match["home"]["score"]
            away_score = match["away"]["score"]

        normalized.append({
            "home_score": home_score,
            "away_score": away_score,
            "winner": match.get("winner")
        })
    return normalized

# ==========================
# Perfil completo do Tipster por esporte
# ==========================
SPORT_TIPSTER_PROFILE = {
    "football": {
        "aggressiveness": 0.7,
        "value_bets_focus": True,
        "historical_hit_rate": 0.65,
        "roi": 0.12
    },
    "basketball": {
        "aggressiveness": 0.6,
        "value_bets_focus": True,
        "historical_hit_rate": 0.62,
        "roi": 0.10
    },
    "nba": {
        "aggressiveness": 0.6,
        "value_bets_focus": True,
        "historical_hit_rate": 0.63,
        "roi": 0.11
    },
    "baseball": {
        "aggressiveness": 0.5,
        "value_bets_focus": True,
        "historical_hit_rate": 0.60,
        "roi": 0.09
    },
    "formula1": {
        "aggressiveness": 0.8,
        "value_bets_focus": False,
        "historical_hit_rate": 0.58,
        "roi": 0.15
    },
    "handball": {
        "aggressiveness": 0.5,
        "value_bets_focus": True,
        "historical_hit_rate": 0.61,
        "roi": 0.08
    },
    "hockey": {
        "aggressiveness": 0.5,
        "value_bets_focus": True,
        "historical_hit_rate": 0.59,
        "roi": 0.09
    },
    "mma": {
        "aggressiveness": 0.9,
        "value_bets_focus": False,
        "historical_hit_rate": 0.55,
        "roi": 0.20
    },
    "american_football": {
        "aggressiveness": 0.6,
        "value_bets_focus": True,
        "historical_hit_rate": 0.63,
        "roi": 0.10
    },
    "rugby": {
        "aggressiveness": 0.6,
        "value_bets_focus": True,
        "historical_hit_rate": 0.61,
        "roi": 0.09
    },
    "volleyball": {
        "aggressiveness": 0.5,
        "value_bets_focus": True,
        "historical_hit_rate": 0.60,
        "roi": 0.08
    }
}

# ==========================
# Função generate_picks
# ==========================
def generate_picks(match_data: Dict, sport: str) -> Dict:
    """
    Gera pick, confidence e perfil detalhado do tipster baseado no esporte e H2H
    """
    pick = "draw"
    confidence = 0.5

    h2h_normalized = parse_h2h(match_data.get("h2h_raw", []), sport)
    home_score_sum = sum([m["home_score"] for m in h2h_normalized if m["home_score"] is not None])
    away_score_sum = sum([m["away_score"] for m in h2h_normalized if m["away_score"] is not None])

    if sport in ["football", "basketball", "nba", "american_football", "rugby", "handball", "volleyball"]:
        if home_score_sum > away_score_sum:
            pick = "home"
            confidence = 0.7
        elif away_score_sum > home_score_sum:
            pick = "away"
            confidence = 0.7
    elif sport == "mma":
        home_wins = match_data.get("home_recent_wins", 0)
        away_wins = match_data.get("away_recent_wins", 0)
        if home_wins > away_wins:
            pick = "home"
            confidence = 0.8
        elif away_wins > home_wins:
            pick = "away"
            confidence = 0.8
    elif sport == "formula1":
        pick = "favorite"  # placeholder, Fórmula 1 depende de odds / piloto
        confidence = 0.6

    # Adiciona perfil detalhado do tipster
    tipster_profile = SPORT_TIPSTER_PROFILE.get(sport, {})

    return {"predicted_pick": pick, "confidence": confidence, "tipster_profile": tipster_profile}
# ==========================
# Função principal para gerar TipsterOutput
# ==========================
async def build_tipster_output(sport: str, league_id: int = None, season: int = None):
    client = APISportsClient(sport)
    fixtures = await client.get_fixtures(league_id, season)
    tipster_output = []

    for match in fixtures.get("response", []):
        home_team_id = match["teams"]["home"]["id"]
        away_team_id = match["teams"]["away"]["id"]

        # Pega H2H do time
        h2h = await client.get_h2h(home_team_id, away_team_id)

        tip = TipsterOutput(
            match_id=match["fixture"]["id"],
            home_team=match["teams"]["home"]["name"],
            away_team=match["teams"]["away"]["name"],
            start_time=match["fixture"]["date"],
            h2h_raw=h2h.get("response", [])
        )

        # Gera pick + confidence + perfil detalhado do tipster
        pick_info = generate_picks(tip.dict(), sport)
        tip.predicted_pick = pick_info["predicted_pick"]
        tip.confidence = pick_info["confidence"]
        tip.tipster_profile = pick_info["tipster_profile"]

        # Log de auditoria
        print(f"[AUDIT] {tip.match_id} | {tip.home_team} vs {tip.away_team} | "
              f"Pick: {tip.predicted_pick} | Confidence: {tip.confidence} | "
              f"Profile: {tip.tipster_profile}")

        tipster_output.append(tip)

    return tipster_output

# ==========================
# FastAPI Endpoints
# ==========================
@app.get("/api/{sport}/fixtures", response_model=List[TipsterOutput])
async def api_fixtures(sport: str, league_id: int = None, season: int = None):
    if sport not in SPORTS:
        raise HTTPException(status_code=400, detail="Sport not supported")
    return await build_tipster_output(sport, league_id, season)

@app.get("/api/{sport}/h2h")
async def api_h2h(sport: str, team1_id: int, team2_id: int):
    if sport not in SPORTS:
        raise HTTPException(status_code=400, detail="Sport not supported")
    client = APISportsClient(sport)
    data = await client.get_h2h(team1_id, team2_id)
    return {"sport": sport, "h2h": data}
