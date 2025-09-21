# Filename: sports_betting_analyzer.py
# VERSÃO MELHORADA - COM ANÁLISE DE ESTATÍSTICAS

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List, Dict, Any

app = FastAPI(title="Tipster IA - V3 com Análise Melhorada")

# --- CACHE, CORS, CONFIGURAÇÕES (sem alterações) ---
cache: Dict[str, Any] = {}
CACHE_DURATION_MINUTES = 60
origins = ["https://jean-rgsocd.github.io", "http://127.0.0.1:5500", "http://localhost:5500"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
API_SPORTS_KEY = "85741d1d66385996de506a07e3f527d1"
HEADERS = {"x-apisports-key": API_SPORTS_KEY}

def get_season_for_sport(sport: str) -> str:
    now = datetime.now()
    year = now.year
    if sport == "basketball":
        return f"{year - 1}-{year}" if now.month < 10 else f"{year}-{year + 1}"
    return str(year)

# --- FUNÇÕES DE BUSCA (sem alterações) ---
@app.get("/paises/football")
def get_football_countries() -> List[Dict[str, str]]:
    cache_key = "countries_football"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]: return cache[cache_key]["data"]
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

@app.get("/ligas/football/{country_name}")
def get_leagues_by_country(country_name: str) -> List[Dict[str, Any]]:
    cache_key = f"leagues_football_{country_name}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]: return cache[cache_key]["data"]
    url = "https://v3.football.api-sports.io/leagues"
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

@app.get("/partidas/{sport}/{league_id}")
def get_games_by_league(sport: str, league_id: str) -> List[Dict[str, Any]]:
    season = get_season_for_sport(sport)
    cache_key = f"games_{sport}_{league_id}_{season}"
    if cache_key in cache and datetime.now() < cache[cache_key]["expiry"]: return cache[cache_key]["data"]
    try:
        games_data = []
        if sport == "football":
            url = "https://v3.football.api-sports.io/fixtures"
            params = {"league": league_id, "season": season, "next": "30"}
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

# --- FUNÇÃO DE ANÁLISE (MELHORADA) ---
def get_team_ids_from_fixture(fixture_id):
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"id": fixture_id}
    data = requests.get(url, headers=HEADERS, params=params).json().get("response", [])
    if not data: return None, None
    home_id = data[0]["teams"]["home"]["id"]
    away_id = data[0]["teams"]["away"]["id"]
    return home_id, away_id

@app.get("/analisar-pre-jogo")
def get_pre_game_analysis(game_id: int, sport: str):
    # Por enquanto, a análise avançada é só para futebol
    if sport != "football":
        return [{"market": "Indisponível", "suggestion": "N/A", "justification": "Análise detalhada disponível apenas para futebol no momento.", "confidence": 0}]

    home_id, away_id = get_team_ids_from_fixture(game_id)
    if not home_id:
        return [{"market": "Erro", "suggestion": "N/A", "justification": "Não foi possível encontrar os dados do jogo.", "confidence": 0}]
    
    # 1. Buscar H2H (confronto direto)
    h2h_url = "https://v3.football.api-sports.io/fixtures/headtohead"
    h2h_params = {"h2h": f"{home_id}-{away_id}", "last": "5"}
    h2h_data = requests.get(h2h_url, headers=HEADERS, params=h2h_params).json().get("response", [])
    
    home_wins = 0
    away_wins = 0
    for match in h2h_data:
        if match["teams"]["home"]["winner"]:
            if match["teams"]["home"]["id"] == home_id:
                home_wins += 1
            else:
                away_wins += 1
        elif match["teams"]["away"]["winner"]:
            if match["teams"]["away"]["id"] == away_id:
                away_wins += 1
            else:
                home_wins += 1

    # 2. Buscar estatísticas recentes das equipes (forma)
    stats_url = "https://v3.football.api-sports.io/teams/statistics"
    home_stats_params = {"league": h2h_data[0]["league"]["id"], "season": get_season_for_sport(sport), "team": home_id}
    away_stats_params = {"league": h2h_data[0]["league"]["id"], "season": get_season_for_sport(sport), "team": away_id}
    
    home_stats = requests.get(stats_url, headers=HEADERS, params=home_stats_params).json().get("response", {})
    away_stats = requests.get(stats_url, headers=HEADERS, params=away_stats_params).json().get("response", {})

    home_goals_avg = home_stats.get("goals", {}).get("for", {}).get("average", {}).get("total", 0)
    away_goals_avg = away_stats.get("goals", {}).get("for", {}).get("average", {}).get("total", 0)
    
    # 3. Gerar Justificativas
    analysis_tips = []
    
    # Análise de Vencedor
    if home_wins > away_wins + 1: # Se tem pelo menos 2 vitórias a mais no H2H
        analysis_tips.append({
            "market": "Vencedor da Partida",
            "suggestion": f"Vitória do {home_stats['team']['name']}",
            "justification": f"O time da casa tem um forte retrospecto no confronto direto, com {home_wins} vitórias nos últimos {len(h2h_data)} jogos.",
            "confidence": 75
        })
    elif away_wins > home_wins + 1:
        analysis_tips.append({
            "market": "Vencedor da Partida",
            "suggestion": f"Vitória do {away_stats['team']['name']}",
            "justification": f"O time visitante leva vantagem no confronto direto, com {away_wins} vitórias nos últimos {len(h2h_data)} jogos.",
            "confidence": 75
        })
        
    # Análise de Gols (Over/Under)
    try: # Usar try-except para evitar erro se a média for string
        if float(home_goals_avg) > 1.8 and float(away_goals_avg) > 1.8:
            analysis_tips.append({
                "market": "Total de Gols (Mais/Menos)",
                "suggestion": "Mais de 2.5 Gols",
                "justification": f"Ambas as equipes possuem uma alta média de gols na temporada ({home_goals_avg} e {away_goals_avg} gols/jogo), indicando um jogo com potencial ofensivo.",
                "confidence": 80
            })
    except (ValueError, TypeError):
        pass

    if not analysis_tips:
         return [{"market": "Equilíbrio", "suggestion": "N/A", "justification": "As estatísticas e o confronto direto apontam para um jogo equilibrado. Análise manual recomendada.", "confidence": 0}]

    return analysis_tips
