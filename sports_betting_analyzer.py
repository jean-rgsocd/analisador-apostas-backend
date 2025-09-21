# sports_betting_analyzer.py
# Tipster IA com endpoint /analyze
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import requests, time, traceback

app = FastAPI(title="Tipster IA - API (with Analyze)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# move to env var in production
API_SPORTS_KEY = "7baa5e00c8ae57d0e6240f790c6840dd"

API_CONFIG = {
    "football": {"url": "https://v3.football.api-sports.io", "host": "v3.football.api-sports.io", "endpoint": "fixtures"},
    "nba":      {"url": "https://v2.nba.api-sports.io",        "host": "v2.nba.api-sports.io",        "endpoint": "games"},
    "nfl":      {"url": "https://v2.nfl.api-sports.io",        "host": "v2.nfl.api-sports.io",        "endpoint": "games"}
}

CACHE_TTL = 12
_cache = {}

def _cache_get(key):
    rec = _cache.get(key)
    if not rec: return None
    if time.time() - rec["ts"] > CACHE_TTL:
        _cache.pop(key, None)
        return None
    return rec["data"]

def _cache_set(key, data):
    _cache[key] = {"ts": time.time(), "data": data}

def api_get_raw(cfg, path, params=None):
    """Generic GET to custom path relative to cfg['url']"""
    headers = {"x-rapidapi-key": API_SPORTS_KEY, "x-rapidapi-host": cfg["host"]}
    url = f"{cfg['url']}/{path}"
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=25)
        r.raise_for_status()
        return r.json().get("response", [])
    except Exception as e:
        print(f"[api_get_raw] {url} {params} -> {e}")
        print(traceback.format_exc())
        return []

def api_fetch(sport: str, params: dict) -> List[Dict[str, Any]]:
    cfg = API_CONFIG[sport]
    headers = {"x-rapidapi-key": API_SPORTS_KEY, "x-rapidapi-host": cfg["host"]}
    url = f"{cfg['url']}/{cfg['endpoint']}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=25)
        resp.raise_for_status()
        return resp.json().get("response", [])
    except Exception as e:
        print(f"[api_fetch] {sport} {url} {params} -> {e}")
        print(traceback.format_exc())
        return []

def parse_possession(v):
    if v is None: return None
    if isinstance(v, str) and "%" in v:
        try: return int(v.replace("%","").strip())
        except: pass
    try: return int(v)
    except: return None

def normalize_game(sport: str, raw: dict) -> dict:
    # map various shapes to common format
    if sport == "football":
        fixture = raw.get("fixture", {})
        return {
            "game_id": fixture.get("id"),
            "date": fixture.get("date"),
            "league": {
                "id": raw.get("league", {}).get("id"),
                "name": raw.get("league", {}).get("name"),
                "country": raw.get("league", {}).get("country"),
                "season": raw.get("league", {}).get("season")
            },
            "teams": raw.get("teams", {}),
            "status": fixture.get("status", {}),
            "raw": raw
        }
    else:
        # nba / nfl normalization (best effort)
        game_id = raw.get("id") or raw.get("game", {}).get("id")
        date = raw.get("date") or raw.get("fixture", {}).get("date")
        teams = raw.get("teams")
        if not teams:
            # try other shapes
            home = raw.get("home") or raw.get("home_team")
            away = raw.get("away") or raw.get("away_team") or raw.get("visitors")
            teams = {"home": home or {}, "away": away or {}}
        league = raw.get("league") or {}
        status = raw.get("status") or raw.get("fixture", {}).get("status", {})
        return {"game_id": game_id, "date": date, "league": {"id": league.get("id"), "name": league.get("name")}, "teams": teams, "status": status, "raw": raw}

def is_future_or_live(raw_game: dict) -> bool:
    # Accept if live (status.elapsed present) OR date >= today (future or later today but not finished)
    status = raw_game.get("status") or {}
    # live detection
    elapsed = status.get("elapsed")
    if elapsed is not None:
        return True
    # if status short or long indicates finished, reject
    short = (status.get("short") or "").upper()
    long = (status.get("long") or "").lower()
    if short in ("FT","AET") or "finished" in long or "match finished" in long:
        return False
    # otherwise check date
    date_s = raw_game.get("date")
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
    # if scheduled and in the past (strictly less than now) and not live -> exclude
    if dt < now:
        return False
    return True

def get_dates_list(days=2):
    today = datetime.utcnow().date()
    return [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days+1)]

# -------- endpoints to get games (same as before) but filter out finished games ----------
@app.get("/futebol")
def futebol_all():
    cache_key = "futebol_all_v2"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    results = []
    # live
    live = api_fetch("football", {"live":"all"})
    for r in live:
        g = normalize_game("football", r)
        if is_future_or_live(g):
            results.append(g)
    # hoje + 2 dias (future only)
    for d in get_dates_list(2):
        data = api_fetch("football", {"date": d})
        for r in data:
            g = normalize_game("football", r)
            if is_future_or_live(g):
                results.append(g)
    # sort
    results = sorted(results, key=lambda x: (0 if x["status"].get("elapsed") else 1, x["date"] or ""))
    _cache_set(cache_key, results)
    return results

@app.get("/nba")
def nba_all():
    cache_key = "nba_all_v2"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    results = []
    live = api_fetch("nba", {"live":"all"})
    for r in live:
        g = normalize_game("nba", r)
        if is_future_or_live(g):
            results.append(g)
    for d in get_dates_list(2):
        data = api_fetch("nba", {"date": d})
        for r in data:
            g = normalize_game("nba", r)
            if is_future_or_live(g):
                results.append(g)
    results = sorted(results, key=lambda x: (0 if x["status"].get("elapsed") else 1, x["date"] or ""))
    _cache_set(cache_key, results)
    return results

@app.get("/nfl")
def nfl_all():
    cache_key = "nfl_all_v2"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    results = []
    live = api_fetch("nfl", {"live":"all"})
    for r in live:
        g = normalize_game("nfl", r)
        if is_future_or_live(g):
            results.append(g)
    for d in get_dates_list(2):
        data = api_fetch("nfl", {"date": d})
        for r in data:
            g = normalize_game("nfl", r)
            if is_future_or_live(g):
                results.append(g)
    results = sorted(results, key=lambda x: (0 if x["status"].get("elapsed") else 1, x["date"] or ""))
    _cache_set(cache_key, results)
    return results

# ---------------- TIPSTER ANALYZE ----------------
def fetch_football_statistics(fixture_id: int):
    cfg = API_CONFIG["football"]
    return api_get_raw(cfg, "fixtures/statistics", {"fixture": fixture_id})

def safe_int(v):
    try:
        return int(v)
    except:
        try:
            return int(float(v))
        except:
            return 0

def build_stats_map(stats_raw):
    # stats_raw: list of dicts: [{ "team": {...}, "statistics": [ { "type": "...", "value": ...} ] }, ...]
    out = {"home":{}, "away":{}}
    try:
        for team_stats in stats_raw:
            team = team_stats.get("team",{}) or {}
            team_id = team.get("id")
            # We'll decide side externally
            stats_list = team_stats.get("statistics", []) or []
            kmap = {}
            for s in stats_list:
                key = (s.get("type") or s.get("name") or "").strip()
                val = s.get("value")
                # value can be string "5" or "3/1" etc
                if isinstance(val, str) and "/" in val:
                    # sometimes "total/on target"
                    parts = val.split("/")
                    try:
                        val_parsed = int(parts[0])
                    except:
                        val_parsed = safe_int(parts[0])
                else:
                    val_parsed = safe_int(val)
                kmap[key] = val_parsed
            out[team_id] = kmap
    except Exception as e:
        print("build_stats_map error", e)
    return out

def heuristics_football(fixture_raw, stats_map):
    # teams
    home = fixture_raw.get("teams", {}).get("home", {})
    away = fixture_raw.get("teams", {}).get("away", {})
    home_id = home.get("id")
    away_id = away.get("id")
    home_stats = stats_map.get(home_id, {}) or {}
    away_stats = stats_map.get(away_id, {}) or {}

    # helper fetch common keys (tries several variants)
    def get_stat(d, *keys):
        for k in keys:
            if k in d:
                return d[k]
        return 0

    # common stats
    h_shots = get_stat(home_stats, "Shots", "Total Shots", "Shots on Goal", "Shots on Target", "shots")
    h_sot = get_stat(home_stats, "Shots on Goal", "Shots on Target", "On Target", "Shots on target")
    h_corners = get_stat(home_stats, "Corner", "Corners", "corners")
    h_fouls = get_stat(home_stats, "Fouls", "Fouls committed", "fouls")
    h_pos = get_stat(home_stats, "Possession", "Possession %") or get_stat(home_stats, "possession")
    a_shots = get_stat(away_stats, "Shots", "Total Shots", "Shots on Goal", "Shots on Target", "shots")
    a_sot = get_stat(away_stats, "Shots on Goal", "Shots on Target", "On Target", "Shots on target")
    a_corners = get_stat(away_stats, "Corner", "Corners", "corners")
    a_fouls = get_stat(away_stats, "Fouls", "fouls")
    a_pos = get_stat(away_stats, "Possession", "Possession %") or get_stat(away_stats, "possession")

    # normalize possession strings
    def norm_pos(x):
        if isinstance(x, str):
            try: return int(x.replace("%","").strip())
            except: return 0
        return int(x or 0)
    h_pos = norm_pos(h_pos)
    a_pos = norm_pos(a_pos)

    # power score (simple)
    h_power = h_sot*1.6 + h_shots*0.6 + h_corners*0.35 + (h_pos*0.2) - (h_fouls*0.1)
    a_power = a_sot*1.6 + a_shots*0.6 + a_corners*0.35 + (a_pos*0.2) - (a_fouls*0.1)
    power_diff = h_power - a_power

    # combined metrics
    combined_sot = h_sot + a_sot
    combined_shots = h_shots + a_shots
    combined_corners = h_corners + a_corners

    # predictions container
    preds = []

    # Over 2.5
    over_conf = 0.0
    reason = []
    if combined_sot >= 6 or combined_shots >= 24 or (h_power > 20 and a_power > 12) :
        over_conf = 0.8
        reason.append("Alta atividade ofensiva (chutes / chutes a gol).")
    elif combined_sot >= 4 or combined_shots >= 16:
        over_conf = 0.55
        reason.append("Alguma atividade ofensiva que pode resultar em gols.")
    else:
        over_conf = 0.2
        reason.append("Pouca atividade ofensiva.")
    preds.append({"market":"over_2_5","recommendation": "OVER 2.5" if over_conf>=0.5 else "UNDER 2.5","confidence": round(over_conf,2),"reason":" ".join(reason)})

    # Both Teams To Score (BTTS)
    btts_conf = 0.0
    if h_sot >= 2 and a_sot >= 2:
        btts_conf = 0.8
    elif h_sot >=1 and a_sot>=1:
        btts_conf = 0.6
    else:
        btts_conf = 0.25
    preds.append({"market":"btts","recommendation":"SIM" if btts_conf>=0.5 else "NAO","confidence":round(btts_conf,2),"reason":"Baseado em chutes/atividade de ambos os times."})

    # Corners (over 8.5)
    corners_conf = 0.0
    if combined_corners >= 10:
        corners_conf = 0.8
    elif combined_corners >= 7:
        corners_conf = 0.55
    else:
        corners_conf = 0.2
    preds.append({"market":"corners_over_8_5","recommendation":"OVER 8.5" if corners_conf>=0.5 else "UNDER 8.5","confidence":round(corners_conf,2),"reason":"Baseado no número de escanteios registrados."})

    # Moneyline & Handicap - favorite detection
    ml_reco = "draw"
    ml_conf = 0.0
    if power_diff > 6:
        ml_reco = "home"
        ml_conf = min(0.95, 0.5 + power_diff/30)
    elif power_diff < -6:
        ml_reco = "away"
        ml_conf = min(0.95, 0.5 + (-power_diff)/30)
    else:
        ml_reco = "no_clear_favorite"
        ml_conf = 0.35
    preds.append({"market":"moneyline","recommendation":ml_reco,"confidence":round(ml_conf,2),"reason":"Comparação de atividade ofensiva e posse."})

    # Handicap simple (-0.5)
    handicap = None
    if abs(power_diff) >= 10:
        handicap = ("home_-0.5" if power_diff>0 else "away_-0.5")
        preds.append({"market":"handicap_0_5","recommendation":handicap,"confidence":round(min(0.95, 0.4 + abs(power_diff)/30),2),"reason":"Diferença forte na atividade ofensiva."})
    else:
        preds.append({"market":"handicap_0_5","recommendation":"no_strong_handicap","confidence":0.25,"reason":"Diferença não suficiente para handicap claro."})

    # Double Chance (safe play)
    dc_reco = None
    if ml_conf >= 0.7:
        # strong favorite -> 1X or X2 accordingly
        if ml_reco == "home":
            dc_reco = "1X"
        elif ml_reco == "away":
            dc_reco = "X2"
        else:
            dc_reco = "1X"
        preds.append({"market":"double_chance","recommendation":dc_reco,"confidence":round(ml_conf,2),"reason":"Proteção para favorito com alta confiança."})
    else:
        preds.append({"market":"double_chance","recommendation":"no_strong_recommendation","confidence":0.3,"reason":"Sem favorito claro."})

    # corner trend
    corner_trend = "neutral"
    if h_corners > a_corners and h_corners >=4:
        corner_trend = "home_more_corners"
    elif a_corners > h_corners and a_corners >=4:
        corner_trend = "away_more_corners"
    preds.append({"market":"corner_trend","recommendation":corner_trend,"confidence":0.4,"reason":"Baseado na distribuição de escanteios."})

    # assemble summary
    summary = {
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_power": round(h_power,2),
        "away_power": round(a_power,2),
        "power_diff": round(power_diff,2),
        "combined_shots": combined_shots,
        "combined_sot": combined_sot,
        "combined_corners": combined_corners
    }
    return preds, summary

@app.get("/analyze")
def analyze(game_id: int = Query(...), sport: str = Query("football", enum=["football","nba","nfl"])):
    # fetch fixture
    cfg = API_CONFIG[sport]
    # single fixture fetch
    if sport == "football":
        fixtures = api_fetch("football", {"id": game_id})
        if not fixtures:
            raise HTTPException(status_code=404, detail="Jogo não encontrado")
        fixture = fixtures[0]
        # stats
        stats_raw = fetch_football_statistics(game_id)
        # stats_raw structure: list per team with statistics -> build map
        # some plans return: [{team: {...}, statistics: [{type: "...", value: ...}, ...]}, ...]
        stats_map = {}
        try:
            for team_stats in stats_raw:
                team = team_stats.get("team", {}) or {}
                tid = team.get("id")
                stats_map[tid] = {}
                for s in team_stats.get("statistics", []) or []:
                    k = (s.get("type") or s.get("name") or "").strip()
                    v = s.get("value")
                    if isinstance(v, str) and "/" in v:
                        try:
                            v = int(v.split("/")[0])
                        except:
                            try: v = int(float(v))
                            except: v = 0
                    else:
                        try: v = int(v)
                        except:
                            try: v = int(float(v))
                            except: v = 0
                    stats_map[tid][k] = v
        except Exception as e:
            print("stats_map build error", e)

        preds, summary = heuristics_football(fixture, stats_map)
        return {"game_id": game_id, "sport": sport, "summary": summary, "predictions": preds, "raw_fixture": fixture, "raw_stats": stats_raw}

    else:
        # NBA / NFL: best-effort analysis using available fields
        fixtures = api_fetch(sport, {"id": game_id})
        if not fixtures:
            raise HTTPException(status_code=404, detail="Jogo não encontrado")
        fixture = fixtures[0]
        # Basic heuristics: use points/score or team offensive indicators if available
        # Try to access statistics endpoint if exists (not guaranteed)
        stats_raw = api_get_raw(API_CONFIG[sport], "statistics", {"game": game_id}) or []
        # Very simple recommendation fallback:
        home = fixture.get("teams", {}).get("home", {}) or {}
        away = fixture.get("teams", {}).get("away", {}) or {}
        # build simplified predictions
        preds = []
        # moneyline by score if live
        status = fixture.get("status", {})
        elapsed = status.get("elapsed")
        home_score = fixture.get("score", {}).get("home") if fixture.get("score") else None
        away_score = fixture.get("score", {}).get("away") if fixture.get("score") else None
        if elapsed is not None and home_score is not None and away_score is not None:
            # in-play simple suggestion
            if home_score > away_score:
                preds.append({"market":"moneyline","recommendation":"home","confidence":0.75,"reason":"Time da casa na frente no placar."})
            elif away_score > home_score:
                preds.append({"market":"moneyline","recommendation":"away","confidence":0.75,"reason":"Time visitante na frente no placar."})
            else:
                preds.append({"market":"moneyline","recommendation":"no_clear_favorite","confidence":0.35,"reason":"Empate no momento."})
        else:
            preds.append({"market":"moneyline","recommendation":"no_data","confidence":0.2,"reason":"Dados insuficientes para análise precisa."})

        return {"game_id": game_id, "sport": sport, "summary": {"home": home.get("name"), "away": away.get("name")}, "predictions": preds, "raw_fixture": fixture, "raw_stats": stats_raw}
