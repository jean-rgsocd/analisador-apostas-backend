# Filename: sports_analyzer_live.py
# Versão 7.1 (Validação Final Completa) - NFL=2025, Futebol=2022

import os
import requests
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any

app = FastAPI(title="Tipster Validação Final - Football, NBA e NFL")

# -------------------------------
# CORS
# -------------------------------
origins = [
    "https://jean-rgsocd.github.io",
    "http://localhost:5500",
    "https://analisador-apostas.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Configuração da API
# -------------------------------
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("API_KEY não definida no ambiente!")

SPORTS_MAP = {
    "football": "https://v3.football.api-sports.io/",
    "nba": "https://v2.nba.api-sports.io/",
    "nfl": "https://v1.american-football.api-sports.io/"
}

# -------------------------------
# Perfil Tipster
# -------------------------------
TIPSTER_PROFILE: Dict[str, Any] = {
    "total_predictions": 0,
    "correct_predictions": 0,
    "wrong_predictions": 0,
    "last_predictions": []
}

# -------------------------------
# Funções auxiliares
# -------------------------------
def make_request(url: str, params: dict = None) -> dict:
    try:
        host = url.split("//")[1].split("/")[0]
        headers = {
            "x-rapidapi-key": API_KEY,
            "x-rapidapi-host": host
        }
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[make_request] erro: {e} - url={url} params={params}")
        return {"response": []}


def normalize_fixture_response(g: dict, sport: str) -> Dict[str, Any]:
    """Normaliza resposta para Football, NBA e NFL"""
    if sport == "football":
        fixture = g.get("fixture", {})
        teams = g.get("teams", {})
        return {
            "game_id": fixture.get("id"),
            "home": teams.get("home", {}).get("name"),
            "away": teams.get("away", {}).get("name"),
            "time": fixture.get("date"),
            "status": fixture.get("status", {}).get("short", "NS"),
        }

    elif sport == "nba":
        teams = g.get("teams", {})
        return {
            "game_id": g.get("id"),
            "home": teams.get("home", {}).get("name"),
            "away": teams.get("visitors", {}).get("name"),
            "time": g.get("date"),
            "status": g.get("status", {}).get("short", "NS"),
        }

    elif sport == "nfl":
        fixture = g.get("fixture", {})
        teams = g.get("teams", {})
        return {
            "game_id": fixture.get("id", g.get("id")),
            "home": teams.get("home", {}).get("name"),
            "away": teams.get("away", {}).get("name"),
            "time": fixture.get("date", g.get("date")),
            "status": fixture.get("status", {}).get("short", "NS"),
        }

    return {}

# -------------------------------
# Endpoints: Partidas
# -------------------------------
@app.get("/partidas-por-esporte/{sport}")
async def get_games_by_sport(sport: str):
    sport = sport.lower()
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte não suportado")

    jogos: List[Dict[str, Any]] = []
    
    if sport == "nba":
        hoje = datetime.utcnow().date()
        for i in range(3):
            data_str = (hoje + timedelta(days=i)).strftime("%Y-%m-%d")
            url = f"{SPORTS_MAP['nba']}games?date={data_str}"
            data_json = make_request(url)
            for g in data_json.get("response", []):
                jogos.append(normalize_fixture_response(g, sport))

    elif sport == "nfl":
        # VALIDAÇÃO: Temporada 2025
        ano = datetime.utcnow().year
        # Lógica para pegar a semana atual aproximada da temporada da NFL no formato correto
        week_num = max(1, (datetime.utcnow() - datetime(ano, 9, 1)).days // 7 + 1)
        url = f"{SPORTS_MAP['nfl']}fixtures"
        params = {"season": ano, "week": f"Regular Season - {week_num}"}
        data_json = make_request(url, params=params)
        for g in data_json.get("response", []):
            jogos.append(normalize_fixture_response(g, sport))

    return jogos

# -------------------------------
# Endpoints: Países e Ligas (apenas Football)
# -------------------------------
@app.get("/paises/{esporte}")
def listar_paises(esporte: str):
    if esporte.lower() != "football":
        return []
    url = f"{SPORTS_MAP['football']}countries"
    dados = make_request(url)
    return dados.get("response", [])

@app.get("/ligas/{esporte}/{pais_code}")
def listar_ligas(esporte: str, pais_code: str):
    if esporte.lower() != "football":
        return []
    url = f"{SPORTS_MAP['football']}leagues"
    dados = make_request(url, params={"code": pais_code})
    return dados.get("response", [])
    
@app.get("/partidas/{esporte}/{id_liga}")
def listar_partidas_por_liga(esporte: str, id_liga: int):
    esporte = esporte.lower()
    if esporte != "football":
        raise HTTPException(status_code=400, detail="Endpoint válido apenas para football")

    # EDIÇÃO DE VALIDAÇÃO: Forçando a busca para a temporada de 2022
    # para testar o acesso a dados históricos permitidos pelo plano gratuito.
    ano_teste = 2022
    
    url = f"{SPORTS_MAP['football']}fixtures"
    params = {
        "league": id_liga,
        "season": ano_teste
    }
    
    dados = make_request(url, params=params)
    
    jogos = [normalize_fixture_response(g, esporte) for g in dados.get("response", [])]
    return jogos

# -------------------------------
# Endpoints: Estatísticas, Eventos, Odds
# -------------------------------
@app.get("/estatisticas/{esporte}/{id_partida}")
def endpoint_estatisticas_partida(esporte: str, id_partida: int):
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    if esporte in ["football", "nfl"]:
        url = f"{SPORTS_MAP[esporte]}fixtures/statistics"
        params = {"fixture": id_partida}
    else:
        url = f"{SPORTS_MAP[esporte]}games/statistics"
        params = {"game": id_partida}
    return make_request(url, params=params).get("response", [])

@app.get("/eventos/{esporte}/{id_partida}")
def endpoint_eventos_partida(esporte: str, id_partida: int):
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    if esporte in ["football", "nfl"]:
        url = f"{SPORTS_MAP[esporte]}fixtures/events"
        params = {"fixture": id_partida}
    else:
        url = f"{SPORTS_MAP[esporte]}games/events"
        params = {"game": id_partida}
    return make_request(url, params=params).get("response", [])

@app.get("/probabilidades/{esporte}/{id_partida}")
def endpoint_probabilidades(esporte: str, id_partida: int):
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    url = f"{SPORTS_MAP[esporte]}odds"
    params = {"fixture": id_partida} if esporte in ["football", "nfl"] else {"game": id_partida}
    return make_request(url, params=params).get("response", [])

# -------------------------------
# Endpoints: Perfil do Tipster
# -------------------------------
@app.get("/perfil-tipster")
def perfil_tipster():
    profile = TIPSTER_PROFILE.copy()
    if profile["total_predictions"]:
        profile["accuracy"] = round(profile["correct_predictions"] / profile["total_predictions"] * 100, 2)
    else:
        profile["accuracy"] = 0.0
    return profile

@app.post("/adicionar-previsao")
def adicionar_previsao(fixture_id: int, previsao: str, esporte: str, resultado: Optional[str] = None):
    TIPSTER_PROFILE["total_predictions"] += 1
    if resultado == "correct":
        TIPSTER_PROFILE["correct_predictions"] += 1
    elif resultado == "wrong":
        TIPSTER_PROFILE["wrong_predictions"] += 1
    TIPSTER_PROFILE["last_predictions"].append({
        "fixture_id": fixture_id,
        "prediction": previsao,
        "sport": esporte,
        "result": resultado,
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"message": "Previsão adicionada com sucesso!"}

# -------------------------------
# Atualizações ao vivo
# -------------------------------
async def atualizar_jogos_ao_vivo(esporte: str, intervalo: int = 300):
    while True:
        try:
            if esporte in ["football", "nba"]:
                hoje = datetime.utcnow().date().strftime("%Y-%m-%d")
                endpoint = "fixtures" if esporte == "football" else "games"
                url = f"{SPORTS_MAP[esporte]}{endpoint}?date={hoje}&live=all"
                dados = make_request(url)
            elif esporte == "nfl":
                ano = datetime.utcnow().year
                week_num = max(1, (datetime.utcnow() - datetime(ano, 9, 1)).days // 7 + 1)
                url = f"{SPORTS_MAP['nfl']}fixtures"
                dados = make_request(url, params={"season": ano, "week": f"Regular Season - {week_num}"})
            print(f"[atualizar_jogos] ({esporte}) ao vivo: {len(dados.get('response', []))}")
        except Exception as e:
            print(f"[atualizar_jogos] erro ({esporte}): {e}")
        await asyncio.sleep(intervalo)

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    for esporte in ["football", "nba", "nfl"]:
        loop.create_task(atualizar_jogos_ao_vivo(esporte, intervalo=300))
    print("Serviço iniciado - atualizações ao vivo (football, nba, nfl).")
