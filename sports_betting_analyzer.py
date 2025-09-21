# Filename: sports_betting_analyzer.py
# VERSÃO FINAL CORRIGIDA - Usando o NOME do país para ligas

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - API-Sports V2.2 com Cache")

# --- CACHE SIMPLES (em memória) ---
cache: Dict[str, Any] = {}
CACHE_DURATION_MINUTES = 60

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
HEADERS = {"x-apisports-key": API_SPORTS_KEY}

def get_season_for_sport(sport: str) -> str:
    now = datetime.now()
    year = now.year
    if sport == "basketball":
        return f"{year - 1}-{year}" if now.month < 10 else f"{year}-{year + 1}"
    return str(year)

@app.get("/paises/football")
def get_football_countries() -> List[Dict[str, str]]:
    cache_key = "countries_football"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]:
        return cache[cache_key]["data"]

    url = "https://v3.football.api-sports.io/countries"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json().get("response", [])
        countries = [{"name": c["name"], "code": c["code"]} for c in data if c.get("code")]
        sorted_countries = sorted(countries, key=lambda x: x["name"])
        
        cache[cache_key] = {"data": sorted_countries, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
        return sorted_countries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar países: {e}")

# --- Endpoint de Ligas (com Parâmetro CORRIGIDO) ---
@app.get("/ligas/football/{country_name}") # Recebe o NOME do país, não o código
def get_leagues_by_country(country_name: str) -> List[Dict[str, Any]]:
    cache_key = f"leagues_football_{country_name}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]:
        return cache[cache_key]["data"]

    url = "https://v3.football.api-sports.io/leagues"
    # <-- CORREÇÃO PRINCIPAL AQUI: o parâmetro é 'country' e vai receber o nome completo
    params = {"country": country_name, "season": get_season_for_sport("football")}
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json().get("response", [])
        leagues = [{"id": l["league"]["id"], "name": l["league"]["name"]} for l in data if l.get("league")]
        sorted_leagues = sorted(leagues, key=lambda x: x["name"])
        
        cache[cache_key] = {"data": sorted_leagues, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
        return sorted_leagues
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar ligas: {e}")

# --- Endpoint de Partidas (com Cache) ---
@app.get("/partidas/{sport}/{league_id}")
def get_games_by_league(sport: str, league_id: str) -> List[Dict[str, Any]]:
    season = get_season_for_sport(sport)
    cache_key = f"games_{sport}_{league_id}_{season}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]:
        return cache[cache_key]["data"]
    
    try:
        games_data = []
        if sport == "football":
            url = "https://v3.football.api-sports.io/fixtures"
            params = {"league": league_id, "season": season, "next": "15"}
            response = requests.get(url, headers=HEADERS, params=params).json().get("response", [])
            games_data = [{"game_id": g["fixture"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["fixture"]["date"], "status": g["fixture"]["status"]["short"]} for g in response]

        elif sport == "basketball":
            url = "https://v2.nba.api-sports.io/games"
            params = {"league": "standard", "season": season}
            response = requests.get(url, headers=HEADERS, params=params).json().get("response", [])
            games_data = [{"game_id": g["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["visitors"]["name"], "time": g["date"]["start"], "status": g["status"]["short"]} for g in response]

        elif sport == "american-football":
            url = "https://v1.american-football.api-sports.io/fixtures"
            params = {"league": "1", "season": season}
            response = requests.get(url, headers=HEADERS, params=params).json().get("response", [])
            games_data = [{"game_id": g["fixture"]["id"], "home": g["teams"]["home"]["name"], "away": g["teams"]["away"]["name"], "time": g["fixture"]["date"], "status": g["fixture"]["status"]["short"]} for g in response]
            
        else:
            raise HTTPException(status_code=400, detail="Esporte não suportado")
        
        cache[cache_key] = {"data": games_data, "expiry": datetime.now() + timedelta(minutes=CACHE_DURATION_MINUTES)}
        return games_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar jogos: {e}")

# (O resto do arquivo não muda)

def call_any_api(url: str, params: dict):
    try:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        return resp.json().get("response", [])
    except Exception as e:
        print(f"Erro na chamada da API: {e}")
        return []

@app.get("/analisar-pre-jogo")
def get_pre_game_analysis(game_id: int, sport: str):
    params = {"fixture": game_id} if sport == "football" else {"id": game_id}
    url = ""
    if sport == "football": url = "https://v3.football.api-sports.io/odds"
    elif sport == "basketball": url = "https://v2.nba.api-sports.io/odds"
    elif sport == "american-football": url = "https://v1.american-football.api-sports.io/odds"
    else: return []

    data = call_any_api(url, params)
    
    if not data or not data[0].get("bookmakers"):
        return [{"market": "Indisponível", "suggestion": "N/A", "justification": "As odds para este jogo ainda não foram publicadas.", "confidence": 0}]
    
    bookmaker = data[0]["bookmakers"][0]
    bets = bookmaker.get("bets", [])
    analysis_tips = []

    winner_bet = next((b for b in bets if b["name"] in ("Match Winner", "Moneyline")), None)
    if winner_bet and len(winner_bet.get("values", [])) >= 2:
        home_odd = float(winner_bet["values"][0]["odd"])
        away_odd = float(winner_bet["values"][1]["odd"])
        fav_team = winner_bet["values"][0]["value"] if home_odd < away_odd else winner_bet["values"][1]["value"]
        fav_odd = min(home_odd, away_odd)
        if fav_odd < 1.7: analysis_tips.append({"market": "Vencedor da Partida", "suggestion": f"Vitória do {fav_team}", "justification": f"O mercado aponta um favoritismo claro para o {fav_team}, com odds de {fav_odd}.", "confidence": 85})

    total_bet = next((b for b in bets if "Over/Under" in b["name"]), None)
    if total_bet and len(total_bet.get("values", [])) > 0:
        line = total_bet["values"][0]["value"].replace("Over ", "")
        analysis_tips.append({"market": f"Total de Gols/Pontos (Acima/Abaixo de {line})", "suggestion": f"Analisar o Over {line}", "justification": f"A linha principal está em {line}. Times ofensivos tendem a superar essa marca.", "confidence": 70})

    if not analysis_tips:
         return [{"market": "Análise Padrão", "suggestion": "N/A", "justification": "Não foram encontrados mercados com alta probabilidade para análise automática.", "confidence": 0}]

    return analysis_tips
