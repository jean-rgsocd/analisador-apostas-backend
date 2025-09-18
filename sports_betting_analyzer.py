# Filename: sports_betting_analyzer.py
# Versão 2.1 - Adaptado para Flashscore.com.br

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import requests
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sports Betting Analyzer com Dados Reais", version="2.1")

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

# **NOVA FUNÇÃO** para buscar a lista de TODOS os jogos do dia no FLASHSCORE
def get_daily_games_from_flashscore() -> Dict[str, List[GameInfo]]:
    games_by_league = {}
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        main_url = "https://www.flashscore.com.br/"
        response = requests.get(main_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontra todos os jogos na seção de futebol
        # A classe 'sportName soccer' encapsula todos os jogos de futebol do dia
        soccer_section = soup.find('div', {'class': 'sportName soccer'})
        if not soccer_section:
            raise ValueError("Não foi possível encontrar a seção de futebol na página.")

        current_league = "Desconhecida"
        
        # Itera sobre todos os elementos filhos da seção de futebol
        for element in soccer_section.find_all('div', recursive=False):
            # Se o elemento é um cabeçalho de liga, atualiza a liga atual
            if 'event__header' in element.get('class', []):
                country_element = element.find('span', {'class': 'event__title--type'})
                league_element = element.find('span', {'class': 'event__title--name'})
                if country_element and league_element:
                    current_league = f"{country_element.text.strip()}: {league_element.text.strip()}"
                    games_by_league[current_league] = []

            # Se o elemento é um jogo, extrai as informações
            elif 'event__match' in element.get('class', []):
                home_team = element.find('div', {'class': 'event__participant--home'})
                away_team = element.find('div', {'class': 'event__participant--away'})
                game_time = element.find('div', {'class': 'event__time'})

                if home_team and away_team and game_time:
                    game_info = GameInfo(
                        home=home_team.text.strip(),
                        away=away_team.text.strip(),
                        time=game_time.text.strip()
                    )
                    # Adiciona o jogo à liga atual, se a liga já foi inicializada
                    if current_league in games_by_league:
                        games_by_league[current_league].append(game_info)

        return games_by_league
        
    except Exception as e:
        print(f"Erro ao buscar jogos do dia no Flashscore: {e}")
        return {"Erro": [GameInfo(home="Não foi possível carregar os jogos", away="Verifique os logs do backend", time="")]}


# --- Endpoint Principal da API ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint():
    """
    Busca no Flashscore.com.br e retorna uma lista de jogos do dia, agrupados por liga.
    """
    games = get_daily_games_from_flashscore()
    if not games:
        # Se a raspagem retornar um dicionário vazio, informa o usuário.
        return {"Info": [GameInfo(home="Nenhum jogo encontrado para hoje.", away="", time="")]}
    return games

# --------------------------------------------------------------------
# A função de análise de UM jogo ainda está aqui, mas não é nossa prioridade agora.
# Ela ainda está configurada para o Sofascore e precisaria ser adaptada para o Flashscore
# se quiséssemos manter a funcionalidade de análise detalhada.
# --------------------------------------------------------------------
@app.post("/analyze", response_model=MatchAnalysis)
def analyze_match_endpoint(match: MatchInput):
    raise HTTPException(status_code=501, detail="A funcionalidade de análise detalhada ainda não foi adaptada para o novo site. Use o endpoint /jogos-do-dia.")
