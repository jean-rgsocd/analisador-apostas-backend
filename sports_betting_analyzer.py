# sports_betting_analyzer.py
# Backend FastAPI para Tipster IA (Futebol / NBA / NFL)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests, traceback

app = FastAPI(title="Tipster IA - API")

# CORS (liberar para seu frontend)
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Config (corrigida para a chave que você usou no curl) ---
API_SPORTS_KEY = "7baa5e00c8ae57d0e6240f790c6840dd"

API_HOSTS = {
    "football": "v3.football.api-sports.io",
    "basketball": "v2.nba.api-sports.io",
    "american-football": "v1.american-football.api-sports.io"
}

API_URLS = {
    "football": "https://v3.football.api-sports.io",
    "basketball": "https://v2.nba.api-sports.io",
    "american-football": "https://v1.american-football.api-sports.io"
}

HEADERS = {
    "x-rapidapi-key": API_SPORTS_KEY,
}

def fetch_api_data(sport: str, endpoint: str, params: dict) -> List[Dict[str, Any]]:
    if sport not in API_URLS:
        return []
    headers = HEADERS.copy()
    headers['x-rapidapi-host'] = API_HOSTS[sport]
    url = f"{API_URLS[sport]}/{endpoint}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        j = resp.json()
        return j.get("response", [])
    except requests.RequestException as e:
        print(f"Erro fetch {url}: {e}")
        print(traceback.format_exc())
        return []

# -------------------------
# FUTEBOL: países -> ligas -> jogos (ao vivo + hoje + próximos 3 dias)
# -------------------------

def date_range_list(days_forward: int):
    today = datetime.utcnow().date()
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_forward+1)]

@app.get("/futebol/countries")
def futebol_countries():
    # buscar fixtures ao vivo + hoje + próximos 3 dias e extrair countries disponíveis
    days = 3
    dates = date_range_list(days)
    countries = {}
    for d in dates + ["live"]:
        params = {"date": d} if d != "live" else {"live": "all"}
        data = fetch_api_data('football', 'fixtures', params)
        for f in data:
            league = f.get("league", {})
            country = league.get("country")
            if country:
                countries[country] = countries.get(country, 0) + 1
    # retorna lista de países com contagem
    return [{"country": k, "count": v} for k, v in sorted(countries.items(), key=lambda x: x[0])]

@app.get("/futebol/leagues")
def futebol_leagues(country: str = Query(..., description="Nome do país ex: Brazil, Spain")):
    # busca fixtures nos próximos 3 dias + ao vivo, filtra por country e agrupa por league
    days = 3
    dates = date_range_list(days)
    leagues = {}
    for d in dates + ["live"]:
        params = {"date": d} if d != "live" else {"live": "all"}
        data = fetch_api_data('football', 'fixtures', params)
        for f in data:
            league = f.get("league", {})
            if league.get("country") == country:
                leagues[league["id"]] = {
                    "id": league["id"],
                    "name": league.get("name"),
                    "season": league.get("season")
                }
    return list(leagues.values())

@app.get("/futebol/games")
def futebol_games(league_id: int = Query(..., description="ID da liga (league.id)")):
    # retornar jogos AO VIVO + hoje + próximos 3 dias para a liga específica
    days = 3
    dates = date_range_list(days)
    games = []
    # ao vivo primeiro
    live_data = fetch_api_data('football', 'fixtures', {"live": "all", "league": league_id})
    for g in live_data:
        try:
            games.append({
                "game_id": g["fixture"]["id"],
                "status": g["fixture"]["status"],
                "league": g["league"],
                "teams": g["teams"],
                "fixture": g["fixture"],
                "type": "live"
            })
        except Exception:
            continue
    # depois por datas
    for d in dates:
        data = fetch_api_data('football', 'fixtures', {"date": d, "league": league_id})
        for g in data:
            games.append({
                "game_id": g["fixture"]["id"],
                "status": g["fixture"]["status"],
                "league": g["league"],
                "teams": g["teams"],
                "fixture": g["fixture"],
                "type": "scheduled"
            })
    # ordenar por datetime
    def parse_date(fixt):
        date_s = fixt.get("fixture", {}).get("date")
        if not date_s:
            return datetime.max
        try:
            return datetime.fromisoformat(date_s.replace("Z", "+00:00"))
        except Exception:
            return datetime.max
    games_sorted = sorted(games, key=parse_date)
    return games_sorted

# -------------------------
# NBA (hoje + 30 dias)
# -------------------------
@app.get("/nba")
def nba_games():
    days = 30
    today = datetime.utcnow().date()
    all_games = []
    for i in range(days + 1):
        date_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        data = fetch_api_data('basketball', 'games', {"date": date_str})
        for g in data:
            # normalizar para frontend
            all_games.append({
                "game_id": g.get("id"),
                "date": date_str,
                "home": g.get("teams", {}).get("home"),
                "away": g.get("teams", {}).get("visitors"),
                "status": g.get("status", {})
            })
    return all_games

# -------------------------
# NFL (hoje + 30 dias)
# -------------------------
@app.get("/nfl")
def nfl_games():
    days = 30
    today = datetime.utcnow().date()
    all_games = []
    for i in range(days + 1):
        date_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        data = fetch_api_data('american-football', 'games', {"date": date_str})
        for g in data:
            all_games.append({
                "game_id": g.get("game", {}).get("id") if isinstance(g.get("game"), dict) else g.get("id"),
                "date": date_str,
                "teams": g.get("teams") or g.get("teams"),
                "status": g.get("status") or g.get("game", {}).get("status", {})
            })
    return all_games

# -------------------------
# TIPSTER IA (endpoint stub — você pode estender)
# Recebe game_id e sport e retorna análises resumos simples
# -------------------------
@app.get("/tipster/analyze")
def tipster_analyze(game_id: int, sport: str = Query("football", enum=["football", "basketball", "american-football"])):
    # Busca fixture completo e retorna sugestões simples
    if sport == "football":
        data = fetch_api_data('football', 'fixtures', {"id": game_id})
    elif sport == "basketball":
        data = fetch_api_data('basketball', 'games', {"id": game_id})
    else:
        data = fetch_api_data('american-football', 'games', {"id": game_id})

    if not data:
        raise HTTPException(status_code=404, detail="Jogo não encontrado para análise")

    # Implementação simples: exemplo de outputs que seu frontend pode exibir
    analysis = {
        "game_id": game_id,
        "sport": sport,
        "summary": "Análise inicial (stub). Substitua por seu modelo/heurística.",
        "predictions": {
            "over_2_5_goals": 0.55,
            "both_teams_to_score": 0.6,
            "favorite_ml": "home",
            "corner_trend": "high"
        },
        "raw": data[0]  # enviar o raw para o frontend usar se quiser
    }
    return analysis
