# Filename: sports_analyzer_live.py
# Versão: 5.x (entrega por partes)
# Parte 1/5 - imports, FastAPI init, SPORTS_MAP, TIPSTER_PROFILES_DETAILED, make_request

import os
import requests
import asyncio
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any

# ================================
# Inicialização do FastAPI
# ================================
app = FastAPI(title="Tipster Ao Vivo - Multi Esportes")

origins = [
    "https://jean-rgsocd.github.io",
    "http://localhost:5500",
    "https://analisador-apostas.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# Configuração da API Key (variável de ambiente)
# ================================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("API_KEY não definida no ambiente! Defina a variável de ambiente API_KEY.")

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
# Perfis detalhados do Tipster (coloquei os perfis que você passou)
# ================================
TIPSTER_PROFILES_DETAILED: Dict[str, Dict[str, Any]] = {
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
            "Possession >65% over last 15'",
            "2+ shots on target within <10'",
            "Accumulated fouls >X → card bet"
        ],
        "typical_picks": [
            "Home/Away win",
            "Over 1.5/2.5 goals",
            "Over corners",
            "Over cards",
            "Both teams to score (BTTS)"
        ],
        "required_data": [
            "Match results", "Match events (corners, cards, shots)", "xG if possible"
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
            "Boxscore per game", "Play-by-play for live triggers"
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
        "pre_game": ["Defense vs offense matchup, bench advantage, rest vs travel"],
        "in_play_triggers": ["Pace variation, starter fouls, scoring runs (>10 points)"],
        "typical_picks": ["Moneyline", "Over/Under total points", "Spread handicap"],
        "required_data": ["Boxscore", "Play-by-play"]
    },
    "nfl": {
        "indicators": [
            "Last 5 matches (including performance per quarter)",
            "Yards allowed/earned per game (total and pass/run)",
            "Turnovers (last 5 games)",
            "Red zone efficiency, 3rd down conversion",
            "Key QB/skill position injuries"
        ],
        "pre_game": ["Offense/defense matchup, weather, injuries"],
        "in_play_triggers": ["3rd down failures, sacks, turnover momentum"],
        "typical_picks": ["Moneyline", "Spread", "Over/Under total points", "Props (QB yards)"],
        "required_data": ["Drive charts", "Play-by-play"]
    },
    "baseball": {
        "indicators": [
            "Last 5 matches (including starting pitcher stats)",
            "Starting pitcher ERA, WHIP, K/BB, FIP",
            "Batter OPS/wOBA",
            "Win probability via simulator (Elo/xStat)",
            "Injuries/closer status"
        ],
        "pre_game": ["Pitcher vs lineup matchup (platoon splits L/R), weather/wind"],
        "in_play_triggers": ["Pitcher performance per inning, bullpen usage"],
        "typical_picks": ["Moneyline", "Over/Under runs", "Run line (handicap)"],
        "required_data": ["Boxscore", "Pitching lines", "Splits L/R"]
    },
    "formula-1": {
        "indicators": [
            "Qualifying and race performance last 5 races",
            "Average laps in Top-10 per session",
            "Average lap time, tire degradation, pit strategy",
            "Weather forecast"
        ],
        "pre_game": ["Qualifying, setup, circuit history"],
        "in_play_triggers": ["Safety car probability, pace after pit, tire wear"],
        "typical_picks": ["Podium (top-3) / win", "Top-6/Top-10", "Fastest lap"],
        "required_data": ["Basic telemetry", "Sector times", "Tire status"]
    },
    "handball": {
        "indicators": ["Last 5 matches; average goals scored/conceded", "Shooting efficiency (%)", "Goalkeeper save %", "Turnovers"],
        "pre_game": ["Game pace, goalkeeper rotation, fitness"],
        "in_play_triggers": ["Goal sequences, numerical advantages"],
        "typical_picks": ["Win", "Over total goals", "Handicap"],
        "required_data": ["Stats by period", "Goalkeeper efficiency"]
    },
    "hockey": {
        "indicators": ["Last 5 matches; average goals", "Shots on goal per game", "Goalie save %, PDO", "Powerplay/penalty kill %"],
        "pre_game": ["Projected goalie, special teams"],
        "in_play_triggers": ["SOG per 20', goalie stamina"],
        "typical_picks": ["Moneyline", "Over/Under goals", "Puck line"],
        "required_data": ["Boxscore", "SOG", "PK/PP stats"]
    },
    "mma": {
        "indicators": ["Last 5 fights per fighter", "Strikes per minute, takedown accuracy/defense", "Reach, age, layoff time"],
        "pre_game": ["Fighter style matchup, camp history"],
        "in_play_triggers": ["Fight pace, clinch dominance, accumulated damage"],
        "typical_picks": ["Win by KO/TKO", "Submission", "Fight goes distance"],
        "required_data": ["Fight metrics"]
    },
    "rugby": {
        "indicators": ["Last 5 matches; average points scored/conceded", "Tries per game, conversions, penalties"],
        "pre_game": ["Weather, discipline (cards), scrum/lineout strength"],
        "in_play_triggers": ["Try momentum, accumulated penalties"],
        "typical_picks": ["Moneyline", "Handicap", "Over/Under points"],
        "required_data": ["Phase stats", "Penalties"]
    },
    "volleyball": {
        "indicators": ["Last 5 matches (sets and points per set)", "Attack conversion %, blocks per set, aces per set", "Serve and reception errors (efficiency)"],
        "pre_game": ["Serve advantage, block, injuries"],
        "in_play_triggers": ["Point runs, tactical substitutions"],
        "typical_picks": ["Win", "Handicap (sets)", "Over/Under points per set"],
        "required_data": ["Set-by-set stats", "Efficiency metrics"]
    },
    "afl": {
        "indicators": ["Last 5 matches, scoring breakdown", "Kicks/marks", "Inside 50s"],
        "pre_game": ["Ground conditions, travel fatigue"],
        "in_play_triggers": ["Momentum, scoring runs"],
        "typical_picks": ["Moneyline", "Line", "Total points"],
        "required_data": ["Match stats", "Player minutes"]
    }
}

# ================================
# Perfil agregado do Tipster (tracking simples)
# ================================
TIPSTER_PROFILE: Dict[str, Any] = {
    "total_predictions": 0,
    "correct_predictions": 0,
    "wrong_predictions": 0,
    "last_predictions": []
}

# ================================
# Utilitário genérico de requisição para API-Sports
# ================================
def make_request(url: str, params: dict = None) -> dict:
    """
    Requisição GET para API-Sports com headers corretos.
    Retorna sempre um dict; em erro, retorna {"response": []}
    """
    try:
        host = url.split("//")[1].split("/")[0]
        headers = {
            "x-rapidapi-key": API_KEY,
            "x-rapidapi-host": host
        }
        resp = requests.get(url, headers=headers, params=params, timeout=12)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[make_request] erro: {e} - url={url} params={params}")
        return {"response": []}
        # Parte 2/5 - helpers para extrair estatísticas e normalizar fixtures

# ================================
# Helpers para estatísticas - Football
# ================================
def get_last_matches_stats_football(team_id: int, n: int = 5) -> Dict[str, Any]:
    """
    Retorna média de gols e taxa de vitória para football.
    Usa endpoint: /fixtures?team={id}&last={n}
    """
    if not team_id:
        return {"media_gols": 0.0, "taxa_vitoria": 0.0, "played": 0}

    url = f"{SPORTS_MAP['football']}fixtures"
    params = {"team": team_id, "last": n}
    data = make_request(url, params=params)
    jogos = data.get("response", [])

    total_gols = 0
    jogos_validos = 0
    vitorias = 0

    for j in jogos:
        gols_for = 0
        gols_against = 0
        # V3 pode retornar keys diferentes; lidamos com os padrões mais comuns
        if "goals" in j and isinstance(j["goals"], dict):
            g = j["goals"]
            # padrão fixtures: g.get("home"), g.get("away")
            home_id = j.get("teams", {}).get("home", {}).get("id")
            away_id = j.get("teams", {}).get("away", {}).get("id")
            if home_id == team_id:
                gols_for = g.get("home", 0) or 0
                gols_against = g.get("away", 0) or 0
            elif away_id == team_id:
                gols_for = g.get("away", 0) or 0
                gols_against = g.get("home", 0) or 0
            else:
                gols_for = g.get("for", 0) or 0
                gols_against = g.get("against", 0) or 0

        total_gols += gols_for
        jogos_validos += 1
        if gols_for > gols_against:
            vitorias += 1

    media_gols = round(total_gols / jogos_validos, 2) if jogos_validos else 0.0
    taxa_vitoria = round((vitorias / jogos_validos) * 100, 2) if jogos_validos else 0.0
    return {"media_gols": media_gols, "taxa_vitoria": taxa_vitoria, "played": jogos_validos}

# ================================
# Helpers para estatísticas - Basketball
# ================================
def get_last_matches_stats_basketball(team_id: int, n: int = 5, sport: str = "basketball") -> Dict[str, Any]:
    """
    Retorna média de pontos marcados e sofridos dos últimos n jogos.
    Agora aceita `sport` para suportar 'basketball' e 'nba' (usa base apropriada).
    Usa endpoint: /games?team={id}&last={n}
    """
    if not team_id:
        return {"media_feitos": 0.0, "media_sofridos": 0.0, "played": 0}

    base = SPORTS_MAP.get(sport) or SPORTS_MAP.get("basketball")
    if not base:
        return {"media_feitos": 0.0, "media_sofridos": 0.0, "played": 0}

    url = f"{base}games"
    params = {"team": team_id, "last": n}
    data = make_request(url, params=params)
    jogos = data.get("response", [])

    pontos_feitos = 0
    pontos_sofridos = 0
    jogos_validos = 0

    for j in jogos:
        try:
            scores = j.get("scores", {}) or {}
            home_id = j.get("teams", {}).get("home", {}).get("id")
            away_id = j.get("teams", {}).get("away", {}).get("id")
            if not scores:
                continue
            if home_id == team_id:
                pts_for = scores.get("home", {}).get("total", 0)
                pts_against = scores.get("away", {}).get("total", 0)
            else:
                pts_for = scores.get("away", {}).get("total", 0)
                pts_against = scores.get("home", {}).get("total", 0)
            pontos_feitos += int(pts_for or 0)
            pontos_sofridos += int(pts_against or 0)
            jogos_validos += 1
        except Exception:
            continue

    media_feitos = round(pontos_feitos / jogos_validos, 2) if jogos_validos else 0.0
    media_sofridos = round(pontos_sofridos / jogos_validos, 2) if jogos_validos else 0.0
    return {"media_feitos": media_feitos, "media_sofridos": media_sofridos, "played": jogos_validos}

# ================================
# Normalizador simples de fixture -> dicionário enxuto (usado pelo frontend)
# ================================
def normalize_fixture_response(g: dict) -> Dict[str, Any]:
    fixture = g.get("fixture", g)
    teams = g.get("teams", {})
    home = teams.get("home", {}).get("name", teams.get("home", {}).get("shortName", "Time A"))
    away = teams.get("away", {}).get("name", teams.get("away", {}).get("shortName", "Time B"))
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")
    game_id = fixture.get("id", g.get("id"))
    status = fixture.get("status", {}).get("short", "NS") if isinstance(fixture.get("status"), dict) else fixture.get("status", "NS")
    date_field = fixture.get("date", "") or fixture.get("start", "") or ""
    if "T" in date_field:
        date_part, time_part = date_field.split("T")
        time = f"{date_part} {time_part[:5]}"
    else:
        time = date_field or "?"
    return {
        "game_id": game_id,
        "home": home,
        "away": away,
        "home_id": home_id,
        "away_id": away_id,
        "time": time,
        "status": status
    }
# Parte 3/5 - endpoint partidas-por-esporte (3 dias) e endpoints auxiliares simples

# ================================
# Endpoint: Partidas por esporte (3 dias)
# ================================
@app.get("/partidas-por-esporte/{sport}")
async def get_games_by_sport(sport: str):
    sport = sport.lower()
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    hoje = datetime.utcnow().date()
    jogos: List[Dict[str, Any]] = []

    for i in range(3):  # hoje, amanhã, depois
        data_str = (hoje + timedelta(days=i)).strftime("%Y-%m-%d")

        # Seleciona endpoint correto
        if sport == "football":
            endpoint = f"fixtures?date={data_str}"
        elif sport in ["basketball", "nba", "baseball", "nfl", "rugby", "volleyball", "handball", "hockey"]:
            endpoint = f"games?date={data_str}"
        elif sport == "mma":
            endpoint = f"fights?date={data_str}"
        elif sport == "formula-1":
            endpoint = f"races?season={datetime.now().year}"
        else:
            raise HTTPException(status_code=400, detail=f"Esporte {sport} não suportado.")

        url = f"{SPORTS_MAP[sport]}{endpoint}"
        data_json = make_request(url)

        for g in data_json.get("response", []):
            jogos.append(normalize_fixture_response(g))

        # Fórmula 1 é por season — não precisa repetir por datas
        if sport == "formula-1":
            break

    return jogos

# ================================
# Endpoints simples: estatísticas, eventos, odds (por esporte e partida)
# ================================
@app.get("/estatisticas/{esporte}/{id_partida}")
def endpoint_estatisticas_partida(esporte: str, id_partida: int):
    esporte = esporte.lower()
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")

    # preferencial: football usa fixtures/statistics (param fixture)
    if esporte == "football":
        url = f"{SPORTS_MAP[esporte]}fixtures/statistics"
        params = {"fixture": id_partida}
    else:
        # outros esportes: tentamos games/statistics (param game)
        url = f"{SPORTS_MAP[esporte]}games/statistics"
        params = {"game": id_partida}

    dados = make_request(url, params=params)
    # fallback: se resposta vazia, tentar fixtures/statistics (algumas APIs não são consistentes)
    if not dados.get("response"):
        dados = make_request(f"{SPORTS_MAP[esporte]}fixtures/statistics", params={"fixture": id_partida})
    return dados.get("response", [])


@app.get("/eventos/{esporte}/{id_partida}")
def endpoint_eventos_partida(esporte: str, id_partida: int):
    esporte = esporte.lower()
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")

    if esporte == "football":
        url = f"{SPORTS_MAP[esporte]}fixtures/events"
        params = {"fixture": id_partida}
    else:
        url = f"{SPORTS_MAP[esporte]}games/events"
        params = {"game": id_partida}

    dados = make_request(url, params=params)
    if not dados.get("response"):
        # fallback para fixtures/events
        dados = make_request(f"{SPORTS_MAP[esporte]}fixtures/events", params={"fixture": id_partida})
    return dados.get("response", [])


@app.get("/probabilidades/{esporte}/{id_partida}")
def endpoint_probabilidades(esporte: str, id_partida: int):
    esporte = esporte.lower()
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")

    url = f"{SPORTS_MAP[esporte]}odds"
    # tentar primeiro com 'fixture' (usado por football), se vazio tentar 'game'
    dados = make_request(url, params={"fixture": id_partida})
    if not dados.get("response"):
        dados = make_request(url, params={"game": id_partida})
    # fallback: tentar odds no namespace fixtures (algumas rotas antigas)
    if not dados.get("response"):
        dados = make_request(f"{SPORTS_MAP[esporte]}fixtures/odds", params={"fixture": id_partida})
    return dados.get("response", [])

# ================================
# País -> ligas -> partidas (apenas para football 'countries'/'leagues'/'fixtures')
# ================================
@app.get("/paises/{esporte}")
def listar_paises(esporte: str):
    esporte = esporte.lower()
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[esporte]}countries"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/ligas/{esporte}/{id_pais}")
def listar_ligas(esporte: str, id_pais: str):
    esporte = esporte.lower()
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[esporte]}leagues?country={id_pais}"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/partidas/{esporte}/{id_liga}")
def listar_partidas_por_liga(esporte: str, id_liga: int):
    esporte = esporte.lower()
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[esporte]}fixtures?league={id_liga}"
    dados = make_request(url)
    # normalize
    jogos = [normalize_fixture_response(g) for g in dados.get("response", [])]
    return jogos
# Parte 4/5 - analisar-pre-jogo e analisar-ao-vivo com lógica usando dados reais para football e basketball

# ================================
# Endpoint: Analisar Pré-Jogo (Football + Basketball)
# ================================
@app.get("/analisar-pre-jogo")
def analisar_pre_jogo(game_id: int, sport: str):
    """
    Pré-jogo:
     - football: usa últimos 5 jogos para média de gols -> Over/Under 2.5
     - basketball/nba: usa média de pontos -> Over/Under 200.5 (threshold ajustável)
    """
    sport = sport.lower()
    if sport not in SPORTS_MAP:
        return [{"market": "N/A", "suggestion": "Esporte não suportado", "confidence": 0, "justification": "Esporte inválido"}]

    # FOOTBALL
    if sport == "football":
        url = f"{SPORTS_MAP['football']}fixtures"
        params = {"id": game_id}
        data = make_request(url, params=params)
        resp = data.get("response", [])
        if not resp:
            return [{"market": "N/A", "suggestion": "Partida não encontrada", "confidence": 0, "justification": "Game ID inválido"}]
        fixture = resp[0]
        home = fixture.get("teams", {}).get("home", {})
        away = fixture.get("teams", {}).get("away", {})
        home_id = home.get("id")
        away_id = away.get("id")
        home_name = home.get("name", "Casa")
        away_name = away.get("name", "Fora")

        home_stats = get_last_matches_stats_football(home_id, 5) if home_id else {"media_gols": 0.0}
        away_stats = get_last_matches_stats_football(away_id, 5) if away_id else {"media_gols": 0.0}

        total_media = home_stats["media_gols"] + away_stats["media_gols"]

        if total_media > 2.5:
            pick = "Over 2.5 goals"
            confidence = min(95, int(60 + (total_media - 2.5) * 10))
            justification = f"{home_name} ({home_stats['media_gols']}) + {away_name} ({away_stats['media_gols']}) => média conjunta {total_media} gols."
        else:
            pick = "Under 2.5 goals"
            confidence = min(85, int(55 + (2.5 - total_media) * 8))
            justification = f"Médias recentes: {home_stats['media_gols']} e {away_stats['media_gols']}."

        return [{
            "market": "Over/Under",
            "suggestion": pick,
            "confidence": confidence,
            "justification": justification
        }]

    # BASKETBALL / NBA
    elif sport in ["basketball", "nba"]:
        base = SPORTS_MAP.get("basketball") if sport == "basketball" else SPORTS_MAP.get("nba")
        if not base:
            return [{"market": "N/A", "suggestion": "Base do esporte não encontrada", "confidence": 0, "justification": "Configuração inválida"}]

        url = f"{base}games"
        params = {"id": game_id}
        data = make_request(url, params=params)
        resp = data.get("response", [])
        if not resp:
            return [{"market": "N/A", "suggestion": "Jogo não encontrado", "confidence": 0, "justification": "Game ID inválido"}]

        fixture = resp[0]
        home = fixture.get("teams", {}).get("home", {})
        away = fixture.get("teams", {}).get("away", {})
        home_id = home.get("id")
        away_id = away.get("id")
        home_name = home.get("name", "Casa")
        away_name = away.get("name", "Fora")

        # se sport for 'nba', passe sport='nba', caso contrário 'basketball'
        query_sport = "nba" if sport == "nba" else "basketball"
        home_stats = get_last_matches_stats_basketball(home_id, 5, sport=query_sport) if home_id else {"media_feitos": 0.0, "media_sofridos": 0.0}
        away_stats = get_last_matches_stats_basketball(away_id, 5, sport=query_sport) if away_id else {"media_feitos": 0.0, "media_sofridos": 0.0}

        total_medio = home_stats["media_feitos"] + away_stats["media_feitos"]
        threshold = 200.5

        if total_medio > threshold:
            pick = f"Over {int(threshold)} pontos"
            confidence = min(95, int(55 + (total_medio - threshold) * 5))
            justification = f"Médias: {home_name} ({home_stats['media_feitos']}) + {away_name} ({away_stats['media_feitos']}) => total médio {total_medio}."
        else:
            pick = f"Under {int(threshold)} pontos"
            confidence = min(85, int(55 + (threshold - total_medio) * 4))
            justification = f"Médias recentes: {home_stats['media_feitos']} e {away_stats['media_feitos']}."

        return [{
            "market": "Total de pontos",
            "suggestion": pick,
            "confidence": confidence,
            "justification": justification
        }]

    # FALLBACK para outros esportes (usa perfil)
    profile = TIPSTER_PROFILES_DETAILED.get(sport)
    if not profile:
        return [{"market": "N/A", "suggestion": "Ainda não implementado", "confidence": 0, "justification": "Esporte não suportado"}]
    pick = random.choice(profile.get("typical_picks", ["N/A"]))
    confidence = random.randint(50, 75)
    justification = f"Pick gerado pelo perfil do esporte: {sport}."
    return [{"market": "Generic", "suggestion": pick, "confidence": confidence, "justification": justification}]


# ================================
# Endpoint: Analisar Ao Vivo (Football + Basketball)
# ================================
@app.get("/analisar-ao-vivo")
def analisar_ao_vivo(game_id: int, sport: str):
    sport = sport.lower()
    if sport not in SPORTS_MAP:
        return [{"market": "N/A", "suggestion": "Esporte não suportado", "confidence": 0, "justification": "Esporte inválido"}]

    # FOOTBALL ao vivo
    if sport == "football":
        url = f"{SPORTS_MAP['football']}fixtures/statistics"
        params = {"fixture": game_id}
        data = make_request(url, params=params)
        stats_resp = data.get("response", [])

        # fallback para events
        if not stats_resp:
            ev_data = make_request(f"{SPORTS_MAP['football']}fixtures/events", params={"fixture": game_id})
            events = ev_data.get("response", [])
            if any(e.get("type") == "Goal" for e in events):
                return [{
                    "market": "Ao vivo",
                    "suggestion": "Acompanhar momentum após gol",
                    "confidence": 70,
                    "justification": "Detectado gol recente nos eventos."
                }]
            else:
                return [{"market": "Ao vivo", "suggestion": "Sem dados ao vivo", "confidence": 0, "justification": "Sem estatísticas disponíveis."}]

        poss_vals = []
        for entry in stats_resp:
            stats_list = entry.get("statistics", [])
            for s in stats_list:
                if s.get("type") == "Ball Possession":
                    val = s.get("value", "0%").replace("%", "")
                    try:
                        poss_vals.append(int(val))
                    except Exception:
                        poss_vals.append(0)

        posse_media = sum(poss_vals) / len(poss_vals) if poss_vals else 0
        if posse_media > 65:
            return [{
                "market": "Ao vivo",
                "suggestion": "Próximo gol do time dominante",
                "confidence": 85,
                "justification": f"Posse média alta ({posse_media}%) — pressão sustentada."
            }]
        else:
            return [{
                "market": "Ao vivo",
                "suggestion": "Sem trigger claro",
                "confidence": 55,
                "justification": "Estatísticas não indicam vantagem clara."
            }]

    # BASKETBALL ao vivo
    elif sport in ["basketball", "nba"]:
        base = SPORTS_MAP.get("basketball") if sport == "basketball" else SPORTS_MAP.get("nba")
        if not base:
            return [{"market": "N/A", "suggestion": "Configuração da base ausente", "confidence": 0, "justification": ""}]

        url = f"{base}games/statistics"
        data = make_request(url, params={"game": game_id})
        resp = data.get("response", [])
        if not resp:
            return [{"market": "Ao vivo", "suggestion": "Sem dados ao vivo", "confidence": 0, "justification": "Sem estatísticas."}]

        # tenta detectar pontos do 1º período / quarter
        periods = resp[0].get("periods", {}) or resp[0].get("timeline", {})
        q1_points = None
        try:
            if isinstance(periods, dict) and "1" in periods:
                q1_points = periods["1"].get("points")
            elif isinstance(periods, list) and len(periods) >= 1:
                q1_points = periods[0].get("points") or periods[0].get("total")
        except Exception:
            q1_points = None

        try:
            if q1_points and int(q1_points) > 55:
                return [{
                    "market": "Ao vivo",
                    "suggestion": "Over total (ritmo alto)",
                    "confidence": 80,
                    "justification": f"1º quarto com {q1_points} pontos — ritmo alto."
                }]
        except Exception:
            pass

        return [{
            "market": "Ao vivo",
            "suggestion": "Sem trigger claro",
            "confidence": 55,
            "justification": "Dados ao vivo não mostram trigger pronto."
        }]

    # fallback genérico
    profile = TIPSTER_PROFILES_DETAILED.get(sport)
    if not profile:
        return [{"market": "N/A", "suggestion": "Esporte não suportado", "confidence": 0, "justification": "Perfil ausente"}]
    pick = random.choice(profile.get("typical_picks", ["N/A"]))
    confidence = random.randint(50, 80)
    justification = "Pick gerado via perfil do esporte (fallback ao vivo)."
    return [{"market": "Ao vivo", "suggestion": pick, "confidence": confidence, "justification": justification}]
    # Parte 5/5 - endpoints de perfil, adicionar previsão, e startup tasks

# ================================
# Perfil do Tipster e rota para adicionar previsões (tracking simples)
# ================================
@app.get("/perfil-tipster")
def perfil_tipster():
    profile = TIPSTER_PROFILE.copy()
    if profile["total_predictions"] > 0:
        profile["accuracy"] = round(profile["correct_predictions"] / profile["total_predictions"] * 100, 2)
    else:
        profile["accuracy"] = 0.0
    return profile

@app.post("/adicionar-previsao")
def adicionar_previsao(fixture_id: int, previsao: str, esporte: str, resultado: Optional[str] = None):
    TIPSTER_PROFILE["total_predictions"] += 1
    if resultado == "correct":
        TIPSTER_PROFILE["correct_predictions"] += 1
    elif resultado == "wrong":
        TIPSTER_PROFILE["wrong_predictions"] += 1
    TIPSTER_PROFILE["last_predictions"].append({
        "fixture_id": fixture_id,
        "prediction": previsao,
        "sport": esporte,
        "result": resultado,
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"message": "Previsão adicionada com sucesso!"}

# ================================
# Atualização ao vivo (startup) - opcional, roda tarefas periódicas
# ================================
async def atualizar_jogos_ao_vivo(esporte: str, intervalo: int = 300):
    """
    Task periódica que usa endpoint correto por esporte:
    - football -> fixtures?date=...&live=all
    - outros    -> games?date=...&live=all
    - formula-1 -> races?season=YYYY (chamado só uma vez)
    """
    while True:
        try:
            hoje = datetime.utcnow().date().strftime("%Y-%m-%d")

            if esporte == "football":
                endpoint = f"fixtures?date={hoje}&live=all"
            elif esporte in ["basketball", "nba", "baseball", "nfl", "rugby", "volleyball", "handball", "hockey"]:
                endpoint = f"games?date={hoje}&live=all"
            elif esporte == "mma":
                endpoint = f"fights?date={hoje}&live=all"
            elif esporte == "formula-1":
                endpoint = f"races?season={datetime.now().year}"
            else:
                # fallback geral
                endpoint = f"fixtures?date={hoje}&live=all"

            url = f"{SPORTS_MAP[esporte]}{endpoint}"
            dados = make_request(url)
            print(f"[atualizar_jogos] ({esporte}) jogos ao vivo hoje: {len(dados.get('response', []))}")
        except Exception as e:
            print(f"[atualizar_jogos] erro ({esporte}): {e}")
        await asyncio.sleep(intervalo)


@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    # Só agendamos para sports principais para não estourar quota
    for esporte in ["football", "basketball"]:
        loop.create_task(atualizar_jogos_ao_vivo(esporte, intervalo=300))
    print("Serviço iniciado - atualizações ao vivo agendadas (football, basketball).")

# ================================
# FIM DO ARQUIVO
# ================================
# Observações:
# - Verifique a variável de ambiente API_KEY no Render (Settings > Environment).
# - Antes de deploy, teste localmente:
#     uvicorn sports_analyzer_live:app --reload
# - Testes úteis:
#     GET /partidas-por-esporte/football
#     GET /partidas-por-esporte/basketball
#     GET /analisar-pre-jogo?game_id=<id>&sport=football
#     GET /analisar-ao-vivo?game_id=<id>&sport=football
#
# Se quiser, na próxima mensagem eu te envio:
#  - um script de teste automátizado (test_api.py) para rodar local e verificar endpoints;
#  - o snippet JS para colar no console do navegador que mostra os resultados e ajuda a debuggar (já mandei antes, mas posso adaptar à versão final).


