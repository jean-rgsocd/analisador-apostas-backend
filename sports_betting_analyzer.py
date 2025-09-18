# Filename: sports_betting_analyzer.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sports Betting Analyzer com Dados Reais", version="2.0")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------

# --- Modelos Pydantic (Entrada e Saída) ---
class MatchInput(BaseModel):
    home_team: str
    away_team: str

class BettingTip(BaseModel):
    market: str
    justification: str
    
class MatchAnalysis(BaseModel):
    match_title: str
    live_stats: dict
    top_tips: list[BettingTip]

class GameInfo(BaseModel):
    home: str
    away: str
    time: str

# --- Lógica de Web Scraping ---

# Função para buscar estatísticas de UM jogo (já tínhamos)
def get_real_stats(home_team: str, away_team: str) -> Optional[dict]:
    # ... (o código desta função continua o mesmo de antes, não precisamos mexer)
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        search_url = f"https://www.sofascore.com/search?q={home_team}%20{away_team}"
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        event_link = soup.find('a', {'class': 'sc-b33a5868-0'})
        if not event_link or not event_link.has_attr('href'): return None
        match_url = "https://www.sofascore.com" + event_link['href']
        match_response = requests.get(match_url, headers=headers)
        match_response.raise_for_status()
        match_soup = BeautifulSoup(match_response.text, 'html.parser')
        stats = {"home": {}, "away": {}}
        stat_rows = match_soup.find_all('div', {'class': 'sc-a77553-0'})
        for row in stat_rows:
            stat_name_element = row.find('div', {'class': 'sc-a77553-5'})
            home_value_element = row.find('div', {'class': 'sc-a77553-3'})
            away_value_element = row.find('div', {'class': 'sc-a77553-4'})
            if stat_name_element and home_value_element and away_value_element:
                stat_name = stat_name_element.text.strip()
                home_value = home_value_element.text.strip()
                away_value = away_value_element.text.strip()
                stats["home"][stat_name] = home_value
                stats["away"][stat_name] = away_value
        return stats
    except Exception:
        return None

# **NOVA FUNÇÃO** para buscar a lista de TODOS os jogos do dia
def get_daily_games() -> Dict[str, List[GameInfo]]:
    games_by_league = {}
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        main_url = "https://www.sofascore.com"
        response = requests.get(main_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontra todos os blocos de ligas na página
        league_blocks = soup.find_all('div', {'class': 'sc-b33a5868-2'})

        for block in league_blocks:
            # Pega o nome da liga
            league_name_element = block.find('div', {'class': 'sc-b33a5868-6'})
            if not league_name_element: continue
            league_name = league_name_element.text.strip()
            
            games_by_league[league_name] = []
            
            # Encontra todos os jogos dentro desse bloco de liga
            game_rows = block.find_all('a', {'class': 'sc-b33a5868-0'})
            for game in game_rows:
                home_team_element = game.find('div', {'data-testid': 'event-card-home-team'})
                away_team_element = game.find('div', {'data-testid': 'event-card-away-team'})
                time_element = game.find('div', {'class': 'sc-b33a5868-12'})
                
                if home_team_element and away_team_element and time_element:
                    game_info = GameInfo(
                        home=home_team_element.text.strip(),
                        away=away_team_element.text.strip(),
                        time=time_element.text.strip()
                    )
                    games_by_league[league_name].append(game_info)

        return games_by_league
    except Exception as e:
        print(f"Erro ao buscar jogos do dia: {e}")
        return {"Erro": [GameInfo(home="Não foi possível carregar os jogos", away="", time="")]}

# --- Engine de Análise (continua a mesma) ---
def generate_tips(stats: dict) -> list[BettingTip]:
    # ... (o código desta função continua o mesmo de antes)
    tips = []
    try:
        home_possession = int(stats.get("home", {}).get("Posse de bola", "0").replace('%', ''))
        home_shots_on_target = int(stats.get("home", {}).get("Chutes no gol", "0"))
        away_possession = int(stats.get("away", {}).get("Posse de bola", "0").replace('%', ''))
        away_shots_on_target = int(stats.get("away", {}).get("Chutes no gol", "0"))
        if home_shots_on_target > away_shots_on_target + 2 and home_possession > 60:
            tips.append(BettingTip(market="Próximo Gol: Time da Casa", justification=f"Dominando com {home_possession}% de posse e {home_shots_on_target} chutes no gol."))
        if away_shots_on_target > home_shots_on_target + 2 and away_possession > 60:
            tips.append(BettingTip(market="Próximo Gol: Time Visitante", justification=f"Dominando com {away_possession}% de posse e {away_shots_on_target} chutes no gol."))
        total_shots = home_shots_on_target + away_shots_on_target
        if total_shots > 5:
             tips.append(BettingTip(market="Mais de 1.5 Gols no Jogo (FT)", justification=f"O jogo está aberto com um total de {total_shots} chutes no gol."))
        if not tips:
            tips.append(BettingTip(market="Análise Indisponível", justification="Jogo equilibrado ou sem dados suficientes."))
    except (ValueError, KeyError):
        tips.append(BettingTip(market="Erro na Análise", justification="Não foi possível processar as estatísticas."))
    return tips

# --- Endpoints da API ---

# Endpoint antigo, para analisar um jogo específico
@app.post("/analyze", response_model=MatchAnalysis)
def analyze_match_endpoint(match: MatchInput):
    live_stats = get_real_stats(match.home_team, match.away_team)
    if not live_stats:
        raise HTTPException(status_code=404, detail="Não foi possível encontrar estatísticas para esta partida.")
    tips = generate_tips(live_stats)
    return MatchAnalysis(match_title=f"Análise para: {match.home_team} vs {match.away_team}", live_stats=live_stats, top_tips=tips)

# **NOSSO NOVO ENDPOINT**
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint():
    """
    Busca no Sofascore e retorna uma lista de jogos do dia, agrupados por liga.
    """
    games = get_daily_games()
    if not games:
        raise HTTPException(status_code=500, detail="Ocorreu um erro ao buscar os jogos do dia.")
    return games
