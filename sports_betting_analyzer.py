# sports_betting_analyzer_v5.py
"""
Tipster IA - sports_betting_analyzer (v5.0 FINAL)
-------------------------------------------------
- Endpoints: /countries, /leagues, /games, /analyze
- Busca fixtures (ao vivo + próximos dias) e normaliza
- Heurísticas expandidas (muitos mercados)
- Busca odds e extrai odds específicas das casas preferidas
  (Bet365, Betano, Superbet, Pinnacle)
- Sempre pega a melhor odd entre essas casas
- Cache simples em memória

Como usar:
- Defina a variável de ambiente API_SPORTS_KEY 
  (ou edite direto no código para dev)
- Rode com: uvicorn sports_betting_analyzer_v5:app --reload
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import requests
import os
import time
import traceback

# ---------------- Config ----------------
app = FastAPI(title="Tipster IA - API (v5.0 FINAL)")
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

API_SPORTS_KEY = os.environ.get("API_SPORTS_KEY", "7baa5e00c8ae57d0e6240f790c6840dd")
API_URL_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_SPORTS_KEY}

PREFERRED_BOOKMAKERS = ["bet365", "betano", "superbet", "pinnacle"]

CACHE_TTL = 120  # segundos
_cache: Dict[str, Dict[str, Any]] = {}

# ---------------- Cache helpers ----------------
def _cache_get(key: str):
    rec = _cache.get(key)
    if not rec:
        return None
    if time.time() - rec.get("ts", 0) > CACHE_TTL:
        _cache.pop(key, None)
        return None
    return rec.get("data")

def _cache_set(key: str, data):
    _cache[key] = {"ts": time.time(), "data": data}

# ---------------- API helper ----------------
def api_get_raw(path: str, params: dict = None) -> Optional[Dict[str, Any]]:
    url = f"{API_URL_BASE}/{path}"
    try:
        r = requests.get(url, headers=HEADERS, params=params or {}, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[api_get_raw] ERROR for {url} with params {params}: {e}")
        try:
            print("response_preview:", r.text[:400])
        except Exception:
            pass
        print(traceback.format_exc())
        return None

# ---------------- Fixtures ----------------
def normalize_game(raw: dict) -> dict:
    fixture = raw.get("fixture", {})
    league = raw.get("league", {}) or {}
    teams = raw.get("teams", {}) or {}
    status = fixture.get("status", {}) or {}
    return {
        "game_id": fixture.get("id"),
        "date": fixture.get("date"),
        "league": league,
        "teams": teams,
        "status": status,
        "type": ("live" if status.get("elapsed") else "scheduled"),
        "raw": raw
    }

def get_fixtures_for_dates(days_forward: int = 2) -> List[dict]:
    ck = f"all_fixtures_v3_{days_forward}"
    cached = _cache_get(ck)
    if cached:
        return cached

    dates = [(datetime.utcnow().date() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_forward + 1)]
    all_fixtures: List[dict] = []
    seen_ids = set()

    # Live
    live_data = api_get_raw("fixtures", params={"live": "all"})
    if live_data and live_data.get("response"):
        for fixture in live_data["response"]:
            fid = fixture.get("fixture", {}).get("id")
            if fid and fid not in seen_ids:
                all_fixtures.append(normalize_game(fixture))
                seen_ids.add(fid)

    # Próximas datas
    for date_str in dates:
        fixtures_data = api_get_raw("fixtures", params={"date": date_str})
        if fixtures_data and fixtures_data.get("response"):
            for fixture in fixtures_data["response"]:
                fid = fixture.get("fixture", {}).get("id")
                if fid and fid not in seen_ids:
                    all_fixtures.append(normalize_game(fixture))
                    seen_ids.add(fid)

    _cache_set(ck, all_fixtures)
    return all_fixtures

# ---------------- Endpoints listagem ----------------
@app.get("/countries")
def countries():
    games = get_fixtures_for_dates()
    countries_set = {g.get("league", {}).get("country") for g in games if g.get("league", {}).get("country")}
    return sorted([c for c in countries_set if c])

@app.get("/leagues")
def leagues(country: str = Query(...)):
    games = get_fixtures_for_dates()
    league_map = {g.get("league", {}).get("id"): g.get("league") for g in games if g.get("league", {}).get("country") == country}
    return list(league_map.values())

@app.get("/games")
def games(league: int = Query(None)):
    all_games = get_fixtures_for_dates()
    if league:
        return [g for g in all_games if g.get("league", {}).get("id") == int(league)]
    return all_games

# ---------------- Estatísticas ----------------
def fetch_football_statistics(fixture_id: int) -> Optional[Dict[str, Any]]:
    return api_get_raw("fixtures/statistics", params={"fixture": fixture_id})

def safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        try:
            return int(float(v))
        except Exception:
            return 0

def build_stats_map(stats_raw: Optional[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    if not stats_raw or "response" not in stats_raw:
        return out
    for item in stats_raw["response"]:
        team = item.get("team") or {}
        tid = team.get("id")
        if not tid:
            continue
        out[tid] = {}
        for s in item.get("statistics", []) or []:
            k = (s.get("type") or s.get("name") or "").strip()
            v = s.get("value")
            if isinstance(v, str) and "/" in v:
                try:
                    v = int(v.split("/")[0])
                except Exception:
                    v = safe_int(v)
            else:
                v = safe_int(v)
            out[tid][k] = v
    return out

# ---------------- Heurísticas ----------------
def heuristics_football(fixture_raw: dict, stats_map: Dict[int, Dict[str, Any]]) -> Tuple[List[dict], dict]:
    teams = fixture_raw.get("teams", {}) or {}
    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}

    home_id = home.get("id")
    away_id = away.get("id")
    stats_home = stats_map.get(home_id, {})
    stats_away = stats_map.get(away_id, {})

    predictions: List[dict] = []
    summary = {}

    def add_pred(market, rec, confidence):
        predictions.append({"market": market, "recommendation": rec, "confidence": confidence})

    shots_home = stats_home.get("Shots on Goal", 0)
    shots_away = stats_away.get("Shots on Goal", 0)
    corners_home = stats_home.get("Corner Kicks", 0)
    corners_away = stats_away.get("Corner Kicks", 0)
    attacks_home = stats_home.get("Attacks", 0)
    attacks_away = stats_away.get("Attacks", 0)
    dangerous_home = stats_home.get("Dangerous Attacks", 0)
    dangerous_away = stats_away.get("Dangerous Attacks", 0)
    possession_home = stats_home.get("Ball Possession", 50)
    possession_away = stats_away.get("Ball Possession", 50)

    # ---------------- MONEYLINE ----------------
    if shots_home + dangerous_home > shots_away + dangerous_away:
        add_pred("moneyline", "Vitória Casa", 0.7)
    elif shots_away + dangerous_away > shots_home + dangerous_home:
        add_pred("moneyline", "Vitória Visitante", 0.7)
    else:
        add_pred("moneyline", "Empate", 0.5)

    # ---------------- DOUBLE CHANCE ----------------
    if possession_home > 55:
        add_pred("double_chance", "Casa ou Empate", 0.75)
    elif possession_away > 55:
        add_pred("double_chance", "Fora ou Empate", 0.75)

    # ---------------- OVER/UNDER ----------------
    total_shots = shots_home + shots_away
    if total_shots >= 10 or (dangerous_home + dangerous_away) >= 20:
        add_pred("over_2_5", "OVER 2.5", 0.8)
    else:
        add_pred("over_2_5", "UNDER 2.5", 0.6)

    # ---------------- BTTS ----------------
    if shots_home >= 4 and shots_away >= 4:
        add_pred("btts", "Sim", 0.75)
    else:
        add_pred("btts", "Não", 0.6)

    # ---------------- ASIAN HANDICAP ----------------
    diff_shots = shots_home - shots_away
    if diff_shots >= 4:
        add_pred("asian_handicap_home", "Home -1", 0.7)
    elif diff_shots <= -4:
        add_pred("asian_handicap_away", "Away -1", 0.7)

    # ---------------- CORNERS ----------------
    total_corners = corners_home + corners_away
    if total_corners >= 9:
        add_pred("corners_ft_over", "Over 9.5", 0.75)
    else:
        add_pred("corners_ft_under", "Under 9.5", 0.65)

    if (corners_home + corners_away) >= 5:
        add_pred("corners_ht_over", "Over 4.5", 0.7)

    summary = {
        "shots_on_goal": {"home": shots_home, "away": shots_away},
        "corners": {"home": corners_home, "away": corners_away},
        "possession": {"home": possession_home, "away": possession_away},
        "dangerous_attacks": {"home": dangerous_home, "away": dangerous_away},
        "attacks": {"home": attacks_home, "away": attacks_away}
    }

    return predictions, summary

# ---------------- Odds helpers ----------------
def build_book_odds_map(bookmaker: dict) -> Dict[Tuple[str, str], float]:
    out: Dict[Tuple[str, str], float] = {}
    if not bookmaker:
        return out
    for bet in bookmaker.get("bets", []) or []:
        bet_name = bet.get("name") or ""
        for val in bet.get("values", []) or []:
            v = val.get("value")
            odd = val.get("odd")
            try:
                odd_f = float(odd)
            except Exception:
                try:
                    odd_f = float(str(odd).replace(',', '.'))
                except Exception:
                    odd_f = 0.0
            out[(bet_name.strip(), (v or "").strip())] = odd_f
    return out

def enhance_predictions_with_preferred_odds(predictions: List[Dict], odds_raw: Optional[Dict]) -> List[Dict]:
    if not odds_raw or not odds_raw.get("response"):
        return predictions

    bookmakers = odds_raw["response"][0].get("bookmakers", []) or []
    preferred_books = [b for b in bookmakers if (b.get("name") or "").lower() in PREFERRED_BOOKMAKERS]
    if not preferred_books:
        return predictions

    market_map = {
        "moneyline": {
            "names": ["Match Winner", "Match Result", "1X2"],
            "convert": lambda rec: "Home" if rec == "Vitória Casa" else ("Away" if rec == "Vitória Visitante" else None)
        },
        "double_chance": {
            "names": ["Double Chance"],
            "convert": lambda rec: {"Casa ou Empate": "Home/Draw", "Fora ou Empate": "Away/Draw"}.get(rec)
        },
        "over_2_5": {
            "names": ["Goals Over/Under", "Over/Under", "Total Goals"],
            "convert": lambda rec: "Over 2.5" if "OVER" in rec.upper() else "Under 2.5"
        },
        "btts": {
            "names": ["Both Teams To Score", "Both Teams To Score?", "Both Teams to Score"],
            "convert": lambda rec: "Yes" if rec.upper() == "SIM" else "No"
        },
        "asian_handicap_home": {
            "names": ["Asian Handicap", "Asian Handicap Match"],
            "convert": lambda rec: (rec.split()[-1] if isinstance(rec, str) and "-" in rec.split()[-1] else None)
        },
        "asian_handicap_away": {
            "names": ["Asian Handicap", "Asian Handicap Match"],
            "convert": lambda rec: (rec.split()[-1] if isinstance(rec, str) and "-" in rec.split()[-1] else None)
        },
        "corners_ft_over": {
            "names": ["Corners Over/Under", "Corners Total"],
            "convert": lambda rec: "Over 9.5" if "OVER" in rec.upper() else "Under 9.5"
        },
        "corners_ft_under": {
            "names": ["Corners Over/Under", "Corners Total"],
            "convert": lambda rec: "Under 9.5" if "UNDER" in rec.upper() else "Over 9.5"
        },
        "corners_ht_over": {
            "names": ["1st Half Corners", "Corners Over/Under - 1st Half"],
            "convert": lambda rec: "Over 4.5" if "OVER" in rec.upper() else None
        }
    }

    enhanced = []
    for pred in predictions:
        market = pred.get("market")
        rec = pred.get("recommendation")
        mapping = market_map.get(market)
        if not mapping:
            enhanced.append(pred)
            continue

        api_val = None
        try:
            api_val = mapping["convert"](rec)
        except Exception:
            api_val = None
        if not api_val:
            enhanced.append(pred)
            continue

        best_odd = 0.0
        best_book = None
        best_market_name = None

        for book in preferred_books:
            book_map = build_book_odds_map(book)
            for name in mapping.get("names", []):
                key = (name, api_val)
                odd = book_map.get(key, 0.0)
                if odd and odd > best_odd:
                    best_odd = odd
                    best_book = book.get("name")
                    best_market_name = name

        if best_odd > 0:
            pred = dict(pred)
            pred["best_odd"] = best_odd
            pred["bookmaker"] = best_book
            pred["market_name_found"] = best_market_name
        enhanced.append(pred)

    return enhanced

# ---------------- Analyze endpoint ----------------
@app.get("/analyze")
def analyze(game_id: int = Query(...)):
    fixture_data = api_get_raw("fixtures", params={"id": game_id})
    if not fixture_data or not fixture_data.get("response"):
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    fixture = fixture_data["response"][0]

    stats_raw = fetch_football_statistics(game_id)
    stats_map = build_stats_map(stats_raw)

    preds, summary = heuristics_football(fixture, stats_map)

    odds_raw = api_get_raw("odds", params={"fixture": game_id})
    enhanced = enhance_predictions_with_preferred_odds(preds, odds_raw)

    return {
        "game_id": game_id,
        "summary": summary,
        "predictions": enhanced,
        "raw_fixture": fixture,
        "raw_stats": stats_raw,
        "raw_odds": odds_raw
    }

# ---------------- Health check ----------------
@app.get("/health")
def health():
    return {"status": "ok", "time_utc": datetime.utcnow().isoformat()}
