# Filename: sports_betting_analyzer.py
# Versão 3.1 - Com logs detalhados para depuração

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import time

# Importações do Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = FastAPI(title="Sports Betting Analyzer com Dados Reais", version="3.1")

# --- Configuração do CORS ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Modelos Pydantic ---
class GameInfo(BaseModel):
    home: str
    away: str
    time: str

# --- Lógica de Web Scraping com Selenium ---
def get_daily_games_with_selenium() -> Dict[str, List[GameInfo]]:
    print("PASSO 1: Iniciando a função get_daily_games_with_selenium.")
    games_by_league = {}
    
    print("PASSO 2: Configurando as opções do Chrome.")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = None
    try:
        print("PASSO 3: Tentando iniciar o driver do Chrome. Esta parte pode demorar...")
        driver = webdriver.Chrome(options=chrome_options)
        print("PASSO 4: Driver do Chrome iniciado com sucesso!")
        
        main_url = "https://www.flashscore.com.br/"
        print(f"PASSO 5: Acessando a URL: {main_url}")
        driver.get(main_url)
        print("PASSO 6: URL acessada. Aguardando o carregamento dinâmico dos jogos (até 20s)...")

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".event__match"))
        )
        print("PASSO 7: Elementos dos jogos foram encontrados na página!")
        
        html_content = driver.page_source
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        print("PASSO 8: HTML da página completa foi capturado e processado pelo BeautifulSoup.")

        soccer_section = soup.find('div', {'class': 'sportName soccer'})
        if not soccer_section:
            print("ERRO: Seção de futebol não encontrada.")
            raise ValueError("Seção de futebol não encontrada após carregamento dinâmico.")

        print("PASSO 9: Seção de futebol encontrada. Começando a extrair os jogos...")
        current_league = "Desconhecida"
        
        # ... (Lógica de extração de jogos continua a mesma) ...
        for element in soccer_section.find_all('div', recursive=False):
            if 'event__header' in element.get('class', []):
                country_element = element.find('span', {'class': 'event__title--type'})
                league_element = element.find('span', {'class': 'event__title--name'})
                if country_element and league_element:
                    current_league = f"{country_element.text.strip()}: {league_element.text.strip()}"
                    games_by_league[current_league] = []

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
                    if current_league in games_by_league:
                        games_by_league[current_league].append(game_info)
        
        print(f"PASSO 10: Extração concluída. {len(games_by_league)} ligas encontradas.")
        return games_by_league

    except Exception as e:
        print(f"ERRO CRÍTICO: Uma exceção ocorreu. Detalhes: {e}")
        return {"Erro": [GameInfo(home="Falha ao carregar jogos com Selenium.", away="O site pode estar bloqueando o robô.", time="")]}
    finally:
        if driver:
            print("PASSO FINAL: Fechando o driver do Chrome.")
            driver.quit()


# --- Endpoint da API ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint():
    print("--- REQUISIÇÃO RECEBIDA EM /jogos-do-dia ---")
    games = get_daily_games_with_selenium()
    if "Erro" in games:
         raise HTTPException(status_code=500, detail="Ocorreu um erro no backend ao tentar ler os dados do site de esportes.")
    if not games:
        print("Nenhum jogo foi retornado pela função de scraping.")
        return {"Info": [GameInfo(home="Nenhum jogo encontrado para hoje.", away="", time="")]}
    print("--- REQUISIÇÃO CONCLUÍDA COM SUCESSO ---")
    return games
