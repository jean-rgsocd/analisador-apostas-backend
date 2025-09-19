# Filename: sports_analyzer_live.py
# Versão 3.0 - Multi-Esportivo Ao Vivo com Tipster IA (Final)

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

HEADERS = {"x-rapidapi-key": API_KEY}

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
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Erro na requisição para {url}: {e}")
        return {"response": []}  # sempre retorna dicionário com "response"

# ================================
# Funções auxiliares de datas
# ================================
def jogos_ao_vivo(esporte: str):
    """Busca apenas jogos ao vivo."""
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")

    hoje = datetime.utcnow().date()
    url = f"{SPORTS_MAP[esporte]}fixtures"
    params = {
        "from": hoje.strftime("%Y-%m-%d"),
        "to": hoje.strftime("%Y-%m-%d"),
        "live": "all"
    }
    dados = make_request(url, params=params)
    jogos = dados.get("response", [])
    return jogos if isinstance(jogos, list) else []

def jogos_por_data(esporte: str, dias: int = 2):
    """Busca jogos a partir de hoje por X dias."""
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    hoje = datetime.utcnow().date()
    fim = hoje + timedelta(days=dias - 1)
    url = f"{SPORTS_MAP[esporte]}fixtures"
    params = {
        "from": hoje.strftime("%Y-%m-%d"),
        "to": fim.strftime("%Y-%m-%d")
    }
    dados = make_request(url, params=params)
    return dados.get("response", [])

def get_date_range(dias: int = 3):
    hoje = datetime.utcnow().date()
    fim = hoje + timedelta(days=dias - 1)
    return hoje, fim

# ================================
# Endpoints de jogos
# ================================
@app.get("/jogos-ao-vivo/{esporte}")
def endpoint_jogos_ao_vivo(esporte: str):
    return jogos_ao_vivo(esporte)

@app.get("/jogos-por-esporte")
def endpoint_jogos_por_esporte(sport: str = Query(..., description="Nome do esporte")):
    return jogos_por_data(sport, dias=2)

@app.get("/proximos-jogos/{esporte}/{dias}")
def endpoint_proximos_jogos(esporte: str, dias: int = 3):
    start_date, end_date = get_date_range(dias)
    url = f"{SPORTS_MAP[esporte]}fixtures"
    params = {
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d")
    }
    dados = make_request(url, params=params)
    return dados.get("response", [])

@app.get("/confronto-direto/{esporte}/{id_casa}/{id_fora}")
def endpoint_confronto_direto(esporte: str, id_casa: int, id_fora: int):
    url = f"{SPORTS_MAP[esporte]}fixtures/headtohead?h2h={id_casa}-{id_fora}"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/estatisticas/{esporte}/{id_partida}")
def endpoint_estatisticas_partida(esporte: str, id_partida: int):
    url = f"{SPORTS_MAP[esporte]}fixtures/statistics?fixture={id_partida}"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/eventos/{esporte}/{id_partida}")
def endpoint_eventos_partida(esporte: str, id_partida: int):
    url = f"{SPORTS_MAP[esporte]}fixtures/events?fixture={id_partida}"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/probabilidades/{esporte}/{id_partida}")
def endpoint_probabilidades(esporte: str, id_partida: int):
    url = f"{SPORTS_MAP[esporte]}odds?fixture={id_partida}"
    dados = make_request(url)
    return dados.get("response", [])

# ================================
# País → Liga → Jogos
# ================================
@app.get("/paises/{esporte}")
def listar_paises(esporte: str):
    url = f"{SPORTS_MAP[esporte]}countries"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/ligas/{esporte}/{id_pais}")
def listar_ligas(esporte: str, id_pais: str):
    url = f"{SPORTS_MAP[esporte]}leagues?country={id_pais}"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/partidas/{esporte}/{id_liga}")
def listar_partidas(esporte: str, id_liga: int):
    url = f"{SPORTS_MAP[esporte]}fixtures?league={id_liga}"
    dados = make_request(url)
    return dados.get("response", [])

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
    # Validação
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    if not game_id:
        raise HTTPException(status_code=400, detail="ID do jogo é obrigatório")

    # Aqui você processa as estatísticas e retorna dicas
    return [
        {"market": "Over/Under", "suggestion": "Over 2.5", "confidence": 75, "justification": "Times com média alta de gols"}
    ]


@app.get("/analisar-ao-vivo")
def analisar_ao_vivo(game_id: int, sport: str):
    # Validação
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    if not game_id:
        raise HTTPException(status_code=400, detail="ID do jogo é obrigatório")

    # Aqui você processa estatísticas em tempo real
    return [
        {"market": "Both Teams to Score", "suggestion": "Yes", "confidence": 80, "justification": "Time da casa atacando forte"}
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
            url = f"{SPORTS_MAP[esporte]}fixtures"
            params = {
                "from": datetime.utcnow().date().strftime("%Y-%m-%d"),
                "to": datetime.utcnow().date().strftime("%Y-%m-%d"),
                "live": "all"
            }
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
