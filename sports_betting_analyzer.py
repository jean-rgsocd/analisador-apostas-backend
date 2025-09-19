# Filename: sports_betting_analyzer.py
# Versão 10.0 - Tipster com Análise Pré-Jogo e Ao Vivo baseada nas regras do usuário

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI(title="Sports Betting Analyzer - Tipster IA", version="10.0")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int

# --- Lógica da API ---
SPORTS_MAP = {"football": {"endpoint_games": "/fixtures", "host": "v3.football.api-sports.io"}}

def get_daily_games_from_api(sport: str) -> Dict[str, List[GameInfo]]:
    # (Esta função permanece a mesma)
    games_by_league = {}; api_key = os.getenv("API_KEY")
    if not api_key: return {"Erro": []}
    config = SPORTS_MAP.get(sport.lower())
    if not config: return {"Erro": []}
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://{config['host']}{config['endpoint_games']}"
    querystring = {"date": today}
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status(); data = response.json()
        for item in data.get("response", []):
            league_name = item.get("league", {}).get("name", "Outros")
            home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
            away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
            game_id = item.get("fixture", {}).get("id", 0)
            status = item.get("fixture", {}).get("status", {}).get("short", "N/A")
            timestamp = item.get("fixture", {}).get("timestamp")
            game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
            if league_name not in games_by_league: games_by_league[league_name] = []
            games_by_league[league_name].append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
        return games_by_league
    except Exception as e:
        print(f"Erro ao buscar jogos: {e}"); return {"Erro": []}

# --- NOVA ENGINE DE ANÁLISE PRÉ-JOGO ---
def analyze_pre_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    tips = []
    try:
        # Busca H2H e forma dos times
        h2h_url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={game_id}-{game_id}" # API usa ID repetido para buscar H2H
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={game_id}"
        
        h2h_response = requests.get(h2h_url, headers=headers).json().get("response", [])
        stats_response = requests.get(stats_url, headers=headers).json().get("response", [])

        if not h2h_response or not stats_response:
            raise ValueError("Dados de H2H ou estatísticas não disponíveis.")

        # Análise de Gols
        total_goals = 0
        for match in h2h_response[:5]: # últimos 5 confrontos
            total_goals += match.get("goals", {}).get("home", 0) + match.get("goals", {}).get("away", 0)
        avg_goals = total_goals / 5 if len(h2h_response) >= 5 else 2.5
        
        if avg_goals > 2.7:
            tips.append(TipInfo(market="Total de Gols", suggestion="Mais de 2.5 Gols", justification=f"A média de gols nos últimos 5 confrontos diretos é de {avg_goals:.2f}.", confidence=75))
        elif avg_goals > 1.8:
            tips.append(TipInfo(market="Total de Gols", suggestion="Mais de 1.5 Gols", justification=f"A média de gols nos últimos 5 confrontos diretos é de {avg_goals:.2f}.", confidence=80))

        # Análise de Vencedor
        home_wins = 0
        away_wins = 0
        home_team_id = stats_response[0].get("team", {}).get("id")
        
        for match in h2h_response[:5]:
            winner_id = match.get("teams", {}).get("home", {}).get("winner")
            if winner_id == home_team_id: home_wins +=1
            elif winner_id != None: away_wins +=1

        if home_wins > away_wins + 2:
            tips.append(TipInfo(market="Vencedor da Partida", suggestion=f"Vitória do Time da Casa", justification=f"O time da casa venceu {home_wins} dos últimos {len(h2h_response)} confrontos diretos.", confidence=70))
        elif away_wins > home_wins + 2:
            tips.append(TipInfo(market="Vencedor da Partida", suggestion=f"Vitória do Time Visitante", justification=f"O time visitante venceu {away_wins} dos últimos {len(h2h_response)} confrontos diretos.", confidence=70))

        if not tips:
             tips.append(TipInfo(market="Análise Conclusiva", suggestion="Equilíbrio", justification="Os dados históricos não apontam um favoritismo claro para nenhum mercado.", confidence=0))
             
    except Exception as e:
        print(f"Erro na análise pré-jogo: {e}")
        tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados detalhados para esta partida.", confidence=0))
    return tips

# --- NOVA ENGINE DE ANÁLISE AO VIVO ---
def analyze_live_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    tips = []
    try:
        fixture_url = f"https://v3.football.api-sports.io/fixtures?id={game_id}"
        fixture_response = requests.get(fixture_url, headers=headers).json().get("response", [])
        if not fixture_response: raise ValueError("Dados do fixture não encontrados.")
        
        fixture = fixture_response[0]
        elapsed = fixture.get("fixture", {}).get("status", {}).get("elapsed", 0)
        home_goals = fixture.get("goals", {}).get("home", 0)
        away_goals = fixture.get("goals", {}).get("away", 0)
        
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={game_id}"
        stats_response = requests.get(stats_url, headers=headers).json().get("response", [])
        
        home_sot, away_sot, home_corners, away_corners = 0, 0, 0, 0
        if len(stats_response) == 2:
            home_stats = stats_response[0].get('statistics', [])
            away_stats = stats_response[1].get('statistics', [])
            def find_stat(sl, sn):
                for s in sl:
                    if s.get('type') == sn and s.get('value'): return int(s.get('value'))
                return 0
            home_sot = find_stat(home_stats, 'Shots on Goal')
            away_sot = find_stat(away_stats, 'Shots on Goal')
            home_corners = find_stat(home_stats, 'Corner Kicks')

        # REGRA AO VIVO 1: Gol no 1º Tempo
        if elapsed < 45 and home_goals == 0 and away_goals == 0:
            if (home_sot + away_sot) >= 3:
                tips.append(TipInfo(market="Gols no 1º Tempo", suggestion="Mais de 0.5 Gols (HT)", justification=f"O jogo está 0x0 mas já tem {home_sot+away_sot} chutes a gol, indicando pressão ofensiva.", confidence=70))

        # REGRA AO VIVO 2: Escanteios no Final do Jogo
        is_home_losing_fav = home_goals < away_goals # (Simplificação, idealmente checaríamos as odds)
        if elapsed > 75 and is_home_losing_fav and home_corners >= 7:
            tips.append(TipInfo(market="Escanteios Asiáticos", suggestion=f"Mais de {home_corners + 1.5} Escanteios", justification=f"O time da casa está perdendo e pressionando, com {home_corners} cantos já conquistados.", confidence=80))
            
        if not tips:
            tips.append(TipInfo(market="Análise Ao Vivo", suggestion="Aguardar", justification="O jogo está se desenrolando sem criar oportunidades claras de aposta no momento.", confidence=0))
            
    except Exception as e:
        print(f"Erro na análise ao vivo: {e}")
        tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados ao vivo para esta partida.", confidence=0))
    return tips

# --- Endpoints da API ---
@app.get("/jogos-do-dia")
def get_daily_games_endpoint(sport: str = "football"): return get_daily_games_from_api(sport)

@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
def analyze_pre_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_pre_game(game_id, api_key, headers)

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
def analyze_live_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_live_game(game_id, api_key, headers)
