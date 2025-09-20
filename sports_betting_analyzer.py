# Filename: sports_analyzer_live.py
# Versão: 7.1 (Correção na busca de jogos por liga)

import os
import requests
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

# ================================
# Inicialização do FastAPI
# ================================
app = FastAPI(title="Tipster Especialista - Futebol & NBA")

origins = ["https://jean-rgsocd.github.io", "http://localhost:5500", "https://analisador-apostas.onrender.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# Configuração
# ================================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("API_KEY não definida no ambiente.")

SPORTS_MAP = {
    "football": "https://v3.football.api-sports.io/",
    "nba": "https://v2.nba.api-sports.io/",
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
    return {
        "market": market,
        "suggestion": suggestion,
        "confidence": max(10, min(95, confidence)),
        "justification": justification
    }

# ================================
# Lógica de Análise - FUTEBOL
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
        elif f['fixture']['status']['short'] == 'FT' and not f['teams']['home']['winner'] and not f['teams']['away']['winner']: stats['draws'] += 1
        else: stats['losses'] += 1
        
        goals = f['goals']
        stats['goals_for'] += goals['home' if f['teams']['home']['id'] == team_id else 'away']
        stats['goals_against'] += goals['away' if f['teams']['home']['id'] == team_id else 'home']

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
        
        total_goals += (f['goals']['home'] or 0) + (f['goals']['away'] or 0)

    if stats['played'] > 0:
        stats['avg_total_goals'] = round(total_goals / stats['played'], 2)
    return stats

# ================================
# Lógica de Análise - NBA
# ================================
def _get_team_form_nba(team_id: int, n: int = 7) -> Dict[str, Any]:
    url = f"{SPORTS_MAP['nba']}games"
    params = {"team": team_id, "last": n, "season": "2024-2025"} # Ajuste a season conforme necessário
    data = make_request(url, params)
    games = data.get("response", [])
    
    stats = {"played": len(games), "wins": 0, "points_for": 0, "points_against": 0, "avg_points_for": 0.0, "win_rate": 0.0}
    if not games: return stats

    for g in games:
        if g.get('scores') and g['scores']['home'].get('total') is not None:
            is_home = g['teams']['home']['id'] == team_id
            if (is_home and g['scores']['home']['total'] > g['scores']['away']['total']) or \
               (not is_home and g['scores']['away']['total'] > g['scores']['home']['total']):
                stats['wins'] += 1
            
            stats['points_for'] += g['scores']['home' if is_home else 'away']['total']
            stats['points_against'] += g['scores']['away' if is_home else 'home']['total']

    if stats['played'] > 0:
        stats['win_rate'] = round((stats['wins'] / stats['played']) * 100, 2)
        stats['avg_points_for'] = round(stats['points_for'] / stats['played'], 2)
    return stats

# ================================
# Endpoints Principais de Análise
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

    elif sport == "nba":
        url = f"{SPORTS_MAP['nba']}games?id={game_id}"
        data = make_request(url)
        if not data.get("response"): raise HTTPException(404, "Partida da NBA não encontrada.")
        
        game = data["response"][0]
        home_team, away_team = game['teams']['home'], game['teams']['away']

        home_form = _get_team_form_nba(home_team['id'])
        away_form = _get_team_form_nba(away_team['id'])

        if abs(home_form['win_rate'] - away_form['win_rate']) > 25:
            winner = home_team['name'] if home_form['win_rate'] > away_form['win_rate'] else away_team['name']
            confidence = int(50 + abs(home_form['win_rate'] - away_form['win_rate']) / 2)
            picks.append(_build_pick("Vencedor (Moneyline)", f"{winner} para vencer", confidence, f"Forma recente superior com {max(home_form['win_rate'], away_form['win_rate'])}% de vitórias."))

        point_proj = home_form['avg_points_for'] + away_form['avg_points_for']
        dynamic_line = round(point_proj - 5, 0)
        if point_proj > 225:
            confidence = int(40 + (point_proj - 220) / 2)
            picks.append(_build_pick("Total de Pontos", f"Mais de {dynamic_line} pontos", confidence, f"Ambas as equipes têm médias ofensivas altas, projetando {point_proj:.1f} pontos."))

    if not picks:
        return [_build_pick("Equilibrado", "Nenhuma tendência clara", 40, "Estatísticas muito equilibradas para uma sugestão de alta confiança.")]
    
    return sorted(picks, key=lambda p: p['confidence'], reverse=True)

@app.get("/analisar-ao-vivo")
async def analisar_ao_vivo(game_id: int, sport: str):
    # Lógica de análise ao vivo pode ser implementada aqui no futuro
    return [_build_pick("Ao Vivo", "Análise ao vivo em desenvolvimento", 50, f"A análise ao vivo para {sport.upper()} será implementada em breve.")]

# ================================
# Endpoints Auxiliares de Navegação
# ================================
def normalize_fixture_response(g: dict, sport: str) -> Dict[str, Any]:
    try:
        if sport == 'football':
            fixture, teams = g.get("fixture", {}), g.get("teams", {})
            home, away = teams.get("home", {}), teams.get("away", {})
            status = fixture.get("status", {}).get("short", "NS")
            game_time = datetime.fromisoformat(fixture.get("date").replace("Z", "+00:00")).strftime('%H:%M')
        else: # NBA
            fixture, teams = g, g.get("teams", {})
            home, away = teams.get("home", {}), teams.get("visitors", {})
            status = g.get("status", {}).get("short", "NS")
            game_time = g.get("time", "?")
        
        return {
            "game_id": fixture.get("id"),
            "home": home.get("name", "Casa"),
            "away": away.get("name", "Fora"),
            "time": game_time,
            "status": status
        }
    except (AttributeError, TypeError, KeyError):
        return None # Retorna None se a estrutura do jogo for inválida

@app.get("/partidas-por-esporte/{sport}")
async def get_games_by_sport(sport: str):
    sport = sport.lower()
    if sport not in SPORTS_MAP:
        raise HTTPException(400, "Esporte não suportado.")

    endpoint_path = ""
    hoje = datetime.utcnow().strftime('%Y-%m-%d')

    if sport == "football":
        endpoint_path = f"fixtures?date={hoje}"
    elif sport == "nba":
        endpoint_path = f"games?date={hoje}"

    data = make_request(f"{SPORTS_MAP[sport]}{endpoint_path}")
    
    jogos_normalizados = []
    for g in data.get("response", []):
        jogo = normalize_fixture_response(g, sport)
        if jogo:
            jogos_normalizados.append(jogo)
    return jogos_normalizados


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
    # ===== MUDANÇA PRINCIPAL AQUI =====
    hoje_str = datetime.utcnow().strftime('%Y-%m-%d')
    season = datetime.now().year
    
    # Pedimos à API jogos para a liga e data específicas, muito mais eficiente
    url = f"{SPORTS_MAP['football']}fixtures"
    params = {"league": id_liga, "season": season, "date": hoje_str}
    
    data = make_request(url, params)
    
    jogos_normalizados = []
    for g in data.get("response", []):
        jogo = normalize_fixture_response(g, 'football')
        if jogo:
            jogos_normalizados.append(jogo)
            
    return jogos_normalizados

@app.on_event("startup")
async def startup_event():
    print("Serviço de Análise Esportiva iniciado. Foco: Futebol & NBA.")
