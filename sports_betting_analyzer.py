# Filename: sports_analyzer_live.py
# Versão 16.1 (Futebol + NBA + NFL com Análises Inteligentes)

import requests
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

app = FastAPI(title="Tipster IA - V16.1 Global")

# --- CORS ---
origins = [
    "https://jean-rgsocd.github.io",
    "http://127.0.0.1:5500",
    "http://localhost:5500"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- Configuração da API ---
API_KEY = "d6adc9f70174645bada5a0fb8ad3ac27"
THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"

# --- Lista de Ligas de Futebol ---
FOOTBALL_LEAGUES = [
    {"key": "soccer_argentina_primera_division", "title": "Primera División (Argentina)"},
    {"key": "soccer_brazil_campeonato", "title": "Brasileirão Série A"},
    {"key": "soccer_brazil_serie_b", "title": "Brasileirão Série B"},
    {"key": "soccer_chile_campeonato", "title": "Primera División (Chile)"},
    {"key": "soccer_conmebol_libertadores", "title": "Copa Libertadores"},
    {"key": "soccer_conmebol_sudamericana", "title": "Copa Sul-Americana"},
    {"key": "soccer_epl", "title": "Premier League (Inglaterra)"},
    {"key": "soccer_efl_champ", "title": "Championship (Inglaterra)"},
    {"key": "soccer_spain_la_liga", "title": "La Liga (Espanha)"},
    {"key": "soccer_spain_segunda_division", "title": "La Liga 2 (Espanha)"},
    {"key": "soccer_italy_serie_a", "title": "Serie A (Itália)"},
    {"key": "soccer_italy_serie_b", "title": "Serie B (Itália)"},
    {"key": "soccer_germany_bundesliga", "title": "Bundesliga (Alemanha)"},
    {"key": "soccer_germany_bundesliga2", "title": "Bundesliga 2 (Alemanha)"},
    {"key": "soccer_france_ligue_one", "title": "Ligue 1 (França)"},
    {"key": "soccer_france_ligue_two", "title": "Ligue 2 (França)"},
    {"key": "soccer_portugal_primeira_liga", "title": "Primeira Liga (Portugal)"},
    {"key": "soccer_netherlands_eredivisie", "title": "Eredivisie (Holanda)"},
    {"key": "soccer_austria_bundesliga", "title": "Bundesliga (Áustria)"},
    {"key": "soccer_belgium_first_div", "title": "First Division (Bélgica)"},
    {"key": "soccer_denmark_superliga", "title": "Superliga (Dinamarca)"},
    {"key": "soccer_poland_ekstraklasa", "title": "Ekstraklasa (Polônia)"},
    {"key": "soccer_norway_eliteserien", "title": "Eliteserien (Noruega)"},
    {"key": "soccer_sweden_allsvenskan", "title": "Allsvenskan (Suécia)"},
    {"key": "soccer_sweden_superettan", "title": "Superettan (Suécia)"},
    {"key": "soccer_turkey_super_lig", "title": "Super Lig (Turquia)"},
    {"key": "soccer_greece_super_league", "title": "Super League (Grécia)"},
    {"key": "soccer_uefa_champs_league", "title": "UEFA Champions League"},
    {"key": "soccer_uefa_europa_league", "title": "UEFA Europa League"},
    {"key": "soccer_fifa_world_cup", "title": "Copa do Mundo (FIFA)"},
    {"key": "soccer_usa_mls", "title": "MLS (EUA)"},
    {"key": "soccer_mexico_ligamx", "title": "Liga MX (México)"},
    {"key": "soccer_australia_aleague", "title": "A-League (Austrália)"},
    {"key": "soccer_china_superleague", "title": "Super League (China)"},
    {"key": "soccer_japan_j_league", "title": "J League (Japão)"},
    {"key": "soccer_korea_kleague1", "title": "K League 1 (Coréia do Sul)"}
]

# --- Ligas Extras ---
EXTRA_LEAGUES = [
    {"key": "basketball_nba", "title": "NBA"},
    {"key": "americanfootball_nfl", "title": "NFL"}
]

# --- Cache ---
api_cache: Dict[str, tuple] = {}
CACHE_DURATION_SECONDS = 300

# --- Função para chamada na API ---
def make_odds_api_request(url: str, params: dict) -> list:
    params['apiKey'] = API_KEY
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"ERRO na chamada à API: {e}")
        return []

# --- Endpoints de Ligas ---
@app.get("/ligas/football")
def get_football_leagues():
    return sorted(FOOTBALL_LEAGUES, key=lambda x: x['title'])

@app.get("/ligas/extras")
def get_extra_leagues():
    return EXTRA_LEAGUES

# --- Endpoint de Partidas ---
@app.get("/partidas/{league_key}")
def get_games_by_league(league_key: str):
    cache_key = league_key
    now = time.time()

    if cache_key in api_cache and (now - api_cache[cache_key][1]) < CACHE_DURATION_SECONDS:
        jogos_da_api = api_cache[cache_key][0]
    else:
        url = f"{THE_ODDS_API_BASE_URL}/sports/{league_key}/odds"
        params = {"regions": "us", "markets": "h2h,spreads,totals"}
        jogos_da_api = make_odds_api_request(url, params)
        if jogos_da_api:
            api_cache[cache_key] = (jogos_da_api, now)

    def normalize(g):
        try:
            time_str = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M')
        except:
            time_str = g.get("commence_time", "Sem data")
        return {
            "game_id": g["id"],
            "home": g["home_team"],
            "away": g["away_team"],
            "time": time_str,
            "status": "NS"
        }

    return [normalize(g) for g in jogos_da_api]

# --- Endpoint de Análise ---
@app.get("/analise/{league_key}/{game_id}")
def get_analysis_for_game(league_key: str, game_id: str):
    if league_key not in api_cache:
        get_games_by_league(league_key)
        if league_key not in api_cache:
            raise HTTPException(status_code=404, detail="Cache expirou. Recarregue a liga.")

    jogos = api_cache[league_key][0]
    game = next((g for g in jogos if g.get("id") == game_id), None)
    if not game:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")

    bookmakers = game.get("bookmakers", [])
    if not bookmakers:
        return [{"market": "Aguardando Odds", "analysis": "Nenhuma casa (região US) liberou odds ainda."}]

    bookmaker = bookmakers[0]
    markets = bookmaker.get("markets", [])
    analysis_report = []

    # --- Moneyline ---
    h2h = next((m for m in markets if m.get("key") == "h2h"), None)
    if h2h and len(h2h.get("outcomes", [])) >= 2:
        o = h2h["outcomes"]
        fav, under = (o[0], o[1]) if o[0]['price'] < o[1]['price'] else (o[1], o[0])
        fav_prob = 100 / fav['price']
        under_prob = 100 / under['price']
        if under_prob * 1.2 > (100 - fav_prob):  # azarão com possível valor
            analysis_report.append({
                "market": "Vencedor (Moneyline)",
                "analysis": f"{fav['name']} é favorito pelo mercado. Mas {under['name']} pode ter valor com odd {under['price']}."
            })
        else:
            analysis_report.append({
                "market": "Vencedor (Moneyline)",
                "analysis": f"O mercado aponta {fav['name']} como favorito com odd {fav['price']}."
            })

    # --- Handicap ---
    spread = next((m for m in markets if m.get("key") == "spreads"), None)
    if spread and len(spread.get("outcomes", [])) >= 2:
        o = spread["outcomes"]
        analysis_report.append({
            "market": "Handicap (Spread)",
            "analysis": f"A linha está {o[0]['name']} {o[0]['point']} vs {o[1]['name']} {o[1]['point']}. "
                        f"Mercado espera equilíbrio ajustado, atenção se uma equipe tem histórico de superar spreads."
        })

    # --- Totais ---
    totals = next((m for m in markets if m.get("key") == "totals"), None)
    if totals and len(totals.get("outcomes", [])) >= 2:
        o = totals["outcomes"]
        linha = o[0]['point']
        analysis_report.append({
            "market": f"Total (Over/Under {linha})",
            "analysis": f"Linha em {linha}. Se ataques são fortes → tendência Over; se defesas sólidas → Under."
        })

    if not analysis_report:
        return [{"market": "Mercados Indisponíveis", "analysis": "Nenhum mercado encontrado (H2H, Spreads, Totals)."}]

    return analysis_report
