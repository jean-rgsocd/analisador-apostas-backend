# Filename: sports_betting_analyzer.py
# CORRIGIDO

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Dict, Any

app = FastAPI(title="Tipster IA - API-Sports")

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

# --- Configuração API-Sports ---
API_SPORTS_KEY = "85741d1d66385996de506a07e3f527d1"
API_BASES = {
    "football": "https://v3.football.api-sports.io",
    "basketball": "https://v3.basketball.api-sports.io",
    "american-football": "https://v3.american-football.api-sports.io" # <-- CORREÇÃO AQUI
}
HEADERS = {"x-apisports-key": API_SPORTS_KEY}

# ... (o resto do arquivo continua o mesmo)
# --- Função para GET na API ---
def call_api(sport: str, endpoint: str, params: dict = None):
    base = API_BASES.get(sport)
    if not base:
        raise HTTPException(status_code=400, detail=f"Esporte '{sport}' não suportado.")
    try:
        resp = requests.get(f"{base}{endpoint}", headers=HEADERS, params=params or {}, timeout=15)
        resp.raise_for_status()
        return resp.json().get("response", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na API-Sports: {e}")

# --- Endpoints de Ligas ---
@app.get("/ligas/football")
def get_football_leagues():
    data = call_api("football", "/leagues", {"type": "league", "current": "true"})
    leagues = [
        {"id": l["league"]["id"], "title": f"{l['league']['name']} ({l['country']['name']})"}
        for l in data if l.get("league") and l.get("country")
    ]
    return sorted(leagues, key=lambda x: x["title"])

@app.get("/ligas/extras")
def get_extra_leagues():
    return [
        {"id": 12, "title": "NBA", "sport": "basketball"},
        {"id": 16, "title": "NFL", "sport": "american-football"}
    ]

# --- Endpoint de Partidas ---
@app.get("/partidas/{sport}/{league_id}")
def get_games_by_league(sport: str, league_id: int):
    season = datetime.now().year
    data = call_api(sport, "/fixtures", {"league": league_id, "season": season})
    return [
        {
            "game_id": g["fixture"]["id"],
            "home": g["teams"]["home"]["name"],
            "away": g["teams"]["away"]["name"],
            "time": g["fixture"]["date"],
            "status": g["fixture"]["status"]["short"]
        }
        for g in data
    ]

# --- Perfil de análise do Tipster ---
def analyze_odds(sport: str, fixture_id: int):
    # A análise de Odds depende de uma estrutura de dados que pode variar.
    # Esta função busca por mercados comuns e retorna uma análise simples.
    data = call_api(sport, "/odds", {"fixture": fixture_id})
    if not data or not data[0].get("bookmakers"):
        return [{"market": "Indisponível", "justification": "As odds para este jogo ainda não foram publicadas.", "confidence": 0}]
    
    # Usando a primeira casa de apostas como referência (ex: Bet365)
    bookmaker = data[0]["bookmakers"][0]
    bets = bookmaker.get("bets", [])
    
    analysis_tips = []

    # Vencedor da Partida (Moneyline)
    winner_bet = next((b for b in bets if b["name"] in ("Match Winner", "Moneyline")), None)
    if winner_bet:
        home_odd = float(winner_bet["values"][0]["odd"])
        away_odd = float(winner_bet["values"][1]["odd"])
        fav_team = winner_bet["values"][0]["value"] if home_odd < away_odd else winner_bet["values"][1]["value"]
        fav_odd = min(home_odd, away_odd)
        if fav_odd < 1.6:
            analysis_tips.append({
                "market": "Vencedor da Partida",
                "suggestion": f"Vitória do {fav_team}",
                "justification": f"O mercado aponta um favoritismo claro para o {fav_team}, com odds de {fav_odd}, indicando alta probabilidade de vitória.",
                "confidence": 85
            })

    # Total de Pontos/Gols (Over/Under)
    total_bet = next((b for b in bets if "Over/Under" in b["name"]), None)
    if total_bet:
        line = total_bet["values"][0]["value"].replace("Over ", "")
        analysis_tips.append({
            "market": f"Total de Gols/Pontos (Acima/Abaixo de {line})",
            "suggestion": f"Analisar o Over {line}",
            "justification": f"A linha principal do mercado está em {line}. Jogos com times ofensivos tendem a superar essa marca (Over), enquanto times defensivos tendem a ficar abaixo (Under).",
            "confidence": 70
        })

    if not analysis_tips:
         return [{"market": "Análise Padrão", "justification": "Não foram encontrados mercados com alta probabilidade para análise automática. Recomenda-se uma análise manual das estatísticas.", "confidence": 0}]

    return analysis_tips

# --- Endpoint de Análise ---
@app.get("/analisar-pre-jogo")
def get_pre_game_analysis(game_id: int, sport: str):
    return analyze_odds(sport, game_id)

@app.get("/analisar-ao-vivo")
def get_live_analysis(game_id: int, sport: str):
    # Lógica de análise ao vivo pode ser mais complexa, usando estatísticas em tempo real
    # Por enquanto, retorna a mesma análise pré-jogo como placeholder
    return analyze_odds(sport, game_id)
