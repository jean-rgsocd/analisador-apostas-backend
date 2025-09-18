# Filename: sports_betting_analyzer.py
# Versão 3.0 - Usando Selenium para sites dinâmicos

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

app = FastAPI(title="Sports Betting Analyzer com Dados Reais", version="3.0")

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
    games_by_league = {}
    
    # --- Configuração do Navegador (Chrome) para rodar no servidor do Render ---
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Roda o Chrome sem abrir uma janela visual
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = None # Inicializa a variável do driver
    try:
        driver = webdriver.Chrome(options=chrome_options)
        main_url = "https://www.flashscore.com.br/"
        driver.get(main_url)

        # Espera até que os elementos dos jogos estejam visíveis na página (até 20 segundos)
        # Esta é a parte chave: esperamos o JavaScript do site carregar os dados
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".event__match"))
        )
        
        # Agora que a página está completa, pegamos o HTML final
        html_content = driver.page_source
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        soccer_section = soup.find('div', {'class': 'sportName soccer'})
        if not soccer_section:
            raise ValueError("Seção de futebol não encontrada após carregamento dinâmico.")

        current_league = "Desconhecida"
        
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

        return games_by_league

    except Exception as e:
        print(f"Erro detalhado com Selenium: {e}")
        return {"Erro": [GameInfo(home="Falha ao carregar jogos com Selenium.", away="O site pode estar bloqueando o robô.", time="")]}
    finally:
        # Garante que o navegador seja fechado, mesmo se ocorrer um erro
        if driver:
            driver.quit()


# --- Endpoint da API ---
@app.get("/jogos-do-dia", response_model=Dict[str, List[GameInfo]])
def get_daily_games_endpoint():
    games = get_daily_games_with_selenium()
    if "Erro" in games:
         raise HTTPException(status_code=500, detail="Ocorreu um erro no backend ao tentar ler os dados do site de esportes.")
    if not games:
        return {"Info": [GameInfo(home="Nenhum jogo encontrado para hoje.", away="", time="")]}
    return games
