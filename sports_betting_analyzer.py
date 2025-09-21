# Filename: tipster.py
# Tipster IA - Multi-Esporte (Futebol + NBA + NFL) via API-Sports

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
    "nfl": "https://v3.american-football.api-sports.io"
}
HEADERS = {"x-apisports-key": API_SPORTS_KEY}

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
        {"id": 16, "title": "NFL", "sport": "nfl"}
    ]

# --- Endpoint de Partidas ---
@app.get("/partidas/{sport}/{league_id}")
def get_games_by_league(sport: str, league_id: int):
    season = datetime.now().year
    data = call_api(sport, "/fixtures", {"league": league_id, "season": season})
    return [
        {
            "fixture_id": g["fixture"]["id"],
            "home": g["teams"]["home"]["name"],
            "away": g["teams"]["away"]["name"],
            "time": g["fixture"]["date"],
            "status": g["fixture"]["status"]["short"]
        }
        for g in data
    ]

# --- Perfil de análise do Tipster ---
def analyze_odds(sport: str, markets: list):
    analysis = []

    # Futebol e NBA → Moneyline
    if sport in ["football", "basketball"]:
        h2h = next((m for m in markets if m.get("name") in ["Match Winner", "Moneyline"]), None)
        if h2h and len(h2h.get("values", [])) >= 2:
            fav = h2h["values"][0]
            under = h2h["values"][1]
            analysis.append({
                "market": "Vencedor (Moneyline)",
                "analysis": f"O mercado aponta {fav['value']} como favorito. {under['value']} pode surpreender."
            })

    # NFL → Spread tem mais peso
    if sport == "nfl" or sport == "basketball":
        spread = next((m for m in markets if "Handicap" in m.get("name", "") or "Spread" in m.get("name", "")), None)
        if spread and len(spread.get("values", [])) >= 2:
            lines = [v["value"] for v in spread["values"]]
            analysis.append({
                "market": "Handicap (Spread)",
                "analysis": f"Linhas oferecidas: {lines}. Mercado espera equilíbrio, mas times com histórico de superar spreads merecem atenção."
            })

    # Totais (Over/Under)
    totals = next((m for m in markets if "Over/Under" in m.get("name", "")), None)
    if totals and len(totals.get("values", [])) >= 2:
        linha = totals["values"][0]["value"]
        analysis.append({
            "market": f"Total (Over/Under {linha})",
            "analysis": f"Linha em {linha}. Se ataques são fortes → Over; se defesas sólidas → Under."
        })

    if not analysis:
        return [{"market": "Mercados Indisponíveis", "analysis": "Nenhum mercado válido encontrado."}]
    return analysis

# --- Endpoint de Análise ---
@app.get("/analise/{sport}/{fixture_id}")
def get_analysis_for_game(sport: str, fixture_id: int):
    data = call_api(sport, "/odds", {"fixture": fixture_id})
    if not data:
        return [{"market": "Odds indisponíveis", "analysis": "Nenhuma casa liberou odds ainda."}]

    bookmakers = data[0].get("bookmakers", [])
    if not bookmakers:
        return [{"market": "Aguardando Odds", "analysis": "Ainda não há odds publicadas para este jogo."}]

    markets = bookmakers[0].get("bets", [])
    return analyze_odds(sport, markets)
