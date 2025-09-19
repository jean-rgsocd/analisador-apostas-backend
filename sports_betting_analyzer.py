# Filename: sports_betting_analyzer.py
# Versão 13.0 - Filtro Geográfico

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime, timedelta

app = FastAPI(title="Sports Betting Analyzer - Filtro Geográfico", version="13.0")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str; away: str; time: str; game_id: int; status: str

# --- MAPA DE ESPORTES ---
SPORTS_MAP = {"football": {"endpoint_games": "/fixtures", "host": "v3.football.api-sports.io"}}

# --- MAPEAMENTO DE COMPETIÇÕES INTERNACIONAIS ---
CONTINENT_MAP = {
    "CONMEBOL Libertadores": "América do Sul",
    "CONMEBOL Sudamericana": "América do Sul",
    "Copa America": "América do Sul",
    "UEFA Champions League": "Europa",
    "UEFA Europa League": "Europa",
    "Euro Championship": "Europa",
    "Friendlies": "Mundo (Amistosos)",
    "World Cup": "Mundo (Copa do Mundo)"
}

# --- FUNÇÕES DA API ---

@app.get("/paises", response_model=List[str])
def get_countries_endpoint():
    """Retorna uma lista de países e continentes com jogos."""
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    url = "https://v3.football.api-sports.io/countries"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json().get("response", [])
        
        # Extrai os nomes dos países da resposta da API
        countries = [country.get("name") for country in data if country.get("name")]
        
        # Adiciona os continentes manualmente e remove duplicatas
        all_locations = sorted(list(set(countries + list(CONTINENT_MAP.values()))))
        
        return all_locations
    except Exception as e:
        print(f"Erro ao buscar países: {e}")
        raise HTTPException(status_code=500, detail="Falha ao buscar lista de países.")


@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint(sport: str = "football", pais: Optional[str] = None):
    """Retorna os jogos do dia, opcionalmente filtrados por país ou continente."""
    games_by_league = {}
    api_key = os.getenv("API_KEY")
    if not api_key: return {"Erro": []}

    config = SPORTS_MAP.get(sport.lower())
    if not config: return {"Erro": []}

    url = f"https://{config['host']}{config['endpoint_games']}"
    headers = {'x-rapidapi-host': config["host"], 'x-rapidapi-key': api_key}
    today = datetime.now().strftime("%Y-%m-%d")

    # A busca agora é sempre por data, o filtro de país é aplicado depois
    querystring = {"date": today}
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        all_fixtures = response.json().get("response", [])

        if not all_fixtures:
            return {"Info": [GameInfo(home="Nenhum jogo encontrado para hoje.", away="", time="", game_id=0, status="")]}

        # Aplica o filtro de país/continente se ele foi fornecido
        for item in all_fixtures:
            league_name = item.get("league", {}).get("name", "Outros")
            country_name = item.get("league", {}).get("country", "")
            
            # Verifica se a liga pertence a um continente mapeado
            continent = CONTINENT_MAP.get(league_name)

            # Lógica de filtragem
            if pais:
                if pais == continent: # Se o filtro é um continente
                    pass # Inclui o jogo
                elif pais == country_name: # Se o filtro é um país
                    pass # Inclui o jogo
                else:
                    continue # Pula o jogo se não corresponder ao filtro

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


# --- Os endpoints de análise permanecem os mesmos ---
@app.get("/analisar-pre-jogo")
# ... (seu código de análise pré-jogo aqui) ...

@app.get("/analisar-ao-vivo")
# ... (seu código de análise ao vivo aqui) ...
