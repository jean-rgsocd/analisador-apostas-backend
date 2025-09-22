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

def api_get(params: dict):
    cfg = API_CONFIG["football"]
    headers = {
        "x-apisports-key": API_SPORTS_KEY,
        # Se usar RapidAPI, descomente:
        # "x-rapidapi-key": API_SPORTS_KEY,
        # "x-rapidapi-host": cfg["host"],
    }
    url = cfg["url"]
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=25)
        r.raise_for_status()
        j = r.json()
        resp = j.get("response", [])
        if not resp:
            print(f"[api_get] football {url} params={params} -> empty response, status={r.status_code}, body_preview={str(j)[:300]}")
        return resp
    except Exception as e:
        print(f"[api_get] football {url} {params} -> {e}")
        print(traceback.format_exc())
        return []

def api_get_raw(path: str, params: dict=None):
    cfg = API_CONFIG["football"]
    headers = {"x-apisports-key": API_SPORTS_KEY}
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

def normalize_game(raw: dict) -> dict:
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
    live = api_get({"live":"all"})
    for r in live:
        g = normalize_game(r)
        if is_future_or_live(g):
            results.append(g)
    # próximos 2 dias (hoje + 2)
    for d in get_dates(2):
        data = api_get({"date": d})
        for r in data:
            g = normalize_game(r)
            if is_future_or_live(g):
                results.append(g)
    results = sorted(results, key=lambda x: (0 if x.get("status", {}).get("elapsed") else 1, x.get("date") or ""))
    _cache_set(ck, results)
    return results

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
def games(league: int = Query(None)):
    all_games = futebol_all()
    if league:
        filtered = [g for g in all_games if (g.get("league") or {}).get("id") == int(league)]
    else:
        filtered = all_games
    return filtered

# ---- ANALYZE ----
def fetch_football_statistics(fixture_id: int):
    return api_get_raw("fixtures/statistics", params={"fixture": fixture_id})

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
    # (mesmo código de antes, sem mudanças)
    ...
    return preds, summary

@app.get("/analyze")
def analyze(game_id: int = Query(...)):
    fixtures = api_get({"id": game_id})
    if not fixtures:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    fixture = fixtures[0]
    stats_raw = fetch_football_statistics(game_id) or {}
    stats_map = build_stats_map(stats_raw or {})
    preds, summary = heuristics_football(fixture, stats_map)
    return {
        "game_id": game_id,
        "summary": summary,
        "predictions": preds,
        "raw_fixture": fixture,
        "raw_stats": stats_raw
    }
