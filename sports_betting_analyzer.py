# sports_betting_analyzer.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import requests, os, time, traceback

app = FastAPI(title="Tipster IA - API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://jean-psocd.github.io",  # GitHub Pages
        "http://localhost:8000"          # opcional para testes locais
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    headers = {"x-apisports-key": API_SPORTS_KEY}
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
    live = api_get({"live": "all"})
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
    try:
        return int(v)
    except:
        try:
            return int(float(v))
        except:
            return 0

def build_stats_map(stats_raw):
    out = {}
    if not stats_raw:
        return out
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
                    try:
                        v = int(v.split("/")[0])
                    except:
                        v = safe_int(v)
                else:
                    v = safe_int(v)
                out[tid][k] = v
    return out

def heuristics_football(fixture_raw, stats_map):
    home = fixture_raw.get("teams", {}).get("home", {}) or {}
    away = fixture_raw.get("teams", {}).get("away", {}) or {}
    home_id = home.get("id")
    away_id = away.get("id")
    home_stats = stats_map.get(home_id, {}) or {}
    away_stats = stats_map.get(away_id, {}) or {}

    def g(d, *keys):
        for k in keys:
            if k in d:
                return d[k]
        return 0

    h_shots = g(home_stats, "Total Shots", "Shots")
    h_sot = g(home_stats, "Shots on Goal", "Shots on Target")
    h_corners = g(home_stats, "Corners")
    h_fouls = g(home_stats, "Fouls")
    h_pos = g(home_stats, "Ball Possession", "Possession")
    a_shots = g(away_stats, "Total Shots", "Shots")
    a_sot = g(away_stats, "Shots on Goal", "Shots on Target")
    a_corners = g(away_stats, "Corners")
    a_fouls = g(away_stats, "Fouls")
    a_pos = g(away_stats, "Ball Possession", "Possession")

    def norm_pos(x):
        if isinstance(x, str) and "%" in x:
            try:
                return int(x.replace("%", "").strip())
            except:
                return 0
        try:
            return int(x)
        except:
            return 0

    h_pos = norm_pos(h_pos)
    a_pos = norm_pos(a_pos)

    h_power = h_sot * 1.6 + h_shots * 0.6 + h_corners * 0.35 + (h_pos * 0.2) - (h_fouls * 0.1)
    a_power = a_sot * 1.6 + a_shots * 0.6 + a_corners * 0.35 + (a_pos * 0.2) - (a_fouls * 0.1)
    power_diff = h_power - a_power

    combined_sot = h_sot + a_sot
    combined_shots = h_shots + a_shots
    combined_corners = h_corners + a_corners

    preds = []

    # Over/Under 2.5
    if combined_sot >= 6 or combined_shots >= 24:
        preds.append({"market": "over_2_5", "recommendation": "OVER 2.5", "confidence": 0.9})
    elif combined_sot >= 4 or combined_shots >= 16:
        preds.append({"market": "over_2_5", "recommendation": "OVER 2.5", "confidence": 0.6})
    else:
        preds.append({"market": "over_2_5", "recommendation": "UNDER 2.5", "confidence": 0.25})

    # BTTS
    if h_sot >= 2 and a_sot >= 2:
        preds.append({"market": "btts", "recommendation": "SIM", "confidence": 0.9})
    elif h_sot >= 1 and a_sot >= 1:
        preds.append({"market": "btts", "recommendation": "SIM", "confidence": 0.6})
    else:
        preds.append({"market": "btts", "recommendation": "NAO", "confidence": 0.3})

    # Corners
    if combined_corners >= 10:
        preds.append({"market": "corners_over_8_5", "recommendation": "OVER 8.5", "confidence": 0.85})
    elif combined_corners >= 7:
        preds.append({"market": "corners_over_8_5", "recommendation": "OVER 8.5", "confidence": 0.6})
    else:
        preds.append({"market": "corners_over_8_5", "recommendation": "UNDER 8.5", "confidence": 0.25})

    # Moneyline
    if power_diff > 6:
        preds.append({"market": "moneyline", "recommendation": "Vitória Casa", "confidence": min(0.95, 0.5 + power_diff/30)})
    elif power_diff < -6:
        preds.append({"market": "moneyline", "recommendation": "Vitória Visitante", "confidence": min(0.95, 0.5 + (-power_diff)/30)})
    else:
        preds.append({"market": "moneyline", "recommendation": "Sem favorito definido", "confidence": 0.35})

    summary = {
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_power": round(h_power, 2),
        "away_power": round(a_power, 2),
        "combined_shots": combined_shots,
        "combined_sot": combined_sot,
        "combined_corners": combined_corners
    }
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
