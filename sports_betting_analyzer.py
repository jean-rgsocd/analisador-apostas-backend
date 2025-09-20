# Filename: sports_analyzer_live.py
# Versão 12.1 (Sniper Mode Resiliente)

import os
import requests
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - Sniper Mode V12.1")

# -------------------------------
# CORS
# -------------------------------
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
    allow_headers=["*"],
)

# -------------------------------
# Configuração da API
# -------------------------------
API_KEY = "d6adc9f70174645bada5a0fb8ad3ac27"
BASE_URL = "https://api.the-odds-api.com/v4/sports"
SPORTS_MAP = {
    "football": "soccer_epl",
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba"
}

# -------------------------------
# Implementação do Cache
# -------------------------------
api_cache: Dict[str, tuple] = {}
CACHE_DURATION_SECONDS = 300

# -------------------------------
# Função de Requisição com Cache
# -------------------------------
def make_request_with_cache(sport_key: str) -> list:
    current_time = time.time()
    
    if sport_key in api_cache and (current_time - api_cache[sport_key][1]) < CACHE_DURATION_SECONDS:
        print(f"[Cache HIT] Retornando dados em cache para {sport_key}.")
        return api_cache[sport_key][0]

    print(f"[Cache MISS] Buscando novos dados da API para {sport_key}.")
    url = f"{BASE_URL}/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        jogos_da_api = resp.json()
        api_cache[sport_key] = (jogos_da_api, current_time)
        return jogos_da_api
    except requests.RequestException as e:
        print(f"[make_request] ERRO para {sport_key}: {e}")
        return []

# -------------------------------
# Função de Normalização
# -------------------------------
def normalize_odds_response(g: dict) -> Dict[str, Any]:
    try:
        # O 'Z' no final indica UTC (Zulu time), o replace garante a compatibilidade
        game_time = datetime.fromisoformat(g.get("commence_time", "").replace("Z", "+00:00"))
        time_str = game_time.strftime('%Y-%m-%d %H:%M')
    except (ValueError, TypeError):
        time_str = g.get("commence_time", "Sem data")

    return {
        "game_id": g.get("id"),
        "home": g.get("home_team"),
        "away": g.get("away_team"),
        "time": time_str,
        "status": "NS", # Not Started
    }

# -------------------------------
# Endpoint Principal de Partidas
# -------------------------------
@app.get("/partidas/{sport_name}")
def get_upcoming_games_by_sport(sport_name: str):
    sport_key = SPORTS_MAP.get(sport_name.lower())
    if not sport_key:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    jogos_da_api = make_request_with_cache(sport_key)
    jogos_normalizados = [normalize_odds_response(g) for g in jogos_da_api]
    return jogos_normalizados

# -------------------------------
# Endpoint de Análise (COM A CORREÇÃO FINAL)
# -------------------------------
@app.get("/analise/{sport_name}/{game_id}")
def get_analysis_for_game(sport_name: str, game_id: str):
    sport_key = SPORTS_MAP.get(sport_name.lower())
    if not sport_key:
        raise HTTPException(status_code=404, detail="Esporte não encontrado")

    if sport_key not in api_cache:
        make_request_with_cache(sport_key)
        
    todos_os_jogos = api_cache.get(sport_key, ([], 0))[0]
    
    game_encontrado = next((g for g in todos_os_jogos if g.get("id") == game_id), None)

    if not game_encontrado:
        raise HTTPException(status_code=404, detail="ID do jogo não encontrado no cache. Tente recarregar a lista de jogos.")

    # -------> INÍCIO DA CORREÇÃO <-------
    bookmakers = game_encontrado.get("bookmakers", [])
    if not bookmakers:
        # Se a lista de bookmakers estiver VAZIA, retorna a mensagem amigável em vez de quebrar.
        return [{"market": "Aguardando Odds", "analysis": "Nenhuma casa de aposta (região US) ofereceu odds para este jogo ainda. Mercados indisponíveis."}]
    # -------> FIM DA CORREÇÃO <-------

    bookmaker = bookmakers[0] # Agora é seguro pegar o primeiro item
    markets = bookmaker.get("markets", [])
    analysis_report = []
    
    # Análise H2H (Vencedor)
    h2h_market = next((m for m in markets if m.get("key") == "h2h"), None)
    if h2h_market:
        outcomes = h2h_market.get("outcomes", [])
        if len(outcomes) >= 2:
            team1, price1 = outcomes[0]['name'], outcomes[0]['price']
            team2, price2 = outcomes[1]['name'], outcomes[1]['price']
            favorito = team1 if price1 < price2 else team2
            underdog = team2 if price1 < price2 else team1
            analysis_report.append({
                "market": "Vencedor (Moneyline)",
                "analysis": f"O mercado aponta {favorito} como favorito. O valor pode residir em {underdog} se fatores qualitativos superarem as probabilidades."
            })

    # (O restante do código de análise para spreads e totals continua o mesmo)
    spread_market = next((m for m in markets if m.get("key") == "spreads"), None)
    if spread_market:
        outcomes = spread_market.get("outcomes", [])
        if len(outcomes) >= 2:
            team1_spread = f"{outcomes[0]['name']} {outcomes[0]['point']}"
            team2_spread = f"{outcomes[1]['name']} {outcomes[1]['point']}"
            analysis_report.append({ "market": "Handicap (Spread)", "analysis": f"A linha de handicap está definida em: {team1_spread} e {team2_spread}." })

    totals_market = next((m for m in markets if m.get("key") == "totals"), None)
    if totals_market:
        outcomes = totals_market.get("outcomes", [])
        if len(outcomes) >= 2:
            over_under_points = outcomes[0]['point']
            analysis_report.append({ "market": f"Total de Pontos/Gols (Over/Under {over_under_points})", "analysis": f"A linha principal está em {over_under_points}. Analisar o ritmo (pace) das equipes é essencial." })

    if not analysis_report:
        return [{"market": "Mercados Indisponíveis", "analysis": "Apesar de haver odds, os mercados específicos (H2H, Spreads, Totals) não foram encontrados para este jogo."}]

    return analysis_report
