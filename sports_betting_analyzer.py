# Filename: sports_betting_analyzer.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests
from bs4 import BeautifulSoup

# --- Configuração do CORS ---
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sports Betting Analyzer com Dados Reais", version="1.0")

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

# --- Lógica de Web Scraping (O Robô) ---
def get_real_stats(home_team: str, away_team: str) -> Optional[dict]:
    try:
        # Define um User-Agent para simular um navegador real
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        # 1. Busca pelo jogo para encontrar a URL
        search_url = f"https://www.sofascore.com/search?q={home_team}%20{away_team}"
        response = requests.get(search_url, headers=headers)
        response.raise_for_status() # Lança um erro se a requisição falhar
        
        # Analisa o HTML da busca
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontra o primeiro link de evento na lista de resultados
        event_link = soup.find('a', {'class': 'sc-b33a5868-0'}) # A classe pode mudar, é a parte frágil
        if not event_link or not event_link.has_attr('href'):
            return None # Retorna None se não encontrar o jogo

        match_url = "https://www.sofascore.com" + event_link['href']

        # 2. Acessa a página da partida para pegar as estatísticas
        match_response = requests.get(match_url, headers=headers)
        match_response.raise_for_status()
        match_soup = BeautifulSoup(match_response.text, 'html.parser')
        
        # Dicionário para armazenar as estatísticas
        stats = {"home": {}, "away": {}}
        
        # 3. Extrai as estatísticas (Exemplo com "Chutes no gol" e "Posse de bola")
        # Esta parte é a mais customizada e depende da estrutura do HTML do Sofascore
        stat_rows = match_soup.find_all('div', {'class': 'sc-a77553-0'}) # Encontra as linhas de estatísticas
        
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

    except requests.exceptions.RequestException as e:
        print(f"Erro de rede ou HTTP: {e}")
        return None
    except Exception as e:
        print(f"Um erro inesperado ocorreu: {e}")
        return None


# --- Engine de Análise (Agora usando dados reais) ---
def generate_tips(stats: dict) -> list[BettingTip]:
    tips = []
    
    # Exemplo de regra simples: Se um time tem muito mais posse de bola e chutes
    try:
        home_possession = int(stats.get("home", {}).get("Posse de bola", "0").replace('%', ''))
        away_possession = int(stats.get("away", {}).get("Posse de bola", "0").replace('%', ''))
        
        home_shots_on_target = int(stats.get("home", {}).get("Chutes no gol", "0"))
        away_shots_on_target = int(stats.get("away", {}).get("Chutes no gol", "0"))

        if home_shots_on_target > away_shots_on_target + 2 and home_possession > 60:
            tips.append(BettingTip(market="Próximo Gol: Time da Casa", justification=f"Dominando com {home_possession}% de posse e {home_shots_on_target} chutes no gol."))
        
        if away_shots_on_target > home_shots_on_target + 2 and away_possession > 60:
            tips.append(BettingTip(market="Próximo Gol: Time Visitante", justification=f"Dominando com {away_possession}% de posse e {away_shots_on_target} chutes no gol."))
        
        total_shots = home_shots_on_target + away_shots_on_target
        if total_shots > 5:
             tips.append(BettingTip(market="Mais de 1.5 Gols no Jogo (FT)", justification=f"O jogo está aberto com um total de {total_shots} chutes no gol."))

        if not tips:
            tips.append(BettingTip(market="Análise Indisponível", justification="O jogo está equilibrado ou não há dados suficientes para uma dica clara."))

    except (ValueError, KeyError) as e:
        tips.append(BettingTip(market="Erro na Análise", justification=f"Não foi possível processar as estatísticas: {e}"))

    return tips


# --- Endpoint Principal da API ---
@app.post("/analyze", response_model=MatchAnalysis)
def analyze_match(match: MatchInput):
    # Chama o robô de scraping para pegar dados reais
    live_stats = get_real_stats(match.home_team, match.away_team)
    
    if not live_stats:
        raise HTTPException(status_code=404, detail="Não foi possível encontrar estatísticas para esta partida. Verifique os nomes dos times ou tente mais tarde.")
    
    # Gera as dicas com base nos dados coletados
    tips = generate_tips(live_stats)
    
    report = MatchAnalysis(
        match_title=f"Análise para: {match.home_team} vs {match.away_team}",
        live_stats=live_stats,
        top_tips=tips
    )
    return report
