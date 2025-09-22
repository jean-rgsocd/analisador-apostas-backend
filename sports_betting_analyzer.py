# sports_betting_analyzer.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import requests, os, time, traceback

app = FastAPI(title="Tipster IA - API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

API_SPORTS_KEY = os.environ.get("API_SPORTS_KEY", "7baa5e00c8ae57d0e6240f790c6840dd")

API_CONFIG = {
    "football": {
        "url": "https://v3.football.api-sports.io/fixtures",
        "host": "v3.football.api-sports.io",
       
    },
    "nba": {
        "url": "https://v2.nba.api-sports.io/games",
        "host": "v2.nba.api-sports.io",
        
    },
    "nfl": {
        "url": "https://v1.american-football.api-sports.io/fixtures",
        "host": "v1.american-football.api-sports.io",
        
    }
}

CACHE_TTL = 12
_cache: Dict[str, Dict[str, Any]] = {}

def _cache_get(key: str):
    rec = _cache.get(key)
    if not rec:
        return None
    if time.time() - rec["ts"] > CACHE_TTL:
        _cache.pop(key, None)
        return None
    return rec["data"]

def _cache_set(key: str, data):
    _cache[key] = {"ts": time.time(), "data": data}

def api_get(sport: str, params: dict):
    cfg = API_CONFIG[sport]
    headers = {
        "x-apisports-key": API_SPORTS_KEY,
        # compatibilidade, pode remover se não usar RapidAPI:
        "x-rapidapi-key": API_SPORTS_KEY,
        "x-rapidapi-host": cfg["host"]
    }
    url = cfg["url"]
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=25)
        r.raise_for_status()
        j = r.json()
        resp = j.get("response", [])
        if not resp:
            print(f"[api_get] {sport} {url} params={params} -> empty response, status={r.status_code}, body_preview={str(j)[:300]}")
        return resp
    except Exception as e:
        print(f"[api_get] {sport} {url} {params} -> {e}")
        print(traceback.format_exc())
        return []

def api_get_raw(sport: str, path: str, params: dict=None):
    cfg = API_CONFIG[sport]
    headers = {
        "x-apisports-key": API_SPORTS_KEY,
        "x-rapidapi-key": API_SPORTS_KEY,
        "x-rapidapi-host": cfg["host"]
    }
    url = f"{cfg['url'].rsplit('/',1)[0]}/{path}"
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[api_get_raw] {url} {params} -> {e}")
        try:
            print("response_text_preview:", r.text[:400])
        except:
            pass
        return None

def normalize_game(sport: str, raw: dict) -> dict:
    if sport == "football":
        fixture = raw.get("fixture", {})
        league = raw.get("league", {}) or {}
        teams = raw.get("teams", {}) or {}
        status = fixture.get("status", {}) or {}
        gid = fixture.get("id")
        date = fixture.get("date")
        league_obj = {
            "id": league.get("id"),
            "name": league.get("name"),
            "country": league.get("country"),
            "season": league.get("season")
        }
        return {
            "game_id": gid,
            "date": date,
            "league": league_obj,
            "teams": teams,
            "status": status,
            "type": ("live" if status.get("elapsed") else "scheduled"),
            "raw": raw
        }
    else:
        # NBA / NFL generic
        gid = raw.get("id") or raw.get("game", {}).get("id")
        date = raw.get("date") or raw.get("fixture", {}).get("date")
        league = raw.get("league") or {}
        status = raw.get("status") or raw.get("fixture", {}).get("status", {})
        teams = raw.get("teams") or {}
        if not teams:
            home = raw.get("home") or raw.get("home_team") or {}
            away = raw.get("away") or raw.get("away_team") or {}
            teams = {"home": home or {}, "away": away or {}}
        league_obj = {"id": league.get("id"), "name": league.get("name")}
        return {
            "game_id": gid,
            "date": date,
            "league": league_obj,
            "teams": teams,
            "status": status,
            "type": ("live" if status.get("elapsed") else "scheduled"),
            "raw": raw
        }

def is_future_or_live(normalized_game: dict) -> bool:
    status = normalized_game.get("status") or {}
    if status.get("elapsed") is not None:
        return True
    short = (status.get("short") or "").upper()
    long = (status.get("long") or "").lower()
    if short in ("FT","AET") or "finished" in long or "match finished" in long:
        return False
    date_s = normalized_game.get("date")
    if not date_s:
        return False
    try:
        dt = datetime.fromisoformat(date_s.replace("Z","+00:00"))
    except:
        try:
            dt = datetime.strptime(date_s, "%Y-%m-%dT%H:%M:%S%z")
        except:
            return False
    now = datetime.now(timezone.utc)
    if dt < now:
        return False
    return True

def get_dates(days_forward=2):
    today = datetime.utcnow().date()
    # retorna hoje + next days_forward days (inclusive)
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_forward+1)]

# --- lists endpoints ---
@app.get("/futebol")
def futebol_all():
    ck = "futebol_all_v2"
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    results = []
    # live
    live = api_get("football", {"live":"all"})
    for r in live:
        g = normalize_game("football", r)
        if is_future_or_live(g):
            results.append(g)
    # próximos 2 dias (hoje + 2)
    for d in get_dates(2):
        data = api_get("football", {"date": d})
        for r in data:
            g = normalize_game("football", r)
            if is_future_or_live(g):
                results.append(g)
    results = sorted(results, key=lambda x: (0 if x.get("status", {}).get("elapsed") else 1, x.get("date") or ""))
    _cache_set(ck, results)
    return results

@app.get("/nba")
def nba_all():
    ck = "nba_all_v2"
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    results = []
    # Jogos ao vivo
    live = api_get("nba", {"live": "all"})
    for r in live:
        g = normalize_game("nba", r)
        if is_future_or_live(g):
            results.append(g)
    # Próximos 10 dias (hoje + 10)
    for d in get_dates(10):
        data = api_get("nba", {"date": d})
        for r in data:
            g = normalize_game("nba", r)
            if is_future_or_live(g):
                results.append(g)
    results = sorted(results, key=lambda x: (0 if x.get("status", {}).get("elapsed") else 1, x.get("date") or ""))
    _cache_set(ck, results)
    return results

@app.get("/nfl")
def nfl_all():
    ck = "nfl_all_v2"
    cached = _cache_get(ck)
    if cached is not None:
        return cached
    results = []
    # Jogos ao vivo
    live = api_get("nfl", {"live": "all"})
    for r in live:
        g = normalize_game("nfl", r)
        if is_future_or_live(g):
            results.append(g)

    # Próximos 10 dias (hoje + 10) - usa "date" por dia
    for d in get_dates(10):
        data = api_get("nfl", {"date": d})
        for r in data:
            g = normalize_game("nfl", r)
            if is_future_or_live(g):
                results.append(g)

    results = sorted(results, key=lambda x: (0 if x.get("status", {}).get("elapsed") else 1, x.get("date") or ""))
    _cache_set(ck, results)
    return results

# helper endpoints for frontend
@app.get("/countries")
def countries():
    games = futebol_all()
    countries = sorted(list({(g.get("league") or {}).get("country") for g in games if (g.get("league") or {}).get("country")}))
    return [c for c in countries if c]

@app.get("/leagues")
def leagues(country: str = Query(...)):
    games = futebol_all()
    league_map = {}
    for g in games:
        lg = g.get("league") or {}
        if lg.get("country") == country:
            league_map[lg.get("id")] = lg
    return list(league_map.values())

@app.get("/games")
def games(sport: str = Query(...), league: int = Query(None)):
    sport = sport.lower()
    if sport == "football":
        all_games = futebol_all()
        if league:
            filtered = [g for g in all_games if (g.get("league") or {}).get("id") == int(league)]
        else:
            filtered = all_games
        return filtered
    elif sport == "nba":
        return nba_all()
    elif sport == "nfl":
        return nfl_all()
    else:
        return []

# ---- ANALYZE ----
def fetch_football_statistics(fixture_id: int):
    return api_get_raw("football", "fixtures/statistics", params={"fixture": fixture_id})

def safe_int(v):
    try: return int(v)
    except:
        try: return int(float(v))
        except: return 0

def build_stats_map(stats_raw):
    out = {}
    if not stats_raw: return out
    data = stats_raw.get("response") if isinstance(stats_raw, dict) and "response" in stats_raw else stats_raw
    if isinstance(data, list):
        for item in data:
            team = item.get("team") or {}
            tid = team.get("id")
            out[tid] = {}
            for s in item.get("statistics", []) or []:
                k = (s.get("type") or s.get("name") or "").strip()
                v = s.get("value")
                if isinstance(v, str) and "/" in v:
                    try: v = int(v.split("/")[0])
                    except: v = safe_int(v)
                else:
                    v = safe_int(v)
                out[tid][k] = v
    return out

def heuristics_football(fixture_raw, stats_map):
    home = fixture_raw.get("teams", {}).get("home", {}) or {}
    away = fixture_raw.get("teams", {}).get("away", {}) or {}
    home_id = home.get("id"); away_id = away.get("id")
    home_stats = stats_map.get(home_id, {}) or {}; away_stats = stats_map.get(away_id, {}) or {}

    def g(d, *keys):
        for k in keys:
            if k in d: return d[k]
        return 0

    h_shots = g(home_stats, "Shots", "Total Shots", "Shots on Goal", "Shots on Target")
    h_sot = g(home_stats, "Shots on Goal", "Shots on Target", "On Target")
    h_corners = g(home_stats, "Corner", "Corners")
    h_fouls = g(home_stats, "Fouls", "Fouls committed")
    h_pos = g(home_stats, "Ball Possession", "Possession", "Possession %")
    a_shots = g(away_stats, "Shots", "Total Shots", "Shots on Goal", "Shots on Target")
    a_sot = g(away_stats, "Shots on Goal", "Shots on Target")
    a_corners = g(away_stats, "Corner", "Corners")
    a_fouls = g(away_stats, "Fouls")
    a_pos = g(away_stats, "Ball Possession", "Possession", "Possession %")

    def norm_pos(x):
        if isinstance(x, str) and "%" in x:
            try: return int(x.replace("%","").strip())
            except: return 0
        try: return int(x)
        except: return 0
    h_pos = norm_pos(h_pos); a_pos = norm_pos(a_pos)

    h_power = h_sot*1.6 + h_shots*0.6 + h_corners*0.35 + (h_pos*0.2) - (h_fouls*0.1)
    a_power = a_sot*1.6 + a_shots*0.6 + a_corners*0.35 + (a_pos*0.2) - (a_fouls*0.1)
    power_diff = h_power - a_power

    combined_sot = h_sot + a_sot
    combined_shots = h_shots + a_shots
    combined_corners = h_corners + a_corners

    preds = []

    # Over/Under 2.5
    over_conf = 0.25
    reasons = []
    if combined_sot >= 6 or combined_shots >= 24:
        over_conf = 0.9; reasons.append("Alta atividade ofensiva: muitos chutes e chutes no alvo.")
    elif combined_sot >= 4 or combined_shots >= 16:
        over_conf = 0.6; reasons.append("Atividade ofensiva moderada.")
    else:
        over_conf = 0.25; reasons.append("Pouca atividade ofensiva.")
    preds.append({
        "market":"over_2_5",
        "recommendation": "OVER 2.5" if over_conf>=0.5 else "UNDER 2.5",
        "confidence": round(over_conf,2),
        "reason":" ".join(reasons)
    })

    # BTTS
    btts_conf = 0.3
    if h_sot>=2 and a_sot>=2: btts_conf=0.9
    elif h_sot>=1 and a_sot>=1: btts_conf=0.6
    preds.append({
        "market":"btts",
        "recommendation":"SIM" if btts_conf>=0.5 else "NAO",
        "confidence":round(btts_conf,2),
        "reason":"Atividade ofensiva de ambos os times."
    })

    # Corners
    corners_conf = 0.25
    if combined_corners >= 10: corners_conf=0.85
    elif combined_corners >=7: corners_conf=0.6
    preds.append({
        "market":"corners_over_8_5",
        "recommendation":"OVER 8.5" if corners_conf>=0.5 else "UNDER 8.5",
        "confidence":round(corners_conf,2),
        "reason":"Baseado no número de escanteios registrados."
    })

    # Moneyline
    ml_reco = "Sem favorito definido"; ml_conf = 0.35
    if power_diff>6:
        ml_reco="Vitória Casa"; ml_conf = min(0.95, 0.5 + power_diff/30)
    elif power_diff<-6:
        ml_reco="Vitória Visitante"; ml_conf = min(0.95, 0.5 + (-power_diff)/30)
    preds.append({"market":"moneyline","recommendation":ml_reco,"confidence":round(ml_conf,2),"reason":"Comparação de atividade ofensiva e posse."})

    # Handicap -0.5
    if abs(power_diff)>=10:
        handicap = ("Casa -0.5" if power_diff>0 else "Visitante -0.5")
        preds.append({"market":"handicap_0_5","recommendation":handicap,"confidence":round(min(0.95,0.4+abs(power_diff)/30),2),"reason":"Diferença significativa de força."})
    else:
        preds.append({"market":"handicap_0_5","recommendation":"Sem handicap indicado","confidence":0.25,"reason":"Diferença insuficiente para handicap."})

    # Double chance
    dc_reco = "Sem recomendação clara"
    if ml_conf>=0.7:
        dc_reco = "1X" if ml_reco=="Vitória Casa" else "X2"
    preds.append({"market":"double_chance","recommendation":dc_reco,"confidence":round(ml_conf,2),"reason":"Proteção para favorito com confiança."})

    summary = {
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_power": round(h_power,2),
        "away_power": round(a_power,2),
        "combined_shots": combined_shots,
        "combined_sot": combined_sot,
        "combined_corners": combined_corners
    }
    return preds, summary

@app.get("/analyze")
def analyze(game_id: int = Query(...), sport: str = Query("football", enum=["football","nba","nfl"])):
    sport = sport.lower()
    if sport=="football":
        fixtures = api_get("football", {"id": game_id})
        if not fixtures:
            raise HTTPException(status_code=404, detail="Jogo não encontrado")
        fixture = fixtures[0]
        stats_raw = fetch_football_statistics(game_id) or {}
        stats_map = build_stats_map(stats_raw or {})
        preds, summary = heuristics_football(fixture, stats_map)
        return {"game_id": game_id, "sport": sport, "summary": summary, "predictions": preds, "raw_fixture": fixture, "raw_stats": stats_raw}
    else:
        fixtures = api_get(sport, {"id": game_id})
        if not fixtures:
            raise HTTPException(status_code=404, detail="Jogo não encontrado")
        fixture = fixtures[0]
        status = fixture.get("status", {})
        elapsed = status.get("elapsed")
        home = fixture.get("teams", {}).get("home", {}) or {}
        away = fixture.get("teams", {}).get("away", {}) or {}
        preds=[]
        if elapsed is not None:
            # jogo ao vivo
            home_score = fixture.get("score", {}).get("home")
            away_score = fixture.get("score", {}).get("away")
            if home_score is not None and away_score is not None:
                if home_score > away_score:
                    preds.append({"market":"moneyline","recommendation":"Vitória Casa","confidence":0.75,"reason":"Time da casa na frente."})
                elif away_score > home_score:
                    preds.append({"market":"moneyline","recommendation":"Vitória Visitante","confidence":0.75,"reason":"Visitante na frente."})
                else:
                    preds.append({"market":"moneyline","recommendation":"Sem favorito definido","confidence":0.35,"reason":"Empate."})
            else:
                preds.append({"market":"moneyline","recommendation":"Sem dados","confidence":0.2,"reason":"Dados limitados."})
        else:
            preds.append({"market":"moneyline","recommendation":"Sem dados","confidence":0.2,"reason":"Dados limitados."})

        return {
            "game_id": game_id,
            "sport": sport,
            "summary": {"home": home.get("name"), "away": away.get("name")},
            "predictions": preds,
            "raw_fixture": fixture
        }
