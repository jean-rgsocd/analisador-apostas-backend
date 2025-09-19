# Filename: sports_betting_analyzer.py
# Versão 9.1 - Depuração Avançada da Análise Ao Vivo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime
import json

app = FastAPI(title="Sports Betting Analyzer - Tipster IA", version="9.1")
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str
class TipInfo(BaseModel):
    market: str; suggestion: str; justification: str; confidence: int

SPORTS_MAP = {"football": {"endpoint_games": "/fixtures", "host": "v3.football.api-sports.io"}}

# ... (A função get_daily_games_from_api permanece a mesma) ...
def get_daily_games_from_api(sport: str) -> Dict[str, List[GameInfo]]:
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

def analyze_pre_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    # ... (A função de análise pré-jogo permanece a mesma) ...
    tips = []
    try:
        url = f"https://v3.football.api-sports.io/predictions?fixture={game_id}"
        pred_response = requests.get(url, headers=headers, timeout=20)
        pred_response.raise_for_status(); data = pred_response.json().get("response", [])
        if not data: raise ValueError("Sem prognósticos.")
        prediction = data[0]
        winner = prediction.get("predictions", {}).get("winner", {})
        advice = prediction.get("predictions", {}).get("advice", "N/A")
        percent = prediction.get("predictions", {}).get("percent", {})
        if winner and winner.get("name"):
            confidence = max(int(percent.get('home', '0%')[:-1]), int(percent.get('away', '0%')[:-1]))
            if confidence > 65:
                tips.append(TipInfo(market="Vencedor da Partida", suggestion=f"Vitória do {winner['name']}", justification=f"Análise da API sugere: '{advice}'.", confidence=confidence))
        if not tips:
            tips.append(TipInfo(market="Análise Conclusiva", suggestion="Aguardar ao vivo", justification="Os dados pré-jogo não indicam uma vantagem clara.", confidence=0))
    except Exception as e:
        print(f"Erro na análise pré-jogo: {e}")
        tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados detalhados para esta partida.", confidence=0))
    return tips

# --- ENGINE DE ANÁLISE AO VIVO COM DEPURAÇÃO ---
def analyze_live_game(game_id: int, api_key: str, headers: dict) -> List[TipInfo]:
    tips = []
    print(f"\n--- INICIANDO ANÁLISE AO VIVO PARA O JOGO ID: {game_id} ---")
    
    try:
        # Busca estatísticas ao vivo
        stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={game_id}"
        print(f"Buscando estatísticas em: {stats_url}")
        stats_response = requests.get(stats_url, headers=headers)
        stats_data = stats_response.json().get("response", [])
        
        # **DEPURAÇÃO: Imprime os dados brutos de estatísticas**
        print("\n--- RESPOSTA BRUTA DE ESTATÍSTICAS DA API ---")
        print(json.dumps(stats_data, indent=2))
        print("--- FIM DA RESPOSTA BRUTA DE ESTATÍSTICAS ---\n")

        if len(stats_data) < 2:
            raise ValueError("Dados de estatísticas incompletos da API.")

        # Busca dados gerais do fixture (placar, tempo)
        fixture_url = f"https://v3.football.api-sports.io/fixtures?id={game_id}"
        print(f"Buscando dados do fixture em: {fixture_url}")
        fixture_response = requests.get(fixture_url, headers=headers)
        fixture_data_list = fixture_response.json().get("response", [])
        if not fixture_data_list: raise ValueError("Dados do fixture não encontrados.")
        fixture_data = fixture_data_list[0]
        
        elapsed = fixture_data.get("fixture", {}).get("status", {}).get("elapsed", 0)
        home_goals = fixture_data.get("goals", {}).get("home", 0)
        away_goals = fixture_data.get("goals", {}).get("away", 0)
        
        print(f"DADOS DO JOGO: Tempo={elapsed}min, Placar={home_goals}x{away_goals}")

        home_stats = stats_data[0].get('statistics', [])
        away_stats = stats_data[1].get('statistics', [])

        def find_live_stat(stat_list, stat_name):
            for stat in stat_list:
                if stat.get('type') == stat_name and stat.get('value') is not None:
                    return int(stat.get('value'))
            return 0

        home_corners = find_live_stat(home_stats, 'Corner Kicks')
        away_corners = find_live_stat(away_stats, 'Corner Kicks')
        home_sot = find_live_stat(home_stats, 'Shots on Goal')
        away_sot = find_live_stat(away_stats, 'Shots on Goal')

        print(f"ESTATÍSTICAS EXTRAÍDAS: Cantos={home_corners}x{away_corners}, Chutes a Gol={home_sot}x{away_sot}")

        # REGRA 1: Gols no Final do Jogo
        if elapsed > 75 and home_goals == away_goals and (home_sot + away_sot > 8):
            tips.append(TipInfo(market="Gol nos Minutos Finais", suggestion=f"Acima de {home_goals + away_goals + 0.5} Gols", justification=f"Jogo empatado com pressão ofensiva ({home_sot+away_sot} chutes a gol).", confidence=70))

        # REGRA 2: Escanteios
        total_corners = home_corners + away_corners
        if elapsed > 65 and total_corners > 8:
             tips.append(TipInfo(market="Escanteios Asiáticos", suggestion=f"Mais de {total_corners + 1.5} escanteios", justification=f"Jogo com alta média de escanteios ({total_corners} aos {elapsed} min).", confidence=75))

        if not tips:
            tips.append(TipInfo(market="Análise Ao Vivo", suggestion="Mercado sem valor", justification="O jogo está se desenrolando sem criar oportunidades claras de aposta no momento.", confidence=0))
            print("NENHUMA REGRA ATENDIDA. Nenhuma dica gerada.")

    except Exception as e:
        print(f"ERRO CRÍTICO NA ANÁLISE AO VIVO: {e}")
        tips.append(TipInfo(market="Erro de Análise", suggestion="N/A", justification="Não foi possível obter dados ao vivo para esta partida.", confidence=0))
    
    print("--- ANÁLISE AO VIVO CONCLUÍDA ---")
    return tips

# --- Endpoints da API ---
@app.get("/jogos-do-dia")
def get_daily_games_endpoint(sport: str = "football"):
    return get_daily_games_from_api(sport)

@app.get("/analisar-pre-jogo", response_model=List[TipInfo])
def analyze_pre_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_pre_game(game_id, api_key, headers)

@app.get("/analisar-ao-vivo", response_model=List[TipInfo])
def analyze_live_game_endpoint(game_id: int):
    api_key = os.getenv("API_KEY"); headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    return analyze_live_game(game_id, api_key, headers)
