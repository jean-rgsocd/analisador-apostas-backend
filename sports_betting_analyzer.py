# Filename: sports_analyzer_live.py
# Versão 11.0 (Sniper Mode)

import os
import requests
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - Sniper Mode")

# -------------------------------
# CORS
# -------------------------------
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

# -------------------------------
# Configuração da API
# -------------------------------
API_KEY = "d6adc9f70174645bada5a0fb8ad3ac27"
BASE_URL = "https://api.the-odds-api.com/v4/sports"

# Mapeamento de esportes para as chaves da The Odds API
SPORTS_MAP = {
    "football": "soccer_epl",
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba"
}

# -------------------------------
# Função de Requisição (Ampliada)
# -------------------------------
def make_request(sport_key: str) -> list:
    """Busca jogos futuros para um esporte específico com múltiplos mercados."""
    url = f"{BASE_URL}/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals",  # Busca por Vencedor, Handicap e Totais
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[make_request] erro para {sport_key}: {e}")
        return []

# -------------------------------
# Função de Normalização
# -------------------------------
def normalize_odds_response(g: dict) -> Dict[str, Any]:
    """Normaliza a resposta da The Odds API para o nosso front-end."""
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
# Endpoint Principal de Partidas
# -------------------------------
@app.get("/partidas/{sport_name}")
def get_upcoming_games_by_sport(sport_name: str):
    """Busca jogos futuros para o esporte específico solicitado."""
    sport_name = sport_name.lower()
    sport_key = SPORTS_MAP.get(sport_name)
    
    if not sport_key:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    jogos_da_api = make_request(sport_key)
    jogos_normalizados = [normalize_odds_response(g) for g in jogos_da_api]
    return jogos_normalizados

# -------------------------------
# Endpoint de Análise (Motor "Sniper")
# -------------------------------
@app.get("/analise/{sport_name}/{game_id}")
def get_analysis_for_game(sport_name: str, game_id: str):
    """Busca e analisa as odds para um jogo específico."""
    sport_key = SPORTS_MAP.get(sport_name.lower())
    if not sport_key:
        raise HTTPException(status_code=404, detail="Esporte não encontrado")

    todos_os_jogos = make_request(sport_key)
    
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
                    team1 = outcomes[0]['name']
                    price1 = outcomes[0]['price']
                    team2 = outcomes[1]['name']
                    price2 = outcomes[1]['price']
                    
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
                        "analysis": f"A linha de handicap está definida em: {team1_spread} e {team2_spread}. A análise de matchups chave é crucial para determinar quem cobrirá o spread."
                    })

            # Análise Totals (Over/Under)
            totals_market = next((m for m in markets if m.get("key") == "totals"), None)
            if totals_market:
                outcomes = totals_market.get("outcomes", [])
                if len(outcomes) >= 2:
                    over_under_points = outcomes[0]['point']
                    over_price = outcomes[0]['price']
                    under_price = outcomes[1]['price']
                    analysis_report.append({
                        "market": "Total de Pontos/Gols (Over/Under)",
                        "analysis": f"A linha principal está em {over_under_points} pontos/gols. O mercado precifica o Over em {over_price} e o Under em {under_price}, indicando a expectativa de ritmo de jogo."
                    })

            if not analysis_report:
                raise HTTPException(status_code=404, detail="Mercados de análise não encontrados para este jogo.")

            return analysis_report
            
    raise HTTPException(status_code=404, detail="Jogo não encontrado na lista de partidas futuras.")
