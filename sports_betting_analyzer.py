# sports_betting_analyzer_v5.py
"""
Tipster IA - sports_betting_analyzer (v5.0)
- Endpoints: /countries, /leagues, /games, /analyze
- Busca fixtures (ao vivo + próximos dias) e normaliza
- Heurísticas expandidas (muitos mercados)
- Busca odds e extrai odds específicas da Bet365 (quando disponível)
- Cache simples em memória

Como usar:
- Defina a variável de ambiente API_SPORTS_KEY (opcional: código contém uma chave padrão de desenvolvimento)
- Rode com: uvicorn sports_betting_analyzer_v5:app --reload

Observações:
- A lógica de mapping de mercados tenta acomodar nomes típicos retornados pela API-Football, mas, dependendo do fornecedor
  de odds e da versão da API, os nomes podem variar. Ajuste `market_map` se notar diferenças no payload real.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
import requests
import os
import time
import traceback

app = FastAPI(title="Tipster IA - API (v5.0)")
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

# --- Cache (in-memory, simples) ---
CACHE_TTL = 120  # segundos
_cache: Dict[str, Dict[str, Any]] = {}


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


# --- HTTP helper ---
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


# --- Normalização de fixtures / listagem ---

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


# --- Endpoints listagem ---
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


# --- Estatísticas e heurísticas ---

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


def heuristics_football(fixture_raw: dict, stats_map: Dict[int, Dict[str, Any]]) -> Tuple[List[dict], dict]:
    home = fixture_raw.get("teams", {}).get("home", {})
    away = fixture_raw.get("teams", {}).get("away", {})
    home_id = home.get("id")
    away_id = away.get("id")
    home_stats = stats_map.get(home_id, {})
    away_stats = stats_map.get(away_id, {})

    def g(d, *keys):
        for k in keys:
            if k in d:
                return d[k]
        return 0

    # tentamos vários nomes comuns retornados pela API
    h_shots = g(home_stats, "Total Shots", "Shots")
    h_sot = g(home_stats, "Shots on Goal", "Shots on Target")
    h_corners = g(home_stats, "Corners", "Corner Kicks")
    h_fouls = g(home_stats, "Fouls")
    h_pos = g(home_stats, "Ball Possession", "Possession")

    a_shots = g(away_stats, "Total Shots", "Shots")
    a_sot = g(away_stats, "Shots on Goal", "Shots on Target")
    a_corners = g(away_stats, "Corners", "Corner Kicks")
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

    # Goals atuais se presentes (para jogos ao vivo)
    goals = fixture_raw.get("goals", {}) or {}
    h_goals = safe_int(goals.get("home"))
    a_goals = safe_int(goals.get("away"))
    total_goals = h_goals + a_goals

    preds = []

    # Over/Under 2.5
    if combined_sot >= 6 or combined_shots >= 24:
        preds.append({"market": "over_2_5", "recommendation": "OVER 2.5", "confidence": 0.9, "reason": f"{combined_sot} SOT, {combined_shots} chutes totais."})
    elif combined_sot >= 4 or combined_shots >= 16:
        preds.append({"market": "over_2_5", "recommendation": "OVER 2.5", "confidence": 0.6, "reason": f"{combined_sot} SOT, {combined_shots} chutes totais."})
    else:
        preds.append({"market": "over_2_5", "recommendation": "UNDER 2.5", "confidence": 0.25, "reason": f"Apenas {combined_sot} SOT, {combined_shots} chutes totais."})

    # BTTS
    if h_sot >= 2 and a_sot >= 2:
        preds.append({"market": "btts", "recommendation": "SIM", "confidence": 0.9, "reason": f"Casa {h_sot} SOT, Visitante {a_sot} SOT."})
    elif h_sot >= 1 and a_sot >= 1:
        preds.append({"market": "btts", "recommendation": "SIM", "confidence": 0.6, "reason": f"Casa {h_sot} SOT, Visitante {a_sot} SOT."})
    else:
        preds.append({"market": "btts", "recommendation": "NAO", "confidence": 0.3, "reason": f"Um dos times (ou ambos) com menos de 1 SOT."})

    # Corners FT
    if combined_corners >= 10:
        preds.append({"market": "corners_ft_over", "recommendation": "OVER 9.5", "confidence": 0.85, "reason": f"Total de {combined_corners} escanteios."})
    elif combined_corners >= 7:
        preds.append({"market": "corners_ft_over", "recommendation": "OVER 9.5", "confidence": 0.6, "reason": f"Total de {combined_corners} escanteios."})
    else:
        preds.append({"market": "corners_ft_under", "recommendation": "UNDER 9.5", "confidence": 0.25, "reason": f"Total de {combined_corners} escanteios."})

    # Corners HT (se tivermos dados de HT nos statistics)
    h_corners_ht = g(home_stats, "Corners 1st Half", "Corners Half Time", "Corners 1H")
    a_corners_ht = g(away_stats, "Corners 1st Half", "Corners Half Time", "Corners 1H")
    combined_corners_ht = safe_int(h_corners_ht) + safe_int(a_corners_ht)
    if combined_corners_ht > 4:
        preds.append({"market": "corners_ht_over", "recommendation": "OVER 4.5", "confidence": 0.7, "reason": f"{combined_corners_ht} escanteios no 1º tempo."})

    # Moneyline (com base no power)
    if power_diff > 6:
        preds.append({"market": "moneyline", "recommendation": "Vitória Casa", "confidence": min(0.95, 0.5 + power_diff/30)})
    elif power_diff < -6:
        preds.append({"market": "moneyline", "recommendation": "Vitória Visitante", "confidence": min(0.95, 0.5 + (-power_diff)/30)})
    else:
        preds.append({"market": "moneyline", "recommendation": "Sem favorito definido", "confidence": 0.35})

    # Double Chance (heurística simples baseada no power)
    if power_diff >= 2:
        preds.append({"market": "double_chance", "recommendation": "Casa ou Empate", "confidence": 0.6})
    elif power_diff <= -2:
        preds.append({"market": "double_chance", "recommendation": "Fora ou Empate", "confidence": 0.6})

    # Asian handicap (heurística simplificada)
    if power_diff >= 4:
        preds.append({"market": "asian_handicap_home", "recommendation": f"{home.get('name')} -1.5", "confidence": 0.6})
    elif power_diff <= -4:
        preds.append({"market": "asian_handicap_away", "recommendation": f"{away.get('name')} -1.5", "confidence": 0.6})

    summary = {
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_power": round(h_power, 2),
        "away_power": round(a_power, 2),
        "combined_shots": combined_shots,
        "combined_sot": combined_sot,
        "combined_corners": combined_corners,
        "total_goals": total_goals,
    }

    return preds, summary


# --- Odds: foco Bet365 ---

def find_bet365(bookmakers: List[dict]) -> Optional[dict]:
    if not bookmakers:
        return None
    # tentativa por id (comum: 8) ou por nome contendo 'bet' (case-insensitive)
    for b in bookmakers:
        try:
            if b.get("id") == 8:
                return b
        except Exception:
            pass
    for b in bookmakers:
        name = (b.get("name") or "").lower()
        if "bet" in name:
            return b
    return None


def build_book_odds_map(bookmaker: dict) -> Dict[Tuple[str, str], float]:
    """Constroi um dicionario {(bet_name, value): odd} para busca rápida."""
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


def enhance_predictions_with_bet365_odds(predictions: List[Dict], odds_raw: Optional[Dict], fixture_raw: dict) -> List[Dict]:
    if not odds_raw or not odds_raw.get("response"):
        return predictions

    try:
        bookmakers = odds_raw["response"][0].get("bookmakers", [])
    except Exception:
        bookmakers = []

    bet365 = find_bet365(bookmakers)
    if not bet365:
        return predictions

    book_map = build_book_odds_map(bet365)

    # Mapeamento de mercados: (nosso_market) -> lista de possíveis nomes na API + função de conversão da recommendation -> api_value
    market_map = {
        "moneyline": {
            "names": ["Match Winner", "Match Result", "1X2"],
            "convert": lambda rec: "Home" if rec == "Vitória Casa" else ("Away" if rec == "Vitória Visitante" else None)
        },
        "double_chance": {
            "names": ["Double Chance"],
            "convert": lambda rec: {
                "Casa ou Empate": "Home/Draw",
                "Fora ou Empate": "Away/Draw"
            }.get(rec)
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
            # espera recomendação como "TeamName -1.5" -> extrair "-1.5"
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

    # Percorre preds e tenta anexar melhor odd da Bet365
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

        # procura em todas as possibilidades de nomes de mercado
        best_odd = 0.0
        best_name = None
        for name in mapping.get("names", []):
            key = (name, api_val)
            odd = book_map.get(key, 0.0)
            if odd and odd > best_odd:
                best_odd = odd
                best_name = name

        if best_odd > 0:
            pred = dict(pred)  # copia
            pred["best_odd"] = best_odd
            pred["bookmaker"] = bet365.get("name") or "Bet365"
            pred["market_name_found"] = best_name
        enhanced.append(pred)

    return enhanced


# --- Endpoint analyze ---
@app.get("/analyze")
def analyze(game_id: int = Query(...)):
    # fixtures
    fixture_data = api_get_raw("fixtures", params={"id": game_id})
    if not fixture_data or not fixture_data.get("response"):
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    fixture = fixture_data["response"][0]

    # stats
    stats_raw = fetch_football_statistics(game_id)
    stats_map = build_stats_map(stats_raw)

    # heuristics
    preds, summary = heuristics_football(fixture, stats_map)

    # odds
    odds_raw = api_get_raw("odds", params={"fixture": game_id})
    enhanced = enhance_predictions_with_bet365_odds(preds, odds_raw, fixture)

    return {
        "game_id": game_id,
        "summary": summary,
        "predictions": enhanced,
        "raw_fixture": fixture,
        "raw_stats": stats_raw,
        "raw_odds": odds_raw
    }


# --- Health check simple ---
@app.get("/health")
def health():
    return {"status": "ok", "time_utc": datetime.utcnow().isoformat()}
