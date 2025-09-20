# Filename: sports_analyzer_live.py
# Versão 13.0 (Multi-Ligas Dinâmico)

import os
import requests
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - V13 Multi-Ligas")

# --- CORS ---
origins = [ "https://jean-rgsocd.github.io", "http://127.0.0.1:5500", "http://localhost:5500" ]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Configuração da API ---
API_KEY = "d6adc9f70174645bada5a0fb8ad3ac27"
THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"

# --- Cache ---
api_cache: Dict[str, tuple] = {}
CACHE_DURATION_SECONDS = 300 

# --- Função de Requisição Genérica ---
def make_odds_api_request(url: str, params: dict) -> list:
    params['apiKey'] = API_KEY
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"ERRO na chamada à API: {e}")
        return []

# --- NOVO ENDPOINT: Buscar Ligas de Futebol ---
@app.get("/ligas/football")
def get_football_leagues():
    cache_key = "all_sports"
    current_time = time.time()
    
    if cache_key in api_cache and (current_time - api_cache[cache_key][1]) < 3600: # Cache de 1 hora para as ligas
        all_sports = api_cache[cache_key][0]
    else:
        all_sports = make_odds_api_request(f"{THE_ODDS_API_BASE_URL}/sports", params={'all': 'true'})
        if all_sports:
            api_cache[cache_key] = (all_sports, current_time)

    if not all_sports:
        raise HTTPException(status_code=500, detail="Não foi possível buscar as ligas da API externa.")

    # Filtra apenas as ligas de futebol e formata para o front-end
    football_leagues = [
        {"key": sport['key'], "title": sport['title']}
        for sport in all_sports
        if sport.get('group') == 'Soccer' and sport.get('active', False)
    ]
    return sorted(football_leagues, key=lambda x: x['title'])


# --- ENDPOINT ALTERADO: Buscar Partidas por Liga ---
@app.get("/partidas/{league_key}")
def get_games_by_league(league_key: str):
    cache_key = league_key
    current_time = time.time()

    if cache_key in api_cache and (current_time - api_cache[cache_key][1]) < CACHE_DURATION_SECONDS:
        jogos_da_api = api_cache[cache_key][0]
    else:
        url = f"{THE_ODDS_API_BASE_URL}/sports/{league_key}/odds"
        params = {"regions": "us", "markets": "h2h,spreads,totals"}
        jogos_da_api = make_odds_api_request(url, params)
        if jogos_da_api:
            api_cache[cache_key] = (jogos_da_api, current_time)
            
    # Função de Normalização interna para simplificar
    def normalize(g):
        try:
            time_str = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M')
        except:
            time_str = g.get("commence_time", "Sem data")
        return {"game_id": g["id"], "home": g["home_team"], "away": g["away_team"], "time": time_str, "status": "NS"}

    return [normalize(g) for g in jogos_da_api]


# --- ENDPOINT ALTERADO: Análise por Liga e Jogo ---
@app.get("/analise/{league_key}/{game_id}")
def get_analysis_for_game(league_key: str, game_id: str):
    if league_key not in api_cache:
        raise HTTPException(status_code=404, detail="Cache para esta liga expirou. Por favor, selecione a liga novamente.")
        
    todos_os_jogos = api_cache[league_key][0]
    game_encontrado = next((g for g in todos_os_jogos if g.get("id") == game_id), None)

    if not game_encontrado:
        raise HTTPException(status_code=404, detail="Jogo não encontrado no cache. Tente recarregar a lista.")

    bookmakers = game_encontrado.get("bookmakers", [])
    if not bookmakers:
        return [{"market": "Aguardando Odds", "analysis": "Nenhuma casa de aposta (região US) ofereceu odds para este jogo ainda."}]

    bookmaker = bookmakers[0]
    markets = bookmaker.get("markets", [])
    analysis_report = []
    
    # Lógica de análise (H2H, Spreads, Totals) - permanece a mesma
    h2h_market = next((m for m in markets if m.get("key") == "h2h"), None)
    if h2h_market and len(h2h_market.get("outcomes", [])) >= 2:
        o = h2h_market["outcomes"]
        fav, und = (o[0], o[1]) if o[0]['price'] < o[1]['price'] else (o[1], o[0])
        analysis_report.append({"market": "Vencedor (Moneyline)", "analysis": f"O mercado aponta {fav['name']} como favorito. O valor pode residir em {und['name']} se fatores qualitativos superarem as probabilidades."})

    spread_market = next((m for m in markets if m.get("key") == "spreads"), None)
    if spread_market and len(spread_market.get("outcomes", [])) >= 2:
        o = spread_market["outcomes"]
        analysis_report.append({"market": "Handicap (Spread)", "analysis": f"A linha de handicap está definida em: {o[0]['name']} {o[0]['point']} e {o[1]['name']} {o[1]['point']}."})

    totals_market = next((m for m in markets if m.get("key") == "totals"), None)
    if totals_market and len(totals_market.get("outcomes", [])) >= 2:
        o = totals_market["outcomes"]
        analysis_report.append({"market": f"Total de Pontos/Gols (Over/Under {o[0]['point']})", "analysis": f"A linha principal está em {o[0]['point']}. Analisar o ritmo (pace) das equipes é essencial."})

    if not analysis_report:
        return [{"market": "Mercados Indisponíveis", "analysis": "Os mercados específicos (H2H, Spreads, Totals) não foram encontrados."}]

    return analysis_report
