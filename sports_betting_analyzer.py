# Filename: sports_analyzer_live.py
# Versão: 5.x (clean) - apenas Football, NBA e NFL

import os
import requests
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any

# ================================
# Inicialização do FastAPI
# ================================
app = FastAPI(title="Tipster Ao Vivo - Football, NBA e NFL")

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

# ================================
# Configuração da API Key
# ================================
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise Exception("API_KEY não definida no ambiente! Defina a variável de ambiente API_KEY.")

# ================================
# Mapas de esportes e URLs base
# ================================
SPORTS_MAP = {
    "football": "https://v3.football.api-sports.io/",
    "nba": "https://v2.nba.api-sports.io/",
    "nfl": "https://v1.american-football.api-sports.io/"
}

# ================================
# Perfis detalhados do Tipster
# ================================
TIPSTER_PROFILES_DETAILED: Dict[str, Dict[str, Any]] = {
    "football": {
        "indicators": ["Forma recente", "xG", "Gols marcados/sofridos", "Odds"],
        "typical_picks": ["1X2", "Over/Under", "BTTS", "Escanteios", "Cartões"]
    },
    "nba": {
        "indicators": ["Pontos por jogo", "FG%", "Rebotes", "Assistências", "Turnovers"],
        "typical_picks": ["Moneyline", "Spread", "Over/Under pontos"]
    },
    "nfl": {
        "indicators": ["Jardas médias", "Turnovers", "Eficiência Red Zone", "3rd Down"],
        "typical_picks": ["Moneyline", "Spread", "Over/Under pontos", "Props QB"]
    }
}

# ================================
# Perfil agregado do Tipster
# ================================
TIPSTER_PROFILE: Dict[str, Any] = {
    "total_predictions": 0,
    "correct_predictions": 0,
    "wrong_predictions": 0,
    "last_predictions": []
}

# ================================
# Utilitário de requisição
# ================================
def make_request(url: str, params: dict = None) -> dict:
    try:
        host = url.split("//")[1].split("/")[0]
        headers = {
            "x-rapidapi-key": API_KEY,
            "x-rapidapi-host": host
        }
        resp = requests.get(url, headers=headers, params=params, timeout=12)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[make_request] erro: {e} - url={url} params={params}")
        return {"response": []}

# ================================
# Helpers estatísticos
# ================================
def get_last_matches_stats_football(team_id: int, n: int = 5) -> Dict[str, Any]:
    if not team_id:
        return {"media_gols": 0.0, "taxa_vitoria": 0.0}
    url = f"{SPORTS_MAP['football']}fixtures"
    params = {"team": team_id, "last": n}
    data = make_request(url, params=params)
    jogos = data.get("response", [])
    gols, vitorias = 0, 0
    for j in jogos:
        g = j.get("goals", {})
        home_id = j.get("teams", {}).get("home", {}).get("id")
        if home_id == team_id:
            gf, ga = g.get("home", 0), g.get("away", 0)
        else:
            gf, ga = g.get("away", 0), g.get("home", 0)
        gols += gf
        if gf > ga:
            vitorias += 1
    return {
        "media_gols": round(gols/len(jogos),2) if jogos else 0,
        "taxa_vitoria": round((vitorias/len(jogos))*100,2) if jogos else 0
    }

def get_last_matches_stats_basketball(team_id: int, n: int = 5, sport: str = "nba") -> Dict[str, Any]:
    if not team_id:
        return {"media_feitos": 0.0, "media_sofridos": 0.0}
    url = f"{SPORTS_MAP[sport]}games"
    params = {"team": team_id, "last": n}
    data = make_request(url, params=params)
    jogos = data.get("response", [])
    pts_for, pts_against = 0, 0
    for j in jogos:
        s = j.get("scores", {})
        home_id = j.get("teams", {}).get("home", {}).get("id")
        if home_id == team_id:
            pts_for += s.get("home", {}).get("total", 0)
            pts_against += s.get("away", {}).get("total", 0)
        else:
            pts_for += s.get("away", {}).get("total", 0)
            pts_against += s.get("home", {}).get("total", 0)
    return {
        "media_feitos": round(pts_for/len(jogos),2) if jogos else 0,
        "media_sofridos": round(pts_against/len(jogos),2) if jogos else 0
    }

# ================================
# Normalizador de fixtures
# ================================
def normalize_fixture_response(g: dict) -> Dict[str, Any]:
    fixture = g.get("fixture", g)
    teams = g.get("teams", {})
    return {
        "game_id": fixture.get("id", g.get("id")),
        "home": teams.get("home", {}).get("name", "Casa"),
        "away": teams.get("away", {}).get("name", "Fora"),
        "home_id": teams.get("home", {}).get("id"),
        "away_id": teams.get("away", {}).get("id"),
        "time": fixture.get("date", "?"),
        "status": fixture.get("status", {}).get("short", "NS") if isinstance(fixture.get("status"), dict) else fixture.get("status", "NS")
    }

# ================================
# Endpoint: Partidas por esporte
# ================================
@app.get("/partidas-por-esporte/{sport}")
async def get_games_by_sport(sport: str):
    sport = sport.lower()
    if sport not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte não suportado")
    hoje = datetime.utcnow().date()
    jogos: List[Dict[str, Any]] = []
    for i in range(3):
        data_str = (hoje + timedelta(days=i)).strftime("%Y-%m-%d")
        endpoint = "fixtures" if sport == "football" else "games"
        url = f"{SPORTS_MAP[sport]}{endpoint}?date={data_str}"
        data_json = make_request(url)
        for g in data_json.get("response", []):
            jogos.append(normalize_fixture_response(g))
    return jogos

# ================================
# Endpoints auxiliares
# ================================
@app.get("/estatisticas/{esporte}/{id_partida}")
def endpoint_estatisticas_partida(esporte: str, id_partida: int):
    if esporte not in SPORTS_MAP:
        raise HTTPException(status_code=400, detail="Esporte inválido")
    if esporte == "football":
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
    if esporte == "football":
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
    return make_request(url, params={"fixture": id_partida} if esporte=="football" else {"game": id_partida}).get("response", [])

# ================================
# Analisar Pré-Jogo
# ================================
@app.get("/analisar-pre-jogo")
def analisar_pre_jogo(game_id: int, sport: str):
    sport = sport.lower()

    def build_pick(market, suggestion, score, indicators):
        prob = int(min(95, max(5, round(score * 100))))
        justification = " | ".join([f"{k}: {v}" for k,v in indicators.items()])
        return {"market": market, "suggestion": suggestion, "confidence": prob, "justification": justification}

    if sport == "football":
        fixture = make_request(f"{SPORTS_MAP['football']}fixtures", {"id": game_id}).get("response", [])
        if not fixture: return [{"market":"N/A","suggestion":"Partida não encontrada","confidence":0,"justification":"Game inválido"}]
        f = fixture[0]
        home, away = f.get("teams", {}).get("home", {}), f.get("teams", {}).get("away", {})
        h_stats = get_last_matches_stats_football(home.get("id"))
        a_stats = get_last_matches_stats_football(away.get("id"))
        avg = h_stats["media_gols"] + a_stats["media_gols"]
        line = round(avg*1.05,2) or 2.5
        prob_over = min(0.99, max(0.01, avg/line))
        if prob_over > 0.6:
            return [build_pick("Over/Under", f"Over {line} gols", prob_over, {"avg_gols": avg})]
        else:
            return [build_pick("Under/Over", f"Under {line} gols", 1-prob_over, {"avg_gols": avg})]

    if sport == "nba":
        fixture = make_request(f"{SPORTS_MAP['nba']}games", {"id": game_id}).get("response", [])
        if not fixture: return [{"market":"N/A","suggestion":"Jogo não encontrado","confidence":0,"justification":"Game inválido"}]
        f = fixture[0]
        home, away = f.get("teams", {}).get("home", {}), f.get("teams", {}).get("away", {})
        h_stats = get_last_matches_stats_basketball(home.get("id"),7,"nba")
        a_stats = get_last_matches_stats_basketball(away.get("id"),7,"nba")
        avg = h_stats["media_feitos"] + a_stats["media_feitos"]
        line = round(avg*0.98,1)
        prob_over = min(0.99,max(0.01,avg/line))
        if prob_over > 0.65:
            return [build_pick("Total pontos", f"Over {line}", prob_over, {"avg_pts": avg})]
        else:
            return [build_pick("Total pontos", f"Under {line}", 1-prob_over, {"avg_pts": avg})]

    if sport == "nfl":
        fixture = make_request(f"{SPORTS_MAP['nfl']}games", {"id": game_id}).get("response", [])
        if not fixture: return [{"market":"N/A","suggestion":"Jogo não encontrado","confidence":0,"justification":"Game inválido"}]
        f = fixture[0]
        scores = f.get("scores", {})
        avg = (scores.get("home", {}).get("total",0)+scores.get("away", {}).get("total",0))/2 or 21
        line = avg*1.1
        prob_over = min(0.95,max(0.05,avg/line))
        return [build_pick("Total pontos", f"Over {line}", prob_over, {"avg_pts": avg})]

# ================================
# Analisar Ao Vivo
# ================================
@app.get("/analisar-ao-vivo")
def analisar_ao_vivo(game_id: int, sport: str):
    sport = sport.lower()

    def build_pick(market, suggestion, score, indicators):
        prob = int(min(95, max(5, round(score * 100))))
        justification = " | ".join([f"{k}: {v}" for k,v in indicators.items()])
        return {"market": market, "suggestion": suggestion, "confidence": prob, "justification": justification}

    if sport == "football":
        data = make_request(f"{SPORTS_MAP['football']}fixtures", {"id": game_id,"live":"all"}).get("response", [])
        if not data: return [{"market":"N/A","suggestion":"Partida não encontrada","confidence":0,"justification":"Game inválido"}]
        stats = data[0].get("statistics", [])
        possession = shots = fouls = 0
        for t in stats:
            for s in t.get("statistics", []):
                if s.get("type")=="Ball Possession":
                    possession = max(possession,int(str(s.get("value","0")).replace("%","")))
                if s.get("type") in ["Shots on Target","Shots on Goal"]:
                    shots += int(s.get("value",0))
                if s.get("type")=="Fouls":
                    fouls += int(s.get("value",0))
        if possession>=65 and shots>=2:
            return [build_pick("Próximo Gol","Equipe dominante marcará",0.85,{"posse":possession,"chutes":shots})]
        if fouls>=15:
            return [build_pick("Cartões","Over cartões",0.7,{"faltas":fouls})]
        return [build_pick("Aguardar","Sem trigger",0.4,{"posse":possession,"chutes":shots,"faltas":fouls})]

    if sport == "nba":
        data = make_request(f"{SPORTS_MAP['nba']}games", {"id": game_id,"live":"all"}).get("response", [])
        if not data: return [{"market":"N/A","suggestion":"Jogo não encontrado","confidence":0,"justification":"Game inválido"}]
        f = data[0]
        scores = f.get("scores", {})
        total_pts = sum((p.get("home",0) or 0)+(p.get("away",0) or 0) for p in scores.values() if isinstance(p,dict))
        if total_pts>=110:
            return [build_pick("Over pontos","Jogo em ritmo acelerado",0.8,{"total_pts":total_pts})]
        return [build_pick("Aguardar","Sem trigger",0.4,{"total_pts":total_pts})]

    if sport == "nfl":
        data = make_request(f"{SPORTS_MAP['nfl']}games", {"id": game_id,"live":"all"}).get("response", [])
        if not data: return [{"market":"N/A","suggestion":"Jogo não encontrado","confidence":0,"justification":"Game inválido"}]
        f = data[0]
        scores = f.get("scores", {})
        total_pts = sum((p.get("home",0) or 0)+(p.get("away",0) or 0) for p in scores.values() if isinstance(p,dict))
        if total_pts>=28:
            return [build_pick("Over pontos","Jogo ofensivo",0.7,{"total_pts":total_pts})]
        return [build_pick("Aguardar","Sem trigger",0.4,{"total_pts":total_pts})]

# ================================
# Perfil do Tipster
# ================================
@app.get("/perfil-tipster")
def perfil_tipster():
    profile = TIPSTER_PROFILE.copy()
    if profile["total_predictions"]:
        profile["accuracy"] = round(profile["correct_predictions"]/profile["total_predictions"]*100,2)
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

# ================================
# Atualização ao vivo
# ================================
async def atualizar_jogos_ao_vivo(esporte: str, intervalo: int = 300):
    while True:
        try:
            hoje = datetime.utcnow().date().strftime("%Y-%m-%d")
            endpoint = "fixtures" if esporte=="football" else "games"
            url = f"{SPORTS_MAP[esporte]}{endpoint}?date={hoje}&live=all"
            dados = make_request(url)
            print(f"[atualizar_jogos] ({esporte}) jogos ao vivo hoje: {len(dados.get('response', []))}")
        except Exception as e:
            print(f"[atualizar_jogos] erro ({esporte}): {e}")
        await asyncio.sleep(intervalo)

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    for esporte in ["football", "nba", "nfl"]:
        loop.create_task(atualizar_jogos_ao_vivo(esporte, intervalo=300))
    print("Serviço iniciado - atualizações ao vivo (football, nba, nfl).")
