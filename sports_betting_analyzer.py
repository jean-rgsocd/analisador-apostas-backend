# Filename: sports_analyzer_live.py
# Versão 3.2 - Multi-Esportivo Ao Vivo com Tipster IA (Endpoints Corrigidos)

import os
import requests
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# ================================
# Inicialização do FastAPI
# ================================
app = FastAPI(title="Tipster Ao Vivo - Multi Esportes")

origins = [
    "https://jean-rgsocd.github.io",
    "http://localhost:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# Configuração da API Key
# ================================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("API_KEY não definida no ambiente!")

# ================================
# Mapas de esportes e URLs base
# ================================
SPORTS_MAP = {
    "football": "https://v3.football.api-sports.io/",
    "basketball": "https://v1.basketball.api-sports.io/",
    "nba": "https://v2.nba.api-sports.io/",
    "baseball": "https://v1.baseball.api-sports.io/",
    "formula-1": "https://v1.formula-1.api-sports.io/",
    "handball": "https://v1.handball.api-sports.io/",
    "hockey": "https://v1.hockey.api-sports.io/",
    "mma": "https://v1.mma.api-sports.io/",
    "nfl": "https://v1.american-football.api-sports.io/",
    "rugby": "https://v1.rugby.api-sports.io/",
    "volleyball": "https://v1.volleyball.api-sports.io/",
    "afl": "https://v1.afl.api-sports.io/"
}

# ================================
# Perfil do Tipster
# ================================
TIPSTER_PROFILE = {
    "total_predictions": 0,
    "correct_predictions": 0,
    "wrong_predictions": 0,
    "last_predictions": []
}

# ================================
# Função para requisições à API
# ================================
def make_request(url: str, params: dict = None) -> dict:
    try:
        host = url.split("//")[1].split("/")[0]
        headers = {
            "x-rapidapi-key": API_KEY,
            "x-rapidapi-host": host
        }
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Erro na requisição para {url}: {e}")
        return {"response": []}

# ================================
# Funções auxiliares de datas
# ================================
def get_date_range(dias: int = 3):
    hoje = datetime.utcnow().date()
    fim = hoje + timedelta(days=dias - 1)
    return hoje, fim

# ================================
# Endpoints de jogos
# ================================
@app.get("/jogos-ao-vivo/{esporte}")
def endpoint_jogos_ao_vivo(esporte: str):
    hoje = datetime.utcnow().date()
    url = f"{SPORTS_MAP[esporte]}fixtures"
    params = {
        "date": hoje.strftime("%Y-%m-%d"),
        "live": "all"
    }
    dados = make_request(url, params=params)
    return dados.get("response", [])

@app.get("/jogos-por-esporte")
def endpoint_jogos_por_esporte(sport: str = Query(...)):
    hoje, fim = get_date_range(2)
    url = f"{SPORTS_MAP[sport]}fixtures"
    params = {"from": hoje.strftime("%Y-%m-%d"), "to": fim.strftime("%Y-%m-%d")}
    dados = make_request(url, params=params)
    return dados.get("response", [])

@app.get("/partidas-por-esporte/{sport}")
async def get_games_by_sport(sport: str):
    try:
        hoje = datetime.utcnow().date()
        jogos = []

        for i in range(3):  # hoje + amanhã + depois
            data_str = (hoje + timedelta(days=i)).strftime("%Y-%m-%d")

            if sport == "football":
                url = f"{SPORTS_MAP[sport]}fixtures?date={data_str}"
            elif sport in ["basketball", "nba", "baseball", "nfl", "rugby", "volleyball", "handball", "hockey"]:
                url = f"{SPORTS_MAP[sport]}games?date={data_str}"
            elif sport == "mma":
                url = f"{SPORTS_MAP[sport]}fights?date={data_str}"
            elif sport == "formula-1":
                url = f"{SPORTS_MAP[sport]}races?season={datetime.now().year}"
            else:
                raise HTTPException(status_code=400, detail=f"Esporte {sport} não suportado.")

            host = url.split("//")[1].split("/")[0]
            headers = {
                "x-rapidapi-key": API_KEY,
                "x-rapidapi-host": host
            }
            response = requests.get(url, headers=headers)
            data_json = response.json()

            for g in data_json.get("response", []):
                fixture = g.get("fixture", g)
                teams = g.get("teams", {})
                home = teams.get("home", {}).get("name", "Time A")
                away = teams.get("away", {}).get("name", "Time B")
                game_id = fixture.get("id", g.get("id"))
                status = fixture.get("status", {}).get("short", "NS")
                date_str = fixture.get("date", "")
                if "T" in date_str:
                    date_part, time_part = date_str.split("T")
                    time = f"{date_part} {time_part[:5]}"
                else:
                    time = "?"
                jogos.append({
                    "game_id": game_id,
                    "home": home,
                    "away": away,
                    "time": time,
                    "status": status
                })

        return jogos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# Perfil do Tipster
# ================================
@app.get("/perfil-tipster")
def perfil_tipster():
    profile = TIPSTER_PROFILE.copy()
    if profile['total_predictions'] > 0:
        profile['accuracy'] = round(profile['correct_predictions'] / profile['total_predictions'] * 100, 2)
    return profile

@app.post("/adicionar-previsao")
def adicionar_previsao(fixture_id: int, previsao: str, esporte: str, resultado: Optional[str] = None):
    TIPSTER_PROFILE['total_predictions'] += 1
    if resultado == "correct":
        TIPSTER_PROFILE['correct_predictions'] += 1
    elif resultado == "wrong":
        TIPSTER_PROFILE['wrong_predictions'] += 1
    TIPSTER_PROFILE['last_predictions'].append({
        "fixture_id": fixture_id,
        "prediction": previsao,
        "sport": esporte,
        "result": resultado
    })
    return {"message": "Previsão adicionada com sucesso!"}

@app.get("/analisar-pre-jogo")
def analisar_pre_jogo(game_id: int, sport: str):
    return [
        {"market": "Over/Under", "suggestion": "Over 2.5", "confidence": 75,
         "justification": "Times com média alta de gols"}
    ]

@app.get("/analisar-ao-vivo")
def analisar_ao_vivo(game_id: int, sport: str):
    return [
        {"market": "Both Teams to Score", "suggestion": "Yes", "confidence": 80,
         "justification": "Time da casa atacando forte"}
    ]

@app.get("/dashboard-tipster")
def dashboard_tipster():
    profile = perfil_tipster()
    esporte_stats = {}
    for prediction in TIPSTER_PROFILE['last_predictions']:
        esporte = prediction.get('sport', 'desconhecido')
        if esporte not in esporte_stats:
            esporte_stats[esporte] = {"total": 0, "corretas": 0, "erradas": 0}
        esporte_stats[esporte]['total'] += 1
        if prediction['result'] == "correct":
            esporte_stats[esporte]['corretas'] += 1
        elif prediction['result'] == "wrong":
            esporte_stats[esporte]['erradas'] += 1
    for e, stats in esporte_stats.items():
        stats['acuracia'] = round(stats['corretas'] / stats['total'] * 100, 2) if stats['total'] > 0 else 0.0
    return {"perfil": profile, "por_esporte": esporte_stats}

# ================================
# Atualização ao vivo (startup)
# ================================
async def atualizar_jogos_ao_vivo(esporte: str, intervalo: int = 30):
    while True:
        try:
            hoje = datetime.utcnow().date()
            url = f"{SPORTS_MAP[esporte]}fixtures"
            params = {"date": hoje.strftime("%Y-%m-%d"), "live": "all"}
            dados = make_request(url, params=params)
            print(f"Atualização ao vivo ({esporte}): {len(dados.get('response', []))} jogos")
        except Exception as e:
            print(f"Erro ao atualizar jogos ao vivo ({esporte}):", e)
        await asyncio.sleep(intervalo)

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    for esporte in SPORTS_MAP.keys():
        loop.create_task(atualizar_jogos_ao_vivo(esporte))
    print("Atualização ao vivo iniciada automaticamente para todos os esportes")
