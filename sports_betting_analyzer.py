# Filename: sports_analyzer_live.py
# Versão: 7.4 (NFL Adicionada) - Versão Final Estável

import os
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

# ================================
# Inicialização do FastAPI
# ================================
app = FastAPI(title="Tipster Especialista - Futebol, NBA & NFL")
origins = ["https://jean-rgsocd.github.io", "http://localhost:5500", "https://analisador-apostas.onrender.com"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ================================
# Configuração
# ================================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("API_KEY não definida no ambiente.")

SPORTS_MAP = {
    "football": "https://v3.football.api-sports.io/",
    "nba": "https://v2.nba.api-sports.io/",
    "nfl": "https://v1.american-football.api-sports.io/",
}

# ================================
# Funções Utilitárias
# ================================
def make_request(url: str, params: dict = None) -> dict:
    try:
        host = url.split("//")[1].split("/")[0]
        headers = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": host}
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {"response": []}

def _build_pick(market: str, suggestion: str, confidence: int, justification: str) -> Dict[str, Any]:
    return {"market": market, "suggestion": suggestion, "confidence": max(10, min(95, confidence)), "justification": justification}

# ================================
# Funções de Análise de Forma
# ================================
def _get_team_form_football(team_id: int, n: int = 5) -> Dict[str, Any]:
    url = f"{SPORTS_MAP['football']}fixtures"
    params = {"team": team_id, "last": n}
    data = make_request(url, params)
    fixtures = data.get("response", [])
    stats = {"played": len(fixtures), "wins": 0, "draws": 0, "losses": 0, "goals_for": 0, "goals_against": 0, "win_rate": 0.0, "avg_goals_for": 0.0}
    if not fixtures: return stats
    for f in fixtures:
        is_winner = f['teams']['home' if f['teams']['home']['id'] == team_id else 'away'].get('winner', False)
        if is_winner: stats['wins'] += 1
        elif f['fixture']['status']['short'] == 'FT' and not f['teams']['home'].get('winner') and not f['teams']['away'].get('winner'): stats['draws'] += 1
        else: stats['losses'] += 1
        goals = f.get('goals', {})
        stats['goals_for'] += goals.get('home' if f['teams']['home']['id'] == team_id else 'away', 0) or 0
        stats['goals_against'] += goals.get('away' if f['teams']['home']['id'] == team_id else 'home', 0) or 0
    if stats['played'] > 0:
        stats['win_rate'] = round((stats['wins'] / stats['played']) * 100, 2)
        stats['avg_goals_for'] = round(stats['goals_for'] / stats['played'], 2)
    return stats


def _get_h2h_stats_football(team1_id: int, team2_id: int, n: int = 5) -> Dict[str, Any]:
    url = f"{SPORTS_MAP['football']}fixtures/headtohead"
    params = {"h2h": f"{team1_id}-{team2_id}", "last": n}
    data = make_request(url, params)
    fixtures = data.get("response", [])
    stats = {"played": len(fixtures), "team1_wins": 0, "team2_wins": 0, "draws": 0, "avg_total_goals": 0.0}
    if not fixtures: return stats
    total_goals = 0
    for f in fixtures:
        winner_id = None
        if f['teams']['home'].get('winner'): winner_id = f['teams']['home']['id']
        elif f['teams']['away'].get('winner'): winner_id = f['teams']['away']['id']
        if winner_id == team1_id: stats['team1_wins'] += 1
        elif winner_id == team2_id: stats['team2_wins'] += 1
        else: stats['draws'] += 1
        total_goals += (f['goals'].get('home', 0) or 0) + (f['goals'].get('away', 0) or 0)
    if stats['played'] > 0:
        stats['avg_total_goals'] = round(total_goals / stats['played'], 2)
    return stats

def _get_team_form_nba_or_nfl(team_id: int, sport: str, n: int = 7) -> Dict[str, Any]:
    url = f"{SPORTS_MAP[sport]}games"
    params = {"team": team_id, "last": n}
    data = make_request(url, params)
    games = data.get("response", [])
    stats = {"played": len(games), "wins": 0, "points_for": 0, "points_against": 0, "avg_points_for": 0.0, "avg_points_against": 0.0, "win_rate": 0.0}
    if not games: return stats
    for g in games:
        if g.get('scores') and g['scores']['home'].get('total') is not None:
            is_home = g['teams']['home']['id'] == team_id
            home_score = g['scores']['home']['total']
            away_score = g['scores']['away']['total']
            if (is_home and home_score > away_score) or (not is_home and away_score > home_score):
                stats['wins'] += 1
            stats['points_for'] += home_score if is_home else away_score
            stats['points_against'] += away_score if is_home else home_score
    if stats['played'] > 0:
        stats['win_rate'] = round((stats['wins'] / stats['played']) * 100, 2)
        stats['avg_points_for'] = round(stats['points_for'] / stats['played'], 2)
        stats['avg_points_against'] = round(stats['points_against'] / stats['played'], 2)
    return stats

# ================================
# Endpoint Principal de Análise
# ================================
@app.get("/analisar-pre-jogo")
async def analisar_pre_jogo(game_id: int, sport: str):
    sport = sport.lower()
    picks = []

    if sport == "football":
        url = f"{SPORTS_MAP['football']}fixtures?id={game_id}"
        data = make_request(url)
        if not data.get("response"): raise HTTPException(404, "Partida de Futebol não encontrada.")
        fixture = data["response"][0]
        home_team, away_team = fixture['teams']['home'], fixture['teams']['away']
        home_form = _get_team_form_football(home_team['id'])
        away_form = _get_team_form_football(away_team['id'])
        h2h = _get_h2h_stats_football(home_team['id'], away_team['id'])
        home_score = 15 + (home_form['win_rate'] * 0.4) + (h2h['team1_wins'] * 5)
        away_score = (away_form['win_rate'] * 0.4) + (h2h['team2_wins'] * 5)
        if abs(home_score - away_score) > 20:
            winner = home_team['name'] if home_score > away_score else away_team['name']
            confidence = int(50 + abs(home_score - away_score) / 2)
            picks.append(_build_pick("Vencedor", f"{winner} para vencer", confidence, f"Análise baseada na forma recente e histórico H2H."))
        goal_proj = (home_form['avg_goals_for'] + away_form['avg_goals_for'] + h2h['avg_total_goals']) / 3 if h2h['played'] > 0 else (home_form['avg_goals_for'] + away_form['avg_goals_for']) / 2
        if goal_proj > 2.8:
            confidence = int(30 + (goal_proj - 2.5) * 20)
            picks.append(_build_pick("Gols", "Mais de 2.5 gols", confidence, f"Projeção de {goal_proj:.2f} gols para a partida."))

    elif sport in ["nba", "nfl"]:
        url = f"{SPORTS_MAP[sport]}games?id={game_id}"
        data = make_request(url)
        if not data.get("response"): raise HTTPException(404, f"Partida da {sport.upper()} não encontrada.")
        
        game = data["response"][0]
        home_team, away_team = game['teams']['home'], game['teams']['away']

        home_form = _get_team_form_nba_or_nfl(home_team['id'], sport)
        away_form = _get_team_form_nba_or_nfl(away_team['id'], sport)
        
        # Análise de Vencedor
        home_power = (home_form['avg_points_for'] - home_form['avg_points_against']) + (home_form['win_rate'] * 0.1)
        away_power = (away_form['avg_points_for'] - away_form['avg_points_against']) + (away_form['win_rate'] * 0.1)
        if abs(home_power - away_power) > 4:
            winner = home_team['name'] if home_power > away_power else away_team['name']
            confidence = int(60 + abs(home_power - away_power))
            picks.append(_build_pick("Vencedor (Moneyline)", f"{winner} para vencer", confidence, f"Análise aponta superioridade com base no saldo de pontos e vitórias recentes."))

        # Análise de Pontos Totais
        point_proj = home_form['avg_points_for'] + away_form['avg_points_for']
        line_threshold = 225 if sport == 'nba' else 45
        dynamic_line = round(point_proj - (5 if sport == 'nba' else 2.5), 0)
        if point_proj > line_threshold:
            confidence = int(50 + (point_proj - line_threshold))
            picks.append(_build_pick("Total de Pontos", f"Mais de {dynamic_line} pontos", confidence, f"Ataques produtivos. Projeção de {point_proj:.1f} pontos na partida."))

    if not picks:
        return [_build_pick("Equilibrado", "Nenhuma tendência clara", 40, "Estatísticas muito equilibradas para uma sugestão de alta confiança.")]
    
    return sorted(picks, key=lambda p: p['confidence'], reverse=True)

# ================================
# Endpoints Auxiliares de Navegação
# ================================
def normalize_fixture_response(g: dict, sport: str) -> Dict[str, Any]:
    try:
        game_time_str = ""
        if sport == 'football':
            fixture, teams = g.get("fixture", {}), g.get("teams", {})
            home, away = teams.get("home", {}), teams.get("away", {})
            status = fixture.get("status", {}).get("short", "NS")
            game_time_str = fixture.get("date", "")
        else: # NBA e NFL
            fixture, teams = g, g.get("teams", {})
            home, away = teams.get("home", {}), teams.get("away", {})
            status = g.get("status", {}).get("short", "NS")
            game_time_str = g.get("date", "")
        
        game_time = datetime.fromisoformat(game_time_str.replace("Z", "+00:00")).strftime('%d/%m %H:%M')
        
        return {"game_id": fixture.get("id"), "home": home.get("name", "Casa"), "away": away.get("name", "Fora"), "time": game_time, "status": status}
    except Exception:
        return None

@app.get("/partidas-por-esporte/{sport}")
async def get_games_by_sport(sport: str):
    sport = sport.lower()
    if sport not in SPORTS_MAP:
        raise HTTPException(400, "Esporte não suportado.")

    all_games, seen_ids = [], set()
    today = datetime.utcnow()
    
    if sport == "football":
        start_date = today.strftime('%Y-%m-%d')
        end_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
        endpoint_path = f"fixtures?from={start_date}&to={end_date}"
        data = make_request(f"{SPORTS_MAP[sport]}/{endpoint_path}")
        for g in data.get("response", []):
            game_id = g.get("fixture", {}).get("id")
            if game_id and game_id not in seen_ids:
                if (jogo := normalize_fixture_response(g, sport)):
                    all_games.append(jogo)
                    seen_ids.add(game_id)
    else: # NBA e NFL
        for i in range(3):
            current_date = today + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            endpoint_path = f"games?date={date_str}"
            data = make_request(f"{SPORTS_MAP[sport]}/{endpoint_path}")
            for g in data.get("response", []):
                game_id = g.get("id")
                if game_id and game_id not in seen_ids:
                    if (jogo := normalize_fixture_response(g, sport)):
                        all_games.append(jogo)
                        seen_ids.add(game_id)
                        
    return sorted(all_games, key=lambda x: x['time'])

@app.get("/paises/football")
def listar_paises_futebol():
    return make_request(f"{SPORTS_MAP['football']}countries").get("response", [])

@app.get("/ligas/football/{id_pais}")
def listar_ligas_futebol(id_pais: str):
    season = datetime.now().year
    data = make_request(f"{SPORTS_MAP['football']}leagues?country={id_pais}&season={season}")
    return [l['league'] for l in data.get("response", [])]

@app.get("/partidas/football/{id_liga}")
def listar_partidas_por_liga_futebol(id_liga: int):
    today = datetime.utcnow()
    start_date = today.strftime('%Y-%m-%d')
    end_date = (today + timedelta(days=2)).strftime('%Y-%m-%d')
    season = today.year
    params = {"league": id_liga, "season": season, "from": start_date, "to": end_date}
    data = make_request(f"{SPORTS_MAP['football']}fixtures", params)
    all_games = [jogo for g in data.get("response", []) if (jogo := normalize_fixture_response(g, 'football'))]
    return sorted(all_games, key=lambda x: x['time'])

@app.on_event("startup")
async def startup_event():
    print("Serviço de Análise Esportiva iniciado. Foco: Futebol, NBA & NFL.")
