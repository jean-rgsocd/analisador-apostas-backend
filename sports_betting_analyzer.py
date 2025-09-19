# Filename: sports_analyzer_live.py
# Versão 2.0 - Multi-Esportivo Ao Vivo com Tipster IA

import os
import requests
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from typing import Dict, List, Optional

# ================================
# Inicialização do FastAPI
# ================================
app = FastAPI(title="Tipster Ao Vivo - Multi Esportes")

# ================================
# Configuração da API Key
# ================================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("API_KEY não definida no ambiente!")

HEADERS = {'x-rapidapi-key': API_KEY}

# ================================
# Mapas de esportes e URLs base
# ================================
SPORTS_MAP = {
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
    "afl": "https://v1.afl.api-sports.io/"
}

# ================================
# Inicialização do TIPSTER_PROFILE
# ================================
TIPSTER_PROFILE = {
    "total_predictions": 0,
    "correct_predictions": 0,
    "wrong_predictions": 0,
    "last_predictions": []
}

# ================================
# Perfil detalhado do Tipster
# ================================
TIPSTER_PROFILES_DETAILED = {
    "football": {
        "indicators": [
            "Last 5 home/away matches for each team",
            "Last 5 head-to-head encounters",
            "Average goals scored/conceded (last 5 matches)",
            "Average corners (last 5 matches)",
            "Average cards (last 5 matches)",
            "Shots on target — total and 1st half (last 5 matches)",
            "Average xG (if available)",
            "Key formations/injuries and pre-match odds"
        ],
        "pre_game": [
            "Recent form, home advantage, xG vs actual goals, historical over/under, odds movement"
        ],
        "in_play_triggers": [
            "Possession >65% over last 15', 2+ shots on target within <10', accumulated fouls >X → card bet"
        ],
        "typical_picks": [
            "Home/Away win",
            "Over 1.5/2.5 goals (1st half or full match)",
            "Over corners",
            "Over cards",
            "Both teams to score (BTTS)"
        ],
        "required_data": [
            "Match results",
            "Match events (corners, cards, shots)",
            "xG if possible"
        ]
    },
    "basketball": {
        "indicators": [
            "Last 5 matches per team (including +/- per player)",
            "Points per quarter (last 5 matches average)",
            "Shooting percentages (FG%, 3P%, FT%)",
            "Rebounds (offensive/defensive), assists, turnovers",
            "Pace (possessions per game) and offensive/defensive efficiency",
            "Key player injuries (minutes impact)"
        ],
        "pre_game": [
            "Defense vs offense matchup, bench advantage, back-to-back, travel"
        ],
        "in_play_triggers": [
            "Pace variations, starter fouls, scoring runs (>10 points)"
        ],
        "typical_picks": [
            "Moneyline win",
            "Over/Under total points",
            "Handicap (spread)",
            "Player points over",
            "Quarter totals (1st Q Over)"
        ],
        "required_data": [
            "Boxscore per game",
            "Play-by-play for live triggers"
        ]
    },
    "nba": {
        "indicators": [
            "Last 5 matches per team (including +/- per player)",
            "Points per quarter",
            "Shooting percentages",
            "Rebounds, assists, turnovers",
            "Pace and offensive/defensive efficiency",
            "Key player injuries"
        ],
        "pre_game": [
            "Defense vs offense matchup, bench advantage, back-to-back, travel"
        ],
        "in_play_triggers": [
            "Pace variation, starter fouls, scoring runs (>10 points)"
        ],
        "typical_picks": [
            "Moneyline win",
            "Over/Under total points",
            "Handicap (spread)"
        ],
        "required_data": [
            "Boxscore per game",
            "Play-by-play for live triggers"
        ]
    },
    "american_football": {
        "indicators": [
            "Last 5 matches (including performance per quarter)",
            "Yards allowed/earned per game (total and pass/run)",
            "Turnovers (last 5 games)",
            "Red zone efficiency, 3rd down conversion",
            "Key QB/skill position injuries"
        ],
        "pre_game": [
            "Offense/defense matchup, weather (outdoor), injuries, estimated possession time"
        ],
        "in_play_triggers": [
            "3rd down failures, sacks, turnover momentum"
        ],
        "typical_picks": [
            "Moneyline",
            "Spread",
            "Over/Under total points",
            "Props (QB yards, TDs)"
        ],
        "required_data": [
            "Drive charts",
            "Play-by-play",
            "Advanced stats (DVOA if available)"
        ]
    },
    "baseball": {
        "indicators": [
            "Last 5 matches (including starting pitcher stats)",
            "Starting pitcher ERA, WHIP, K/BB, FIP",
            "Batter OPS/wOBA",
            "Win probability via simulator (Elo/xStat)",
            "Injuries/closer status"
        ],
        "pre_game": [
            "Pitcher vs lineup matchup (platoon splits L/R), weather/wind"
        ],
        "in_play_triggers": [
            "Pitcher performance per inning, bullpen usage"
        ],
        "typical_picks": [
            "Moneyline",
            "Over/Under runs",
            "Run line (handicap)",
            "Props (total hits/RBI per player)"
        ],
        "required_data": [
            "Boxscore",
            "Pitching lines",
            "Splits L/R"
        ]
    },
    "formula1": {
        "indicators": [
            "Qualifying and race performance last 5 races",
            "Average laps in Top-10 per session",
            "Average lap time, tire degradation, pit strategy",
            "Weather forecast"
        ],
        "pre_game": [
            "Qualifying, setup, circuit history"
        ],
        "in_play_triggers": [
            "Safety car probability, pace after pit, tire wear"
        ],
        "typical_picks": [
            "Podium (top-3) / win",
            "Top-6/Top-10",
            "Fastest lap",
            "Winning strategy (number of pit stops)"
        ],
        "required_data": [
            "Basic telemetry",
            "Sector times",
            "Tire status"
        ]
    },
    "handball": {
        "indicators": [
            "Last 5 matches; average goals scored/conceded",
            "Shooting efficiency (%)",
            "Goalkeeper save %",
            "Turnovers and power-play advantage (2 min)"
        ],
        "pre_game": [
            "Game pace, goalkeeper rotation, fitness"
        ],
        "in_play_triggers": [
            "Goal sequences, numerical advantages"
        ],
        "typical_picks": [
            "Win",
            "Over total goals",
            "Handicap",
            "Over 1st half goals"
        ],
        "required_data": [
            "Stats by period",
            "Goalkeeper efficiency"
        ]
    },
    "hockey": {
        "indicators": [
            "Last 5 matches; average goals",
            "Shots on goal (SOG) per game",
            "Goalie save %, PDO",
            "Powerplay/penalty kill %",
            "Faceoff % (if applicable)"
        ],
        "pre_game": [
            "Projected goalie, special teams"
        ],
        "in_play_triggers": [
            "SOG per 20', goalie stamina/shot volume"
        ],
        "typical_picks": [
            "Moneyline",
            "Over/Under goals",
            "Puck line (handicap)",
            "Over powerplay chances"
        ],
        "required_data": [
            "Boxscore",
            "SOG",
            "PK/PP stats"
        ]
    },
    "mma": {
        "indicators": [
            "Last 5 fights per fighter (stoppages vs decisions)",
            "Strikes per minute, takedown accuracy/defense, control time",
            "Reach, age, layoff time",
            "Injuries and weigh-in issues"
        ],
        "pre_game": [
            "Fighter style matchup (striker vs grappler), camp history, layoff"
        ],
        "in_play_triggers": [
            "Fight pace, clinch dominance, accumulated damage"
        ],
        "typical_picks": [
            "Win by method (KO/TKO, Submission, Decision)",
            "Round total (over/under)",
            "Prop: fight goes to decision / finishes early"
        ],
        "required_data": [
            "Fight metrics (FightMetric)",
            "Stoppage history"
        ]
    },
    "rugby": {
        "indicators": [
            "Last 5 matches; average points scored/conceded",
            "Tries per game, conversions, penalties",
            "Possession %, territory %, tackles missed",
            "Yellow/red cards"
        ],
        "pre_game": [
            "Weather, discipline (cards), scrum/lineout strength"
        ],
        "in_play_triggers": [
            "Try momentum, accumulated penalties"
        ],
        "typical_picks": [
            "Moneyline",
            "Handicap",
            "Over/Under points",
            "Total tries"
        ],
        "required_data": [
            "Phase stats",
            "Penalties"
        ]
    },
    "volleyball": {
        "indicators": [
            "Last 5 matches (sets and points per set)",
            "Attack conversion %, blocks per set, aces per set",
            "Serve and reception errors (efficiency)",
            "Rotation and presence of opposites/key players"
        ],
        "pre_game": [
            "Serve advantage, block, injuries"
        ],
        "in_play_triggers": [
            "Point runs, tactical substitutions"
        ],
        "typical_picks": [
            "Win",
            "Handicap (sets)",
            "Over/Under points per set/match",
            "Total aces/blocks"
        ],
        "required_data": [
            "Set-by-set stats",
            "Efficiency metrics"
        ]
    }
}

# ================================
# Função genérica de requisição
# ================================
def make_request(url: str, headers: dict = HEADERS, timeout: int = 30) -> dict:
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Timeout ao conectar na API")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# Funções auxiliares de datas
# ================================
def get_date_range(days_ahead: int = 3):
    today = datetime.utcnow()
    end_date = today + timedelta(days=days_ahead)
    return today.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

# ================================
# Endpoints de jogos
# ================================
@app.get("/live/{sport}")
def get_live_games(sport: str):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[sport]}fixtures?live=all"
    return make_request(url)

@app.get("/upcoming/{sport}/{days}")
def get_upcoming_games(sport: str, days: int = 3):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    start_date, end_date = get_date_range(days)
    url = f"{SPORTS_MAP[sport]}fixtures?from={start_date}&to={end_date}"
    return make_request(url)

@app.get("/h2h/{sport}/{home_id}/{away_id}")
def get_h2h(sport: str, home_id: int, away_id: int):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[sport]}fixtures/headtohead?h2h={home_id}-{away_id}"
    return make_request(url)

@app.get("/stats/{sport}/{fixture_id}")
def get_match_stats(sport: str, fixture_id: int):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[sport]}fixtures/statistics?fixture={fixture_id}"
    return make_request(url)

@app.get("/events/{sport}/{fixture_id}")
def get_match_events(sport: str, fixture_id: int):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[sport]}fixtures/events?fixture={fixture_id}"
    return make_request(url)

@app.get("/odds/{sport}/{fixture_id}")
def get_odds(sport: str, fixture_id: int):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[sport]}odds?fixture={fixture_id}"
    return make_request(url)

# ================================
# Fluxo país → liga → jogos
# ================================
@app.get("/countries/{sport}")
def get_countries(sport: str):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[sport]}countries"
    return make_request(url)

@app.get("/leagues/{sport}/{country_id}")
def get_leagues(sport: str, country_id: int):
    url = f"{SPORTS_MAP[sport]}leagues?country={country_id}"
    return make_request(url)

@app.get("/fixtures/{sport}/{league_id}")
def get_fixtures_by_league(sport: str, league_id: int):
    url = f"{SPORTS_MAP[sport]}fixtures?league={league_id}"
    return make_request(url)

# ================================
# Perfil do Tipster
# ================================
@app.get("/tipster/profile")
def get_tipster_profile():
    profile = TIPSTER_PROFILE.copy()
    if profile['total_predictions'] > 0:
        profile['accuracy'] = round(profile['correct_predictions'] / profile['total_predictions'] * 100, 2)
    return profile

@app.post("/tipster/predict")
def add_tipster_prediction(fixture_id: int, prediction: str, sport: str, result: Optional[str] = None):
    TIPSTER_PROFILE['total_predictions'] += 1
    if result == "correct":
        TIPSTER_PROFILE['correct_predictions'] += 1
    elif result == "wrong":
        TIPSTER_PROFILE['wrong_predictions'] += 1
    TIPSTER_PROFILE['last_predictions'].append({
        "fixture_id": fixture_id,
        "prediction": prediction,
        "sport": sport,
        "result": result
    })
    return {"message": "Previsão adicionada com sucesso!"}

@app.get("/tipster/dashboard")
def tipster_dashboard():
    profile = get_tipster_profile()
    sport_stats = {}
    for prediction in TIPSTER_PROFILE['last_predictions']:
        sport = prediction.get('sport', 'unknown')
        if sport not in sport_stats:
            sport_stats[sport] = {"total": 0, "correct": 0, "wrong": 0}
        sport_stats[sport]['total'] += 1
        if prediction['result'] == "correct":
            sport_stats[sport]['correct'] += 1
        elif prediction['result'] == "wrong":
            sport_stats[sport]['wrong'] += 1
    for s, stats in sport_stats.items():
        stats['accuracy'] = round(stats['correct'] / stats['total'] * 100, 2) if stats['total'] > 0 else 0.0
    return {"profile": profile, "by_sport": sport_stats}

# ================================
# Função: Atualização ao vivo
# ================================
async def update_live_games(sport: str, interval: int = 30):
    while True:
        try:
            url = f"{SPORTS_MAP[sport]}fixtures?live=all"
            live_data = make_request(url)
            print(f"Atualização ao vivo ({sport}): {len(live_data.get('response', []))} jogos")
        except Exception as e:
            print(f"Erro ao atualizar jogos ao vivo ({sport}):", e)
        await asyncio.sleep(interval)

def start_live_update():
    loop = asyncio.get_event_loop()
    for sport in SPORTS_MAP.keys():
        loop.create_task(update_live_games(sport))
    print("Atualização ao vivo iniciada para todos os esportes")
