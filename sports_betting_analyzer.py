# Filename: sports_analyzer_live.py
# Versão 12.0 (Sniper Mode com Cache)

import os
import requests
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - Sniper Mode V12")

# -------------------------------
# MELHORIA 1: CORS Limpo
# -------------------------------
# Apenas as origens que realmente acessam a API. O servidor não precisa de permissão para si mesmo.
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
API_KEY = "d6adc9f70174645bada5a0fb8ad3ac27" # Sua chave da The Odds API
BASE_URL = "https://api.the-odds-api.com/v4/sports"
SPORTS_MAP = {
    "football": "soccer_epl",
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba"
}

# -------------------------------
# MELHORIA 2: Implementação do Cache
# -------------------------------
# Usaremos um dicionário para guardar os dados dos jogos e o tempo da última busca.
# A chave será o 'sport_key' (ex: 'soccer_epl').
# O valor será uma tupla: (lista_de_jogos, timestamp_da_busca)
api_cache: Dict[str, tuple] = {}
CACHE_DURATION_SECONDS = 300  # 5 minutos. Os dados serão atualizados a cada 5 minutos.

# -------------------------------
# Função de Requisição (Agora com Cache)
# -------------------------------
def make_request_with_cache(sport_key: str) -> list:
    """
    Busca jogos da API, mas primeiro verifica nosso cache para evitar chamadas repetidas.
    """
    current_time = time.time()
    
    # Verifica se já temos dados para esse esporte e se eles não são muito antigos
    if sport_key in api_cache and (current_time - api_cache[sport_key][1]) < CACHE_DURATION_SECONDS:
        print(f"[Cache HIT] Retornando dados em cache para {sport_key}.")
        return api_cache[sport_key][0] # Retorna a lista de jogos do cache

    # Se não tem no cache ou os dados são antigos, busca na API
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
        
        # Guarda os novos dados e o tempo atual no cache
        api_cache[sport_key] = (jogos_da_api, current_time)
        
        return jogos_da_api
    except requests.RequestException as e:
        print(f"[make_request] ERRO para {sport_key}: {e}")
        return []

# -------------------------------
# Função de Normalização (Sem alterações)
# -------------------------------
def normalize_odds_response(g: dict) -> Dict[str, Any]:
    try:
        game_time = datetime.fromisoformat(g.get("commence_time").replace("Z", "+00:00"))
        time_str = game_time.strftime('%Y-%m-%d %H:%M')
    except:
        time_str = g.get("commence_time")

    return {
        "game_id": g.get("id"),
        "home": g.get("home_team"),
        "away": g.get("away_team"),
        "time": time_str,
        "status": "NS",
    }

# -------------------------------
# Endpoint Principal de Partidas (Agora usa o cache)
# -------------------------------
@app.get("/partidas/{sport_name}")
def get_upcoming_games_by_sport(sport_name: str):
    sport_key = SPORTS_MAP.get(sport_name.lower())
    if not sport_key:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    # A chamada agora é para a função com cache
    jogos_da_api = make_request_with_cache(sport_key)
    jogos_normalizados = [normalize_odds_response(g) for g in jogos_da_api]
    return jogos_normalizados

# -------------------------------
# Endpoint de Análise (AGORA USA O CACHE, MUITO MAIS RÁPIDO E SEGURO)
# -------------------------------
@app.get("/analise/{sport_name}/{game_id}")
def get_analysis_for_game(sport_name: str, game_id: str):
    sport_key = SPORTS_MAP.get(sport_name.lower())
    if not sport_key:
        raise HTTPException(status_code=404, detail="Esporte não encontrado")

    # Em vez de chamar a API de novo, busca os jogos do nosso cache!
    if sport_key not in api_cache:
        # Se por algum motivo o cache estiver vazio, força uma busca
        make_request_with_cache(sport_key)
        
    todos_os_jogos = api_cache.get(sport_key, ([], 0))[0]
    
    for game in todos_os_jogos:
        if game.get("id") == game_id:
            bookmaker = game.get("bookmakers", [{}])[0]
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

            # Análise Spreads (Handicap)
            spread_market = next((m for m in markets if m.get("key") == "spreads"), None)
            if spread_market:
                outcomes = spread_market.get("outcomes", [])
                if len(outcomes) >= 2:
                    team1_spread = f"{outcomes[0]['name']} {outcomes[0]['point']}"
                    team2_spread = f"{outcomes[1]['name']} {outcomes[1]['point']}"
                    analysis_report.append({
                        "market": "Handicap (Spread)",
                        "analysis": f"A linha de handicap está definida em: {team1_spread} e {team2_spread}."
                    })

            # Análise Totals (Over/Under)
            totals_market = next((m for m in markets if m.get("key") == "totals"), None)
            if totals_market:
                outcomes = totals_market.get("outcomes", [])
                if len(outcomes) >= 2:
                    over_under_points = outcomes[0]['point']
                    analysis_report.append({
                        "market": f"Total de Pontos/Gols (Over/Under {over_under_points})",
                        "analysis": f"A linha principal está em {over_under_points}. Analisar o ritmo (pace) das equipes e o poderio ofensivo/defensivo é essencial para encontrar valor."
                    })

            if not analysis_report:
                # Agora, em vez de um erro genérico, damos uma resposta clara
                return [{"market": "Aguardando Odds", "analysis": "Os mercados para este jogo ainda não foram abertos ou não estão disponíveis na API. Tente novamente mais perto da data da partida."}]

            return analysis_report
            
    # Se o loop terminar e não achar o jogo, algo deu muito errado.
    raise HTTPException(status_code=404, detail="ID do jogo não encontrado no cache. Tente recarregar a lista de jogos.")
