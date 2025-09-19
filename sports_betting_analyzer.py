# Filename: sports_analyzer_live.py
# Versão 2.0 - Multi-Esportivo Ao Vivo com Tipster IA

import os
import requests
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional


# ================================
# Inicialização do FastAPI
# ================================

app = FastAPI(title="Tipster Ao Vivo - Multi Esportes")

origins = [
    "https://jean-rgsocd.github.io",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================
# Configuração da API Key
# ================================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("API_KEY não definida no ambiente!")

HEADERS = {"x-rapidapi-key": API_KEY}

# ================================
# Mapas de esportes e URLs base
# ================================
SPORTS_MAP = {
    "football": "https://v3.football.api-sports.io/",
    "basketball": "https://v1.basketball.api-sports.io/",
    "nba": "https://v2.nba.api-sports.io/",
    "baseball": "https://v1.baseball.api-sports.io/",
    "formula-1": "https://v1.formula-1.api-sports.io/",
    "handball": "https://v1.handball.api-sports.io/",
    "hockey": "https://v1.hockey.api-sports.io/",
    "mma": "https://v1.mma.api-sports.io/",
    "nfl": "https://v1.american-football.api-sports.io/",
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
    "nfl": {
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
    "formula-1": {
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
# Função para realizar requests na API
# ================================
def make_request(url: str, params: dict = None) -> dict:
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Erro na requisição para {url}: {e}")
        return {"response": []}  # sempre retorna dicionário com "response"


# ================================
# Funções auxiliares de datas
# ================================
def jogos_ao_vivo(esporte: str):
    """Busca apenas jogos ao vivo."""
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[esporte]}fixtures"
    params = {"live": "all"}
    dados = make_request(url, params=params)
    jogos = dados.get("response", [])
    return jogos if isinstance(jogos, list) else []


def jogos_por_data(esporte: str, dias: int = 2):
    """Busca jogos a partir de hoje por X dias (ex: hoje e amanhã)."""
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    hoje = datetime.utcnow().date()
    fim = hoje + timedelta(days=dias - 1)
    url = f"{SPORTS_MAP[esporte]}fixtures?from={hoje}&to={fim}"
    dados = make_request(url)
    return dados.get("response", [])


def get_date_range(dias: int = 3):
    hoje = datetime.utcnow().date()
    fim = hoje + timedelta(days=dias - 1)
    return hoje, fim
# ================================
# Endpoints de jogos
# ================================
@app.get("/jogos-ao-vivo/{esporte}")
def endpoint_jogos_ao_vivo(esporte: str):
    """Retorna todos os jogos ao vivo do esporte."""
    return jogos_ao_vivo(esporte)


@app.get("/jogos-hoje-amanha/{esporte}")
def endpoint_jogos_hoje_amanha(esporte: str):
    """Retorna jogos de hoje e amanhã."""
    return jogos_por_data(esporte, dias=2)


@app.get("/proximos-jogos/{esporte}/{dias}")
def endpoint_proximos_jogos(esporte: str, dias: int = 3):
    """Retorna próximos jogos do esporte para X dias."""
    start_date, end_date = get_date_range(dias)
    url = f"{SPORTS_MAP[esporte]}fixtures?from={start_date}&to={end_date}"
    dados = make_request(url)
    return dados.get("response", [])


@app.get("/confronto-direto/{esporte}/{id_casa}/{id_fora}")
def endpoint_confronto_direto(esporte: str, id_casa: int, id_fora: int):
    url = f"{SPORTS_MAP[esporte]}fixtures/headtohead?h2h={id_casa}-{id_fora}"
    dados = make_request(url)
    return dados.get("response", [])


@app.get("/estatisticas/{esporte}/{id_partida}")
def endpoint_estatisticas_partida(esporte: str, id_partida: int):
    url = f"{SPORTS_MAP[esporte]}fixtures/statistics?fixture={id_partida}"
    dados = make_request(url)
    return dados.get("response", [])


@app.get("/eventos/{esporte}/{id_partida}")
def endpoint_eventos_partida(esporte: str, id_partida: int):
    url = f"{SPORTS_MAP[esporte]}fixtures/events?fixture={id_partida}"
    dados = make_request(url)
    return dados.get("response", [])


@app.get("/probabilidades/{esporte}/{id_partida}")
def endpoint_probabilidades(esporte: str, id_partida: int):
    url = f"{SPORTS_MAP[esporte]}odds?fixture={id_partida}"
    dados = make_request(url)
    return dados.get("response", [])

# ================================
# Fluxo país → liga → jogos
# ================================
@app.get("/paises/{esporte}")
def listar_paises(esporte: str):
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[esporte]}countries"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/ligas/{esporte}/{id_pais}")
def listar_ligas(esporte: str, id_pais: int):
    url = f"{SPORTS_MAP[esporte]}leagues?country={id_pais}"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/partidas/{esporte}/{id_liga}")
def listar_partidas(esporte: str, id_liga: int):
    url = f"{SPORTS_MAP[esporte]}fixtures?league={id_liga}"
    dados = make_request(url)
    return dados.get("response", [])

# ================================
# Perfil do Tipster
# ================================
@app.get("/perfil-tipster")
def perfil_tipster():
    profile = TIPSTER_PROFILE.copy()
    if profile['total_predictions'] > 0:
        profile['accuracy'] = round(profile['correct_predictions'] / profile['total_predictions'] * 100, 2)
    return profile

@app.post("/adicionar-previsao")
def adicionar_previsao(fixture_id: int, previsao: str, esporte: str, resultado: Optional[str] = None):
    TIPSTER_PROFILE['total_predictions'] += 1
    if resultado == "correct":
        TIPSTER_PROFILE['correct_predictions'] += 1
    elif resultado == "wrong":
        TIPSTER_PROFILE['wrong_predictions'] += 1
    TIPSTER_PROFILE['last_predictions'].append({
        "fixture_id": fixture_id,
        "prediction": previsao,
        "sport": esporte,
        "result": resultado
    })
    return {"message": "Previsão adicionada com sucesso!"}

@app.get("/dashboard-tipster")
def dashboard_tipster():
    profile = perfil_tipster()
    esporte_stats = {}
    for prediction in TIPSTER_PROFILE['last_predictions']:
        esporte = prediction.get('sport', 'desconhecido')
        if esporte not in esporte_stats:
            esporte_stats[esporte] = {"total": 0, "corretas": 0, "erradas": 0}
        esporte_stats[esporte]['total'] += 1
        if prediction['result'] == "correct":
            esporte_stats[esporte]['corretas'] += 1
        elif prediction['result'] == "wrong":
            esporte_stats[esporte]['erradas'] += 1
    for e, stats in esporte_stats.items():
        stats['acuracia'] = round(stats['corretas'] / stats['total'] * 100, 2) if stats['total'] > 0 else 0.0
    return {"perfil": profile, "por_esporte": esporte_stats}

# ================================
# Rotas de compatibilidade com frontend atual
# ================================
@app.get("/jogos-por-esporte")
def jogos_por_esporte_compat(sport: str = Query(..., description="Nome do esporte")):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    return jogos_ao_vivo(sport)

@app.get("/paises")
def paises_compat(sport: str = Query(..., description="Nome do esporte")):
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    return listar_paises(sport)

# ================================
# Atualização ao vivo (startup)
# ================================
async def atualizar_jogos_ao_vivo(esporte: str, intervalo: int = 30):
    while True:
        try:
            url = f"{SPORTS_MAP[esporte]}fixtures?live=all"
            dados = make_request(url)
            print(f"Atualização ao vivo ({esporte}): {len(dados.get('response', []))} jogos")
        except Exception as e:
            print(f"Erro ao atualizar jogos ao vivo ({esporte}):", e)
        await asyncio.sleep(intervalo)

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    for esporte in SPORTS_MAP.keys():
        loop.create_task(atualizar_jogos_ao_vivo(esporte))
    print("Atualização ao vivo iniciada automaticamente para todos os esportes")
