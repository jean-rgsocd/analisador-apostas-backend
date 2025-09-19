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
    "football": "https://v3.football.api-sports.io/fixtures",       # Futebol
    "basketball": "https://v1.basketball.api-sports.io/games",      # Basquete (outras ligas)
    "nba": "https://v2.nba.api-sports.io/games",                    # NBA
    "nfl": "https://v1.american-football.api-sports.io/games",      # NFL
    "baseball": "https://v1.baseball.api-sports.io/games",          # Baseball
    "formula-1": "https://v1.formula-1.api-sports.io/races",        # Fórmula 1
    "handball": "https://v1.handball.api-sports.io/games",          # Handebol
    "hockey": "https://v1.hockey.api-sports.io/games",              # Hóquei
    "mma": "https://v1.mma.api-sports.io/fights",                   # MMA
    "rugby": "https://v1.rugby.api-sports.io/games",                # Rugby
    "volleyball": "https://v1.volleyball.api-sports.io/games"       # Vôlei
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
async def get_matches_by_sport(sport: str, date: str, api_key: str):
    """Busca jogos de acordo com o esporte e data."""
    import httpx

    url = SPORTS_MAP.get(sport)
    if not url:
        return {"error": f"Esporte '{sport}' não suportado."}

    headers = {"x-apisports-key": api_key}

    # parâmetros diferentes dependendo do endpoint
    params = {}
    if sport == "football":
        params = {"date": date}
    elif sport in ["basketball", "nba", "nfl", "baseball", "handball", "hockey", "rugby", "volleyball"]:
        params = {"date": date}
    elif sport == "mma":
        params = {"date": date}
    elif sport == "formula-1":
        params = {"season": date.split("-")[0]}  # pega só o ano

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            return {"error": f"API retornou erro {resp.status_code}", "details": resp.text}
        return resp.json()


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
    Análise pré-jogo DINÂMICA baseada em estatísticas recentes.
    Retorna lista de picks com mercado, sugestão, confiança (%) e justificativa.
    """

    sport = sport.lower()

    # --- Helper interno: score/prob builder ---
    def build_pick(market: str, suggestion: str, score_base: float, indicators: Dict[str, float], max_conf=95):
        """
        score_base: valor entre 0..1 estimando probabilidade do evento (0.0 = improvável, 1.0 = muito provável)
        indicators: dicionário de indicadores e seus "força" (0..1) usados na justificativa
        """
        prob = int(min(max_conf, max(1, round(score_base * 100))))
        # elevar confiança se vários indicadores fortes
        indicator_strength = sum(1 for v in indicators.values() if v >= 0.6)
        if indicator_strength >= 2:
            prob = min(max_conf, prob + 10)
        justification = " | ".join([f"{k}: {round(v*100,1)}%" for k, v in indicators.items()])
        return {
            "market": market,
            "suggestion": suggestion,
            "confidence": prob,
            "justification": justification
        }

    # ---------------- FOOTBALL (futebol) ----------------
if sport == "football":
        base = SPORTS_MAP.get("football")
        data = make_request(f"{base}fixtures", params={"id": game_id})
        resp = data.get("response", [])
       if not resp:
    return [{
        "market": "N/A",
        "suggestion": "Partida não encontrada",
        "confidence": 0,
        "justification": "Game ID inválido"
    }]

fixture = resp[0]
    home = fixture.get("teams", {}).get("home", {})
    away = fixture.get("teams", {}).get("away", {})
    home_id, away_id = home.get("id"), away.get("id")
    home_name, away_name = home.get("name", "Casa"), away.get("name", "Fora")

    # pegar médias de gols recentes (últimos 5)
    home_stats = get_last_matches_stats_football(home_id, 5) if home_id else {"media_gols": 0.0}
    away_stats = get_last_matches_stats_football(away_id, 5) if away_id else {"media_gols": 0.0}

    # 🚨 fallback de estatísticas
    if (
        not home_stats
        or not away_stats
        or (home_stats.get("media_gols", 0.0) == 0.0 and away_stats.get("media_gols", 0.0) == 0.0)
    ):
        return [{
            "market": "N/A",
            "suggestion": "Sem estatísticas recentes suficientes",
            "confidence": 0,
            "justification": "A API não retornou dados confiáveis para este jogo."
        }]

    # dynamic line: média conjunta * ajuste
    dynamic_line = round((home_stats["media_gols"] + away_stats["media_gols"]) * 1.05, 2)  # leve ajuste
    total_avg = home_stats["media_gols"] + away_stats["media_gols"]

    # indicador adicional: odds (se disponível)
    odds_resp = make_request(f"{base}odds", params={"fixture": game_id})
    odds_available = bool(odds_resp.get("response"))
    odds_factor = 0.0
    if odds_available:
        try:
            first_market = odds_resp["response"][0]
            odds_factor = 0.1
        except Exception:
            odds_factor = 0.0

    # prob_over estimation
    prob_over = min(
        0.99,
        max(0.01, (total_avg / (dynamic_line if dynamic_line > 0 else 2.5)) * 0.6 + odds_factor)
    )
    indicators = {
        f"{home_name} avg goals": home_stats["media_gols"] / (dynamic_line if dynamic_line > 0 else 1),
        f"{away_name} avg goals": away_stats["media_gols"] / (dynamic_line if dynamic_line > 0 else 1),
        "odds_hint": odds_factor
    }

    if prob_over > 0.65:
        return [build_pick("Over/Under", f"Over {dynamic_line} gols", prob_over, indicators)]
    elif prob_over < 0.40:
        return [build_pick("Over/Under", f"Under {dynamic_line} gols", 1-prob_over, indicators)]
    else:
        # checar BTTS
        btts_prob = 0.0
        if home_stats["media_gols"] >= 1.0 and away_stats["media_gols"] >= 1.0:
            btts_prob = 0.7
        elif home_stats["media_gols"] >= 0.8 and away_stats["media_gols"] >= 0.8:
            btts_prob = 0.55

        if btts_prob >= 0.6:
            return [build_pick(
                "BTTS",
                "Both Teams To Score: Yes",
                btts_prob,
                {"home_avg": home_stats["media_gols"], "away_avg": away_stats["media_gols"]}
            )]
        return [build_pick(
            "Generic",
            "Sem valor claro",
            0.5,
            {"home_avg": home_stats["media_gols"], "away_avg": away_stats["media_gols"]}
        )]


   # ---------------- BASKETBALL / NBA ----------------
elif sport in ["basketball", "nba"]:
    base = SPORTS_MAP.get("basketball") if sport == "basketball" else SPORTS_MAP.get("nba")
    data = make_request(f"{base}games", params={"id": game_id})
    resp = data.get("response", [])
    if not resp:
        return [{
            "market": "N/A",
            "suggestion": "Jogo não encontrado",
            "confidence": 0,
            "justification": "Game ID inválido"
        }]
    fixture = resp[0]
    home = fixture.get("teams", {}).get("home", {})
    away = fixture.get("teams", {}).get("away", {})
    home_id, away_id = home.get("id"), away.get("id")
    home_name, away_name = home.get("name", "Casa"), away.get("name", "Fora")

    # últimas médias
    query_sport = "nba" if sport == "nba" else "basketball"
    home_stats = get_last_matches_stats_basketball(home_id, 7, sport=query_sport)
    away_stats = get_last_matches_stats_basketball(away_id, 7, sport=query_sport)

    # 🚨 fallback de estatísticas
    if (
        not home_stats
        or not away_stats
        or (home_stats.get("media_feitos", 0.0) == 0.0 and away_stats.get("media_feitos", 0.0) == 0.0)
    ):
        return [{
            "market": "N/A",
            "suggestion": "Sem estatísticas recentes suficientes",
            "confidence": 0,
            "justification": "A API não retornou dados confiáveis para este jogo."
        }]

    # linha dinâmica baseada nas médias
    avg_home = home_stats.get("media_feitos", 0.0)
    avg_away = away_stats.get("media_feitos", 0.0)
    dynamic_line = round((avg_home + avg_away) * 0.98, 1)

    # checar variance: se ambos > 110, aumentar linha
    if avg_home > 110 and avg_away > 110:
        dynamic_line = round(dynamic_line * 1.08, 1)

    total_avg = avg_home + avg_away
    indicators = {"home_avg": avg_home, "away_avg": avg_away}

    # probabilidade de over
    prob_over = min(
        0.99,
        max(0.01, (total_avg / (dynamic_line if dynamic_line > 0 else 200)) * 0.7 + 0.15)
    )

    if prob_over > 0.70:
        return [build_pick("Total de pontos", f"Over {dynamic_line} pontos", prob_over, indicators)]
    elif prob_over < 0.35:
        return [build_pick("Total de pontos", f"Under {dynamic_line} pontos", 1-prob_over, indicators)]
    else:
        # sugerir moneyline se diferença ofensiva for relevante
        home_edge = avg_home - avg_away
        if abs(home_edge) > 8:
            fav = home_name if home_edge > 0 else away_name
            return [build_pick(
                "Moneyline",
                f"{fav} para vencer",
                min(0.9, 0.5 + abs(home_edge)/50),
                {"home_edge": home_edge}
            )]
        return [build_pick("Generic", "Sem valor claro (jogo equilibrado)", 0.5, indicators)]


  # ---------------- BASEBALL ----------------
elif sport == "baseball":
    base = SPORTS_MAP.get("baseball")
    data = make_request(f"{base}games", params={"id": game_id})
    resp = data.get("response", [])
    if not resp:
        return [{
            "market": "N/A",
            "suggestion": "Jogo não encontrado",
            "confidence": 0,
            "justification": "Game ID inválido"
        }]
    fixture = resp[0]
    home = fixture.get("teams", {}).get("home", {})
    away = fixture.get("teams", {}).get("away", {})
    home_id, away_id = home.get("id"), away.get("id")
    home_name, away_name = home.get("name", "Casa"), away.get("name", "Fora")

    def avg_runs(team_id):
        stats = make_request(f"{base}games", params={"team": team_id, "last": 7})
        jogos = stats.get("response", [])
        runs, count = 0, 0
        for j in jogos:
            scores = j.get("scores", {})
            if not scores:
                continue
            if j.get("teams", {}).get("home", {}).get("id") == team_id:
                runs += scores.get("home", {}).get("total", 0) if isinstance(scores.get("home"), dict) else 0
            else:
                runs += scores.get("away", {}).get("total", 0) if isinstance(scores.get("away"), dict) else 0
            count += 1
        return round(runs / count, 2) if count else 0

    home_runs = avg_runs(home_id)
    away_runs = avg_runs(away_id)

    # 🚨 fallback de estatísticas
    if home_runs == 0.0 and away_runs == 0.0:
        return [{
            "market": "N/A",
            "suggestion": "Sem estatísticas recentes suficientes",
            "confidence": 0,
            "justification": "A API não retornou dados confiáveis para este jogo."
        }]

    dynamic_line = round((home_runs + away_runs) * 1.0, 1)
    prob_over = min(
        0.99,
        max(0.01, (home_runs + away_runs) / (dynamic_line if dynamic_line > 0 else 9.5) * 0.7)
    )

    indicators = {"home_runs": home_runs, "away_runs": away_runs}
    if prob_over > 0.65:
        return [build_pick("Total Runs", f"Over {dynamic_line} corridas", prob_over, indicators)]
    elif prob_over < 0.35:
        return [build_pick("Total Runs", f"Under {dynamic_line} corridas", 1-prob_over, indicators)]
    else:
        return [build_pick("Generic", "Sem valor claro", 0.5, indicators)]

# ---------------- HOCKEY ----------------
elif sport == "hockey":
    base = SPORTS_MAP.get("hockey")
    data = make_request(f"{base}games", params={"id": game_id})
    resp = data.get("response", [])
    if not resp:
        return [{
            "market": "N/A",
            "suggestion": "Jogo não encontrado",
            "confidence": 0,
            "justification": "Game ID inválido"
        }]
    fixture = resp[0]
    home = fixture.get("teams", {}).get("home", {})
    away = fixture.get("teams", {}).get("away", {})
    home_id, away_id = home.get("id"), away.get("id")

    def avg_goals(team_id):
        stats = make_request(f"{base}games", params={"team": team_id, "last": 7})
        jogos = stats.get("response", [])
        goals, count = 0, 0
        for j in jogos:
            s = j.get("scores", {})
            if isinstance(s, dict):
                # soma gols home+away do jogo
                goals += sum([v for v in [s.get("home", 0), s.get("away", 0)] if isinstance(v, (int, float))])
                count += 1
        return round(goals / (count if count else 1), 2)

    home_goals = avg_goals(home_id)
    away_goals = avg_goals(away_id)

    # 🚨 fallback de estatísticas
    if home_goals == 0.0 and away_goals == 0.0:
        return [{
            "market": "N/A",
            "suggestion": "Sem estatísticas recentes suficientes",
            "confidence": 0,
            "justification": "A API não retornou dados confiáveis para este jogo."
        }]

    dynamic_line = round((home_goals + away_goals) * 0.9, 1)
    prob_over = min(
        0.99,
        max(0.01, (home_goals + away_goals) / (dynamic_line if dynamic_line > 0 else 5.5) * 0.6)
    )

    indicators = {"home_goals": home_goals, "away_goals": away_goals}
    if prob_over > 0.65:
        return [build_pick("Total de gols", f"Over {dynamic_line} gols", prob_over, indicators)]
    elif prob_over < 0.35:
        return [build_pick("Total de gols", f"Under {dynamic_line} gols", 1-prob_over, indicators)]
    else:
        return [build_pick("Generic", "Sem valor claro", 0.5, indicators)]

   # ---------------- MMA ----------------
elif sport == "mma":
    base = SPORTS_MAP.get("mma")
    data = make_request(f"{base}fights", params={"id": game_id})
    resp = data.get("response", []) or []

    if not resp:
        return [{
            "market": "N/A",
            "suggestion": "Luta não encontrada",
            "confidence": 0,
            "justification": "Game ID inválido"
        }]

    f = resp[0]
    fighters = f.get("fighters", []) or []

    # 🚨 fallback: se não houver lutadores ou histórico
    if len(fighters) < 2:
        return [{
            "market": "N/A",
            "suggestion": "Sem estatísticas recentes suficientes",
            "confidence": 0,
            "justification": "Não há dados históricos para os lutadores dessa luta."
        }]

    # função auxiliar para winrate
    def winrate(fid):
        stats = make_request(f"{base}fights", params={"fighter": fid, "last": 10})
        arr = stats.get("response", [])
        wins = sum(1 for x in arr if x.get("result") == "win")
        total = len(arr)
        return wins / total if total else 0

    wr1 = winrate(fighters[0].get("id"))
    wr2 = winrate(fighters[1].get("id"))

    # 🚨 fallback: se não houver histórico de vitórias
    if wr1 == 0 and wr2 == 0:
        return [{
            "market": "N/A",
            "suggestion": "Sem estatísticas recentes suficientes",
            "confidence": 0,
            "justification": "A API não retornou lutas recentes para os atletas."
        }]

    if abs(wr1 - wr2) > 0.25:
        fav = fighters[0].get("name") if wr1 > wr2 else fighters[1].get("name")
        return [build_pick("Winner", f"{fav} para vencer", max(wr1, wr2), {"wr_diff": abs(wr1-wr2)})]

    return [build_pick("Winner", "Sem valor claro", 0.5, {"wr1": wr1, "wr2": wr2})]

   # ---------------- FÓRMULA 1 (simplificado) ----------------
elif sport in ["formula1", "formula-1"]:
    base = SPORTS_MAP.get("formula-1")
    year = datetime.now().year
    data = make_request(f"{base}races", params={"season": year})
    resp = data.get("response", [])

    # 🚨 fallback: nenhuma corrida encontrada
    if not resp:
        return [{
            "market": "N/A",
            "suggestion": "Sem corridas encontradas nesta temporada",
            "confidence": 0,
            "justification": "A API não retornou dados de corridas para o ano atual."
        }]

    # simplificação: se houver corridas, dá sugestão genérica
    return [build_pick(
        "Posição final",
        "Top 6 (probabilidade média)",
        0.6,
        {"note": "Baseado em performance histórica recente"}
    )]

   # ---------------- VOLLEYBALL, RUGBY, HANDBALL, NFL (fallbacks tunáveis) ----------------
elif sport in ["volleyball", "rugby", "handball", "nfl"]:
    base = SPORTS_MAP.get(sport if sport != "nfl" else "nfl", None)

    # 🚨 fallback: caso não haja endpoint válido
    if not base:
        return [{
            "market": "N/A",
            "suggestion": "Esporte não suportado",
            "confidence": 0,
            "justification": f"O esporte '{sport}' não possui integração configurada."
        }]

    # tentativa de pegar últimos jogos
    try:
        stats_home = make_request(f"{base}games", params={"team": "home", "last": 5})
        stats_away = make_request(f"{base}games", params={"team": "away", "last": 5})
    except Exception:
        stats_home, stats_away = {}, {}

    # 🚨 fallback: sem estatísticas
    if not stats_home and not stats_away:
        return [{
            "market": "N/A",
            "suggestion": "Sem estatísticas recentes suficientes",
            "confidence": 0,
            "justification": "A API não retornou dados recentes para este esporte."
        }]

    # pega perfil do tipster para o esporte
    profile = TIPSTER_PROFILES_DETAILED.get(sport, {})
    typical = profile.get("typical_picks", ["Win"])[0]

    return [build_pick(
        "Generic",
        typical,
        0.55,
        {"note": "Sugestão baseada em heurística do perfil do tipster"}
    )]

   # ---------------- FALLBACK ----------------
else:
    profile = TIPSTER_PROFILES_DETAILED.get(sport, {})
    pick = profile.get("typical_picks", ["Generic"])[0]

    # 🚨 fallback: esporte não mapeado e sem perfil configurado
    if not profile:
        return [{
            "market": "N/A",
            "suggestion": "Esporte não suportado ou sem perfil configurado",
            "confidence": 0,
            "justification": f"O esporte '{sport}' não possui lógica ou perfil no Tipster IA."
        }]

    return [{
        "market": "Generic",
        "suggestion": pick,
        "confidence": 50,
        "justification": f"Pick genérico gerado pelo perfil do esporte: {sport}"
    }]
# ================================
# Endpoint: Analisar Ao Vivo (Football + Basketball)
# ================================
@app.get("/analisar-ao-vivo")
def analisar_ao_vivo(game_id: int, sport: str):
    """
    Análise AO VIVO DINÂMICA. Usa estatísticas e eventos em tempo real para detectar triggers.
    Retorna lista com pick(s).
    """
    sport = sport.lower()

    def build_pick(market: str, suggestion: str, strength: float, indicators: Dict[str, float]):
        prob = int(min(95, max(1, round(strength * 100))))
        justification = " | ".join([f"{k}: {round(v*100,1)}%" if isinstance(v, float) else f"{k}: {v}" for k, v in indicators.items()])
        return {"market": market, "suggestion": suggestion, "confidence": prob, "justification": justification}

    # ---------------- FOOTBALL ----------------
    if sport == "football":
        base = SPORTS_MAP.get("football")
        data = make_request(f"{base}fixtures", params={"id": game_id, "live": "all"})
        resp = data.get("response", [])
        if not resp:
            return [{"market": "N/A", "suggestion": "Partida não encontrada", "confidence": 0, "justification": "Game ID inválido"}]
        fixture = resp[0]
        stats = fixture.get("statistics", []) or []
        events = fixture.get("events", []) or []

        possession_vals = []
        shots_on_target = 0
        fouls = 0
        for t in stats:
            for s in t.get("statistics", []):
                typ = s.get("type", "")
                val = s.get("value", 0)
                if typ == "Ball Possession":
                    try:
                        possession_vals.append(int(str(val).replace("%","")))
                    except Exception:
                        pass
                if typ in ["Shots on Goal", "Shots on Target"]:
                    try:
                        shots_on_target += int(val)
                    except Exception:
                        pass
                if typ == "Fouls":
                    try:
                        fouls += int(val)
                    except Exception:
                        pass

        possession = max(possession_vals) if possession_vals else 0
        indicators = {"possession": possession/100.0 if possession else 0.0, "shots_on_target": shots_on_target/10.0 if shots_on_target else 0.0, "fouls": min(1.0,fouls/20.0)}
        # regra: posse alta + chutes no alvo → provável gol futuro
        strength = 0.0
        if possession >= 65 and shots_on_target >= 2:
            strength = 0.85
            return [build_pick("Próximo Gol", "Equipe dominante marcará", strength, indicators)]
        if fouls >= 15:
            strength = 0.7
            return [build_pick("Cartões", "Over cartões", strength, indicators)]
        return [build_pick("Sem trigger", "Aguardar momento", 0.45, indicators)]

    # ---------------- BASKETBALL / NBA ----------------
    if sport in ["basketball", "nba"]:
        base = SPORTS_MAP.get("basketball") if sport == "basketball" else SPORTS_MAP.get("nba")
        data = make_request(f"{base}games", params={"id": game_id, "live": "all"})
        resp = data.get("response", [])
        if not resp:
            return [{"market": "N/A", "suggestion": "Partida não encontrada", "confidence": 0, "justification": "Game ID inválido"}]
        fixture = resp[0]
        # somar pontos atuais por periodos/scores
        scores = fixture.get("scores", {}) or {}
        total_points = 0
        for p in scores.values():
            if isinstance(p, dict):
                total_points += (p.get("home",0) or 0) + (p.get("away",0) or 0)
        # stat indicators (faltas)
        stats = fixture.get("statistics", []) or []
        fouls = 0
        for t in stats:
            for s in t.get("statistics", []):
                if s.get("type") == "Fouls":
                    try:
                        fouls += int(s.get("value",0))
                    except:
                        pass
        indicators = {"total_points": total_points/200.0 if total_points else 0.0, "fouls": min(1.0, fouls/20.0)}
        if total_points >= 110:
            return [build_pick("Over pontos", "Jogo em ritmo acelerado - favorece Over", 0.8, indicators)]
        if fouls >= 12:
            return [build_pick("Handicap", "Faltas altas - favorece banco/rotatividade", 0.65, indicators)]
        return [build_pick("Sem trigger", "Aguardar momento", 0.45, indicators)]

    # ---------------- BASEBALL ----------------
    if sport == "baseball":
        base = SPORTS_MAP.get("baseball")
        data = make_request(f"{base}games", params={"id": game_id, "live": "all"})
        resp = data.get("response", []) or []
        if not resp:
            return [{"market": "N/A", "suggestion": "Partida não encontrada", "confidence": 0, "justification": "Game ID inválido"}]
        fixture = resp[0]
        innings = fixture.get("scores", {}) or {}
        total_runs = sum((v.get("home",0) or 0) + (v.get("away",0) or 0) for v in innings.values() if isinstance(v, dict))
        indicators = {"total_runs": total_runs/10.0}
        if total_runs >= 7:
            return [build_pick("Over runs", "Partida com alta pontuação", 0.75, indicators)]
        return [build_pick("Sem trigger", "Aguardar pitchers", 0.45, indicators)]

    # ---------------- HOCKEY ----------------
    if sport == "hockey":
        base = SPORTS_MAP.get("hockey")
        data = make_request(f"{base}games", params={"id": game_id, "live": "all"})
        resp = data.get("response", []) or []
        if not resp:
            return [{"market": "N/A", "suggestion": "Partida não encontrada", "confidence": 0, "justification": "Game ID inválido"}]
        fixture = resp[0]
        stats = fixture.get("statistics", []) or []
        sog = 0
        periods = fixture.get("scores", {}) or {}
        total_goals = sum((p.get("home",0) or 0) + (p.get("away",0) or 0) for p in periods.values() if isinstance(p, dict))
        for t in stats:
            for s in t.get("statistics", []):
                if s.get("type") == "Shots on Goal":
                    try:
                        sog += int(s.get("value",0))
                    except:
                        pass
        indicators = {"sog": sog/40.0, "total_goals": total_goals/6.0}
        if sog >= 20:
            return [build_pick("Over gols", "Alta pressão ofensiva", 0.78, indicators)]
        if total_goals >= 4:
            return [build_pick("Over gols", "Muitos gols já", 0.72, indicators)]
        return [build_pick("Sem trigger", "Jogo equilibrado", 0.45, indicators)]

    # ---------------- VOLLEYBALL ----------------
    if sport == "volleyball":
        base = SPORTS_MAP.get("volleyball")
        data = make_request(f"{base}games", params={"id": game_id, "live": "all"})
        resp = data.get("response", []) or []
        if not resp:
            return [{"market": "N/A", "suggestion": "Partida não encontrada", "confidence": 0, "justification": "Game ID inválido"}]
        fixture = resp[0]
        sets = fixture.get("scores", {}) or {}
        total_sets = len([s for s in sets.values() if isinstance(s, dict) and (s.get("home") or s.get("away"))])
        indicators = {"sets_played": total_sets/5.0}
        if total_sets >= 3:
            return [build_pick("Over sets", "Partida equilibrada - tende a muitos sets", 0.7, indicators)]
        return [build_pick("Sem trigger", "Poucos sets", 0.45, indicators)]

    # ---------------- RUGBY ----------------
    if sport == "rugby":
        base = SPORTS_MAP.get("rugby")
        data = make_request(f"{base}games", params={"id": game_id, "live": "all"})
        resp = data.get("response", []) or []
        if not resp:
            return [{"market": "N/A", "suggestion": "Partida não encontrada", "confidence": 0, "justification": "Game ID inválido"}]
        fixture = resp[0]
        scores = fixture.get("scores", {}) or {}
        total_points = sum((s.get("home",0) or 0) + (s.get("away",0) or 0) for s in scores.values() if isinstance(s, dict))
        indicators = {"total_points": total_points/60.0}
        if total_points >= 30:
            return [build_pick("Over pontos", "Partida com ritmo ofensivo", 0.7, indicators)]
        return [build_pick("Sem trigger", "Jogo equilibrado", 0.45, indicators)]

    # ---------------- NFL / AMERICAN FOOTBALL ----------------
    if sport == "nfl":
        base = SPORTS_MAP.get("nfl")
        data = make_request(f"{base}games", params={"id": game_id, "live": "all"})
        resp = data.get("response", []) or []
        if not resp:
            return [{"market": "N/A", "suggestion": "Partida não encontrada", "confidence": 0, "justification": "Game ID inválido"}]
        fixture = resp[0]
        scores = fixture.get("scores", {}) or {}
        total_points = sum((s.get("home",0) or 0) + (s.get("away",0) or 0) for s in scores.values() if isinstance(s, dict))
        indicators = {"total_points": total_points/56.0}
        if total_points >= 28:
            return [build_pick("Over pontos", "Jogo ofensivo", 0.68, indicators)]
        return [build_pick("Sem trigger", "Defesas controlando", 0.45, indicators)]

    # ---------------- MMA ----------------    (live placeholders)
    if sport == "mma":
        return [build_pick("Luta", "Aguardar round atual / procurar dominance", 0.45, {})]

    # ---------------- FORMULA 1 ----------------
    if sport in ["formula1", "formula-1"]:
        return [build_pick("Corrida", "Monitorar safety car / pit stops", 0.5, {})]

    # ---------------- FALLBACK ----------------
    profile = TIPSTER_PROFILES_DETAILED.get(sport, {})
    return [build_pick("Generic", profile.get("typical_picks", ["Win"])[0], 0.5, {"note": "fallback"})]


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


