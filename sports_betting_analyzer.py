# sports_betting_analyzer.py
"""
Sports Betting Analyzer - Unificado
- Base, dataclasses, utils
- SPORT_INDICATORS (perfil de especialista por esporte)
- Summarize séries
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from statistics import mean, stdev
from datetime import datetime
import math
import json

# -----------------------
# Utils
# -----------------------
def safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    try:
        return mean(values)
    except Exception:
        return None

def safe_stdev(values: List[float]) -> Optional[float]:
    if not values or len(values) < 2:
        return None
    try:
        return stdev(values)
    except Exception:
        return None

def clamp(n: float, minv: float, maxv: float) -> float:
    try:
        return max(minv, min(n, maxv))
    except Exception:
        return minv

def now_ts() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _is_number_str(s: Any) -> bool:
    try:
        if isinstance(s, str):
            ss = s.replace(",", ".")
            float(ss)
            return True
        return False
    except Exception:
        return False

def _pick_label_safe(label: str) -> str:
    return label.strip().lower().replace(" ", "_")

# -----------------------
# Dataclasses
# -----------------------
@dataclass
class SeriesSummary:
    results: Dict[str, int] = field(default_factory=dict)
    avg_scores_for: Optional[float] = None
    avg_scores_against: Optional[float] = None
    additional: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PreGameSummary:
    home_lastN: SeriesSummary
    away_lastN: SeriesSummary
    head2head_lastN: SeriesSummary
    advanced: Dict[str, Any] = field(default_factory=dict)
    market_odds: Dict[str, float] = field(default_factory=dict)

@dataclass
class LiveSignal:
    trigger: str
    action: str
    note: Optional[str] = None

@dataclass
class Pick:
    pick: str
    confidence: str
    rationale: str

@dataclass
class TipsterOutput:
    sport: str
    match_id: str
    pre_game_summary: PreGameSummary
    live_signals: List[LiveSignal]
    picks: List[Pick]
    confidence_overall: str
    updated_at: str

    def to_json(self) -> str:
        """Serializa para JSON"""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

# -----------------------
# SPORT_INDICATORS (perfil do tipster por esporte)
# -----------------------
SPORT_INDICATORS = {
    "Football": {
        "required_series": ["goals_for", "goals_against", "corners", "cards", "shots_on_target", "xg"],
        "live_triggers": [
            ("home_possession_15m>=65", "consider_add_pick", "dominance prolonged"),
            ("home_shots_on_target_10m>=2", "bet_over_first_half_goals", "shots first half"),
        ],
        "typical_picks": ["Moneyline", "Over_2.5_goals", "Over_first_half_goals", "Over_corners", "Over_cards", "BTTS"],
        "score_scale": 5.0
    },
    "Basketball": {
        "required_series": ["points_for", "points_against", "fg_pct", "three_pct", "rebounds", "turnovers", "pace"],
        "live_triggers": [
            ("team_fouls_quarter>=5", "bet_over_team_fouls", "accumulated fouls"),
            ("run_points>=10", "consider_handicap_shift", "point run")
        ],
        "typical_picks": ["Moneyline", "Over_total_points", "Spread", "Player_points_over"],
        "score_scale": 20.0
    },
    "NBA": {
        "required_series": ["points_for", "points_against", "pace", "fg_pct"],
        "live_triggers": [
            ("team_fouls_quarter>=5", "bet_over_team_fouls", "accumulated fouls"),
        ],
        "typical_picks": ["Moneyline", "Over_total_points", "Spread"],
        "score_scale": 20.0
    },
    "NFL": {
        "required_series": ["yards_for", "yards_against", "turnovers", "redzone_eff"],
        "live_triggers": [
            ("third_down_failures>=3", "consider_pbp_prop", "3rd down failures"),
        ],
        "typical_picks": ["Moneyline", "Spread", "Over_total_points", "Prop_QB_yards"],
        "score_scale": 40.0
    },
    "Baseball": {
        "required_series": ["runs_for", "runs_against", "starter_era", "starter_whip", "ops_lineup"],
        "live_triggers": [
            ("starter_allowed_runs>3", "consider_bullpen_runline", "starter in trouble"),
        ],
        "typical_picks": ["Moneyline", "Over_total_runs", "Run_line", "Player_hits_prop"],
        "score_scale": 10.0
    },
    "Formula1": {
        "required_series": ["qualifying_pos", "race_finish", "lap_times", "pit_stops"],
        "live_triggers": [
            ("safety_car==1", "delay_aggressive_bets", "safety car active"),
        ],
        "typical_picks": ["Winner", "Podium", "Fastest_lap", "Top6"],
        "score_scale": 5.0
    },
    "Handball": {
        "required_series": ["goals_for", "goals_against", "shot_efficiency", "goalkeeper_save_pct"],
        "live_triggers": [
            ("man_up_sequence==1", "bet_over_goals", "numerical superiority"),
        ],
        "typical_picks": ["Moneyline", "Over_goals", "Handicap"],
        "score_scale": 5.0
    },
    "Hockey": {
        "required_series": ["goals_for", "goals_against", "shots_on_goal", "save_pct"],
        "live_triggers": [
            ("sog_20min_high>=15", "bet_over_period_goals", "early shot volume")
        ],
        "typical_picks": ["Moneyline", "Over_goals", "Puck_line", "PP_chances"],
        "score_scale": 5.0
    },
    "MMA": {
        "required_series": ["stoppage_rate", "strikes_per_min", "td_accuracy", "control_time"],
        "live_triggers": [
            ("damage_accumulated>=1", "consider_stop_prop", "strikes dominance")
        ],
        "typical_picks": ["Winner_method", "Over_rounds", "Fight_will_finish"],
        "score_scale": 5.0
    },
    "Rugby": {
        "required_series": ["points_for", "points_against", "tries", "penalties"],
        "live_triggers": [
            ("sin_bin_event==1", "bet_temp_handicap", "sin bin affects momentum")
        ],
        "typical_picks": ["Moneyline", "Handicap", "Over_points"],
        "score_scale": 10.0
    },
    "Volleyball": {
        "required_series": ["sets_for", "sets_against", "attack_pct", "blocks", "aces"],
        "live_triggers": [
            ("serve_run>=3", "bet_set_points_over", "serve streak")
        ],
        "typical_picks": ["Match_winner", "Set_handicap", "Over_points_set"],
        "score_scale": 5.0
    }
}

# -----------------------
# Classe principal
# -----------------------
class SportsTipster:
    def __init__(self, sport: str, default_N: int = 5):
        self.sport = sport if sport in SPORT_INDICATORS else sport.title()
        self.N = default_N
        self.profile = SPORT_INDICATORS.get(
            self.sport,
            {"required_series": [], "live_triggers": [], "typical_picks": ["Moneyline"], "score_scale": 5.0}
        )

    def summarize_series(self, lastN_home: Dict[str, List[float]],
                         lastN_away: Dict[str, List[float]],
                         hh_lastN: Dict[str, List[float]]) -> PreGameSummary:
        """Recebe dicionários de séries e retorna PreGameSummary"""
        def build_summary(series_dict: Dict[str, Any]) -> SeriesSummary:
            results = series_dict.get("results", {})
            avg_f = safe_mean(series_dict.get("goals_for", []))
            avg_a = safe_mean(series_dict.get("goals_against", []))
            additional = {}
            for k, v in series_dict.items():
                if k in ("goals_for", "goals_against", "results"):
                    continue
                if isinstance(v, list) and v:
                    numeric = [float(x) for x in v if isinstance(x, (int, float)) or (isinstance(x, str) and _is_number_str(x))]
                    if numeric:
                        additional[f"avg_{k}"] = safe_mean(numeric)
            return SeriesSummary(results=results, avg_scores_for=avg_f, avg_scores_against=avg_a, additional=additional)

        home_summary = build_summary(lastN_home or {})
        away_summary = build_summary(lastN_away or {})
        h2h_summary = build_summary(hh_lastN or {})

        return PreGameSummary(home_lastN=home_summary, away_lastN=away_summary, head2head_lastN=h2h_summary, advanced={}, market_odds={})

# -----------------------
# PART 2/3
# - Parsing odds/H2H
# - Score normalization & confidence mapping
# - Live triggers evaluator (robusto)
# - Pre-game analysis and pick generation (sport-specific)
# -----------------------

from typing import Tuple

# -----------------------
# Parsing helpers
# -----------------------
def parse_market_odds(odds_dict: Dict[str, Any]) -> Dict[str, float]:
    """
    Convert market odds to floats. Accepts strings like '2.3' or '2,3'
    Ignores invalid or <1.01 values.
    """
    parsed: Dict[str, float] = {}
    if not odds_dict:
        return parsed
    for k, v in odds_dict.items():
        try:
            if isinstance(v, (int, float)):
                f = float(v)
            elif isinstance(v, str) and _is_number_str(v):
                f = float(v.replace(",", "."))
            else:
                continue
            if f and f >= 1.01:
                parsed[str(k)] = f
        except Exception:
            continue
    return parsed

def parse_h2h(h2h_raw: Optional[List[Dict[str, Any]]]) -> Dict[str, List[float]]:
    """
    Generic H2H parser for multiple sports.
    Tries common field names: home_goals, away_goals, goals_for, goals_against,
    points_home, points_away, runs_home, runs_away.
    Returns normalized dict with 'goals_for' and 'goals_against' when applicable.
    """
    out = {"goals_for": [], "goals_against": []}
    if not h2h_raw:
        return out
    for m in h2h_raw:
        # check many possible keys
        gf = None
        ga = None
        possible_home = ["home_goals", "goals_for", "points_home", "runs_home", "home_points", "home_score"]
        possible_away = ["away_goals", "goals_against", "points_away", "runs_away", "away_points", "away_score"]
        for key in possible_home:
            if key in m and m[key] is not None:
                gf = m[key]; break
        for key in possible_away:
            if key in m and m[key] is not None:
                ga = m[key]; break
        # fallback to generic keys
        if gf is None and "home" in m and isinstance(m["home"], dict) and "score" in m["home"]:
            gf = m["home"]["score"]
        if ga is None and "away" in m and isinstance(m["away"], dict) and "score" in m["away"]:
            ga = m["away"]["score"]
        # convert
        try:
            if _is_number_str(gf):
                out["goals_for"].append(float(str(gf).replace(",", ".")))
            if _is_number_str(ga):
                out["goals_against"].append(float(str(ga).replace(",", ".")))
        except Exception:
            continue
    return out

# -----------------------
# Score normalization & mapping
# -----------------------
def _normalize_score_raw(value: float, scale: float) -> float:
    """
    Normalize any raw score to [0..scale], with gentle squashing for outliers.
    """
    try:
        # simple logistic-style squash then scale
        x = float(value)
        # center and soft-limit
        s = scale
        # Use tanh to squash: tanh(x/s) in (-1,1), map to (0,s)
        norm = (math.tanh(x / (s * 1.5)) + 1) / 2.0  # in [0,1]
        return norm * s
    except Exception:
        return scale * 0.5

def _map_score_to_confidence_label(normalized_score: float, scale: float) -> str:
    """
    Map normalized score (0..scale) to label strings that are consistent across module.
    Returns one of: 'very_low','low','medium','high','very_high'
    """
    try:
        pct = (normalized_score / scale) * 100
        if pct >= 85:
            return "very_high"
        if pct >= 70:
            return "high"
        if pct >= 50:
            return "medium"
        if pct >= 30:
            return "low"
        return "very_low"
    except Exception:
        return "very_low"

# -----------------------
# Evaluate live triggers - robust (supports >, >=, <, <=, ==)
# -----------------------
def evaluate_live_triggers(sport: str, live_data: Dict[str, Any]) -> List[LiveSignal]:
    """
    Evaluate configured live_triggers for the sport against live_data dict.
    live_data keys should match the left-hand token names in triggers, e.g. 'home_possession_15m'
    """
    signals: List[LiveSignal] = []
    indicators = SPORT_INDICATORS.get(sport, {})
    triggers = indicators.get("live_triggers", []) or []
    for cond_tuple in triggers:
        try:
            cond = cond_tuple[0]
            action = cond_tuple[1] if len(cond_tuple) > 1 else "action"
            note = cond_tuple[2] if len(cond_tuple) > 2 else None

            # detect operator and split safely
            if ">=" in cond:
                left, right = cond.split(">=", 1)
                op = ">="
            elif "<=" in cond:
                left, right = cond.split("<=", 1)
                op = "<="
            elif ">" in cond:
                left, right = cond.split(">", 1)
                op = ">"
            elif "<" in cond:
                left, right = cond.split("<", 1)
                op = "<"
            elif "==" in cond:
                left, right = cond.split("==", 1)
                op = "=="
            else:
                # unsupported expression form
                continue

            key = left.strip()
            rhs_raw = right.strip()
            if not rhs_raw:
                continue

            # get live value
            if key not in live_data:
                # allow dot/underscore alternatives: try to normalize
                alt_key = key.replace(".", "_")
                if alt_key in live_data:
                    val = live_data[alt_key]
                else:
                    continue
            else:
                val = live_data[key]

            # normalize RHS numeric if possible
            try:
                rhs_val = float(rhs_raw)
            except Exception:
                # rhs may be boolean or string value
                rhs_val = rhs_raw

            # normalize val numeric
            if isinstance(val, str) and _is_number_str(val):
                val = float(val.replace(",", "."))
            # evaluate
            triggered = False
            if op == ">=" and isinstance(val, (int, float)) and isinstance(rhs_val, (int, float)):
                triggered = float(val) >= float(rhs_val)
            elif op == "<=" and isinstance(val, (int, float)) and isinstance(rhs_val, (int, float)):
                triggered = float(val) <= float(rhs_val)
            elif op == ">" and isinstance(val, (int, float)) and isinstance(rhs_val, (int, float)):
                triggered = float(val) > float(rhs_val)
            elif op == "<" and isinstance(val, (int, float)) and isinstance(rhs_val, (int, float)):
                triggered = float(val) < float(rhs_val)
            elif op == "==" :
                # equality for numbers or strings
                if isinstance(val, (int, float)) and isinstance(rhs_val, (int, float)):
                    triggered = float(val) == float(rhs_val)
                else:
                    triggered = str(val) == str(rhs_val)

            if triggered:
                signals.append(LiveSignal(trigger=cond, action=action, note=note))
        except Exception:
            continue
    return signals

# -----------------------
# Pre-game analysis - wrapper
# -----------------------
def analyze_pre_game(tipster: SportsTipster,
                     lastN_home: Dict[str, Any],
                     lastN_away: Dict[str, Any],
                     h2h_raw: Optional[List[Dict[str, Any]]] = None,
                     market_odds_raw: Optional[Dict[str, Any]] = None) -> PreGameSummary:
    """
    Build a PreGameSummary ready for pick generation:
      - normalizes h2h and odds
      - calls tipster.summarize_series
    """
    h2h_parsed = parse_h2h(h2h_raw) if h2h_raw else {}
    odds_parsed = parse_market_odds(market_odds_raw or {})
    pre = tipster.summarize_series(lastN_home or {}, lastN_away or {}, h2h_parsed or {})
    pre.market_odds = odds_parsed
    return pre

# -----------------------
# Generate picks - sport-specific heuristics
# -----------------------
def generate_picks(pre: PreGameSummary, sport: str, score_scale: float) -> List[Pick]:
    """
    Generate 1..3 picks based on pre-game summary and sport.
    Heuristics implemented for Football, Basketball, Baseball, MMA, F1, default fallback.
    """
    picks: List[Pick] = []
    profile = SPORT_INDICATORS.get(sport, {})
    scale = profile.get("score_scale", score_scale)

    # Football heuristics (over/btts/moneyline/corners/cards)
    if sport == "Football":
        hf = pre.home_lastN.avg_scores_for or 0.0
        ha = pre.home_lastN.avg_scores_against or 0.0
        af = pre.away_lastN.avg_scores_for or 0.0
        aa = pre.away_lastN.avg_scores_against or 0.0

        off_edge = hf - af
        def_edge = aa - ha
        raw_score = off_edge - def_edge
        normalized = _normalize_score_raw(raw_score, scale)
        confidence_label = _map_score_to_confidence_label(normalized, scale)

        # Moneyline preference
        if raw_score >= 0.7:
            picks.append(Pick("Moneyline_Home", confidence_label, f"off_edge={off_edge:.2f}, def_edge={def_edge:.2f}"))
        elif raw_score <= -0.7:
            picks.append(Pick("Moneyline_Away", confidence_label, f"off_edge={off_edge:.2f}, def_edge={def_edge:.2f}"))
        else:
            # goal market pick
            avg_total_goals = (hf + af) / 2.0 + (ha + aa) / 4.0
            if avg_total_goals >= 2.4:
                picks.append(Pick("Over_2.5_goals", "medium", f"avg_total_goals~{avg_total_goals:.2f}"))
            else:
                picks.append(Pick("Under_2.5_goals", "low", f"avg_total_goals~{avg_total_goals:.2f}"))

        # BTTS heuristic
        if (hf >= 1.0 and af >= 1.0) or ((pre.home_lastN.avg_scores_against or 0) >= 1.0 and (pre.away_lastN.avg_scores_against or 0) >= 1.0):
            picks.append(Pick("BTTS_Yes", "low", "both sides scoring probability"))

        # Corners/cards if data exists
        avg_corners = (pre.home_lastN.additional.get("avg_corners") or 0) + (pre.away_lastN.additional.get("avg_corners") or 0)
        if avg_corners >= 10:
            picks.append(Pick("Over_Total_Corners", "medium", f"avg_corners_comb={avg_corners:.1f}"))
        avg_cards = (pre.home_lastN.additional.get("avg_cards") or 0) + (pre.away_lastN.additional.get("avg_cards") or 0)
        if avg_cards >= 3:
            picks.append(Pick("Over_Total_Cards", "low", f"avg_cards_comb={avg_cards:.1f}"))

    # Basketball heuristics
    elif sport in ("Basketball", "NBA"):
        home_pts = pre.home_lastN.additional.get("avg_points_for") or pre.home_lastN.avg_scores_for or 0.0
        away_pts = pre.away_lastN.additional.get("avg_points_for") or pre.away_lastN.avg_scores_for or 0.0
        diff = home_pts - away_pts
        normalized = _normalize_score_raw(diff, scale)
        label = _map_score_to_confidence_label(normalized, scale)
        if diff >= 6:
            picks.append(Pick("Moneyline_Home", label, f"home_pts={home_pts:.1f}, away_pts={away_pts:.1f}"))
        elif diff <= -6:
            picks.append(Pick("Moneyline_Away", label, f"home_pts={home_pts:.1f}, away_pts={away_pts:.1f}"))
        else:
            picks.append(Pick("Over_total_points_market_watch", "low", "closely matched scoring averages"))

    # Baseball heuristics
    elif sport == "Baseball":
        h_runs = pre.home_lastN.additional.get("avg_runs_for") or pre.home_lastN.avg_scores_for or 0.0
        a_runs = pre.away_lastN.additional.get("avg_runs_for") or pre.away_lastN.avg_scores_for or 0.0
        diff = h_runs - a_runs
        normalized = _normalize_score_raw(diff, scale)
        label = _map_score_to_confidence_label(normalized, scale)
        if diff >= 1.0:
            picks.append(Pick("Moneyline_Home", label, f"avg_runs {h_runs:.2f} vs {a_runs:.2f}"))
        elif diff <= -1.0:
            picks.append(Pick("Moneyline_Away", label, f"avg_runs {a_runs:.2f} vs {h_runs:.2f}"))
        else:
            picks.append(Pick("Run_line_watch", "low", "small runs diff"))

    # MMA heuristics
    elif sport == "MMA":
        home_fin = pre.home_lastN.additional.get("avg_fin_rate") or 0.0
        away_fin = pre.away_lastN.additional.get("avg_fin_rate") or 0.0
        home_wins = pre.home_lastN.results.get("W", 0) if pre.home_lastN.results else 0
        away_wins = pre.away_lastN.results.get("W", 0) if pre.away_lastN.results else 0
        score = (home_wins - away_wins) + (home_fin - away_fin)
        normalized = _normalize_score_raw(score, scale)
        label = _map_score_to_confidence_label(normalized, scale)
        if score >= 2.0:
            picks.append(Pick("Winner_Home", label, "record/finish advantage"))
        elif score <= -2.0:
            picks.append(Pick("Winner_Away", label, "record/finish advantage"))
        else:
            picks.append(Pick("Method_prop_or_over_rounds", "low", "no clear advantage"))

    # Formula1 heuristics (very lightweight)
    elif sport == "Formula1":
        # if qualifying_pos present in advanced maybe choose winner
        pole = pre.advanced.get("pole_position") if pre.advanced else None
        if pole:
            picks.append(Pick("Winner_based_on_pole", "medium", f"pole={pole}"))
        else:
            picks.append(Pick("Top6_watch", "low", "no pole info"))

    # Default fallback: moneyline based on avg_scores_for
    else:
        hf = pre.home_lastN.avg_scores_for or 0.0
        af = pre.away_lastN.avg_scores_for or 0.0
        diff = hf - af
        normalized = _normalize_score_raw(diff, scale)
        label = _map_score_to_confidence_label(normalized, scale)
        if diff >= 1.5:
            picks.append(Pick("Moneyline_Home", label, f"home avg advantage {diff:.2f}"))
        elif diff <= -1.5:
            picks.append(Pick("Moneyline_Away", label, f"away avg advantage {abs(diff):.2f}"))
        else:
            picks.append(Pick("Moneyline_Tight", "low", "small difference"))

    # Deduplicate picks by normalized label and keep up to 3
    seen = set()
    unique: List[Pick] = []
    for p in picks:
        key = _pick_label_safe(p.pick)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
        if len(unique) >= 3:
            break

    # Guarantee at least one pick
    if not unique:
        unique.append(Pick("Moneyline_Fallback", "very_low", "fallback default"))

    return unique

# -----------------------
# Build tipster output (consolidation)
# -----------------------
def build_tipster_output(tipster: SportsTipster,
                         match_id: str,
                         lastN_home: Dict[str, Any],
                         lastN_away: Dict[str, Any],
                         h2h_raw: Optional[List[Dict[str, Any]]],
                         live_data: Dict[str, Any],
                         market_odds_raw: Optional[Dict[str, Any]]) -> TipsterOutput:
    """
    Consolidates PreGameSummary, LiveSignals and Picks into TipsterOutput
    """
    pre = analyze_pre_game(tipster, lastN_home, lastN_away, h2h_raw, market_odds_raw)
    live_signals = evaluate_live_triggers(tipster.sport, live_data or {})
    picks = generate_picks(pre, tipster.sport, tipster.profile.get("score_scale", 5.0))

    # compute an overall numeric score for confidence (simple avg of pick confidences mapped to numbers)
    label_to_num = {"very_low": 0.2, "low": 0.4, "medium": 0.6, "high": 0.8, "very_high": 1.0}
    nums = [label_to_num.get(p.confidence, 0.4) for p in picks]
    combined = sum(nums) / len(nums) if nums else 0.4
    normalized_score = _normalize_score_raw(combined * tipster.profile.get("score_scale", 5.0), tipster.profile.get("score_scale", 5.0))
    confidence_overall = _map_score_to_confidence_label(normalized_score, tipster.profile.get("score_scale", 5.0))

    out = TipsterOutput(
        sport=tipster.sport,
        match_id=match_id,
        pre_game_summary=pre,
        live_signals=live_signals,
        picks=picks,
        confidence_overall=confidence_overall,
        updated_at=now_ts()
    )
    return out

# -----------------------
# PART 3/3 (FINAL)
# - FastAPI integration
# - Serialization helpers, audit logs, examples and tests
# -----------------------

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
import uvicorn
import traceback

# -----------------------
# Logging / Audit
# -----------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sports_betting_analyzer")

def log_audit(match_id: str, tipster_output: TipsterOutput, stage: str = "pre_game"):
    picks_str = ", ".join([p.pick for p in tipster_output.picks])
    logger.info(f"[AUDIT:{stage}] match={match_id} sport={tipster_output.sport} picks=[{picks_str}] confidence={tipster_output.confidence_overall}")

# -----------------------
# Pydantic request models (lightweight)
# -----------------------
class SeriesPayload(BaseModel):
    results: Optional[dict] = None
    # dynamic keys allowed (goals_for, corners, etc.)
    # Pydantic will accept extra fields if not strictly validated here.

class AnalyzePreGameRequest(BaseModel):
    sport: str
    match_id: str
    home_lastN: dict
    away_lastN: dict
    h2h_raw: Optional[list] = None
    market_odds_raw: Optional[dict] = None
    # optional live_data preview
    live_data_preview: Optional[dict] = None

class AnalyzeLiveRequest(BaseModel):
    sport: str
    match_id: str
    live_data: dict
    # optionally include precomputed pre-game snapshot for speed
    pre_game_snapshot: Optional[dict] = None

# -----------------------
# FastAPI app
# -----------------------
app = FastAPI(title="Sports Betting Analyzer", version="1.0")

@app.get("/health")
async def health():
    return {"status": "ok", "time": now_ts()}

@app.post("/analyze/pre-game")
async def analyze_pre_game_endpoint(req: AnalyzePreGameRequest):
    try:
        sport = req.sport.title()
        tipster = SportsTipster(sport)
        # build pre-game summary
        pre = analyze_pre_game(tipster, req.home_lastN or {}, req.away_lastN or {}, req.h2h_raw or [], req.market_odds_raw or {})
        # generate picks
        picks = generate_picks(pre, tipster.sport, tipster.profile.get("score_scale", 5.0))
        # build tipster output (no live signals)
        out = TipsterOutput(
            sport=tipster.sport,
            match_id=req.match_id,
            pre_game_summary=pre,
            live_signals=[],
            picks=picks,
            confidence_overall="unknown",
            updated_at=now_ts()
        )
        # compute confidence properly
        # reuse build_tipster_output logic partially to avoid duplication
        built = build_tipster_output(tipster, req.match_id, req.home_lastN, req.away_lastN, req.h2h_raw or [], req.live_data_preview or {}, req.market_odds_raw or {})
        # audit log
        log_audit(req.match_id, built, stage="pre_game")
        return JSONResponse(content=asdict(built))
    except Exception as e:
        logger.error("Error in /analyze/pre-game: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/live")
async def analyze_live_endpoint(req: AnalyzeLiveRequest):
    try:
        sport = req.sport.title()
        tipster = SportsTipster(sport)
        # If pre_game_snapshot provided as dict, try to reconstruct TipsterOutput; otherwise we will call build_tipster_output with empty pre-game
        if req.pre_game_snapshot:
            try:
                # rehydrate minimal TipsterOutput from snapshot
                snapshot = req.pre_game_snapshot
                # Note: For production you might store serialized TipsterOutput in DB and retrieve here.
                pre = PreGameSummary(
                    home_lastN=SeriesSummary(**snapshot["pre_game_summary"]["home_lastN"]),
                    away_lastN=SeriesSummary(**snapshot["pre_game_summary"]["away_lastN"]),
                    head2head_lastN=SeriesSummary(**snapshot["pre_game_summary"]["head2head_lastN"]),
                    advanced=snapshot["pre_game_summary"].get("advanced", {}),
                    market_odds=snapshot["pre_game_summary"].get("market_odds", {})
                )
                tip_out = TipsterOutput(
                    sport=snapshot.get("sport", sport),
                    match_id=snapshot.get("match_id", req.match_id),
                    pre_game_summary=pre,
                    live_signals=[],
                    picks=[Pick(**p) for p in snapshot.get("picks", [])],
                    confidence_overall=snapshot.get("confidence_overall", "very_low"),
                    updated_at=snapshot.get("updated_at", now_ts())
                )
            except Exception:
                # fallback to fresh build
                tip_out = build_tipster_output(tipster, req.match_id, {}, {}, [], req.live_data, {})
        else:
            # Build on the fly (could be expensive)
            tip_out = build_tipster_output(tipster, req.match_id, {}, {}, [], req.live_data, {})

        # run live analysis: evaluate triggers and add in-play picks
        # reuse live triggers engine in Part2 - it returns LiveSignal list
        signals = evaluate_live_triggers(tipster.sport, req.live_data or {})
        # merge picks using same policy as live_analysis in earlier drafts:
        # We'll re-use generate_picks to get baseline picks then append in-play suggestions
        picks = tip_out.picks or []
        inplay_suggestions = []
        for s in signals:
            act = s.action.lower()
            if "first_half" in act or "firsthalf" in act:
                inplay_suggestions.append(Pick("Over_0.5_first_half", "medium", f"trigger:{s.trigger}"))
            elif "consider_add_pick" in act:
                inplay_suggestions.append(Pick("In-play_over_momentum", "low", f"trigger:{s.trigger}"))
            elif "handicap" in act or "spread" in act:
                inplay_suggestions.append(Pick("In-play_handicap_shift", "medium", f"trigger:{s.trigger}"))
            else:
                inplay_suggestions.append(Pick(f"In-play_suggestion_{_pick_label_safe(s.action)}", "low", f"trigger:{s.trigger}"))
        # merge, dedupe, prioritize by confidence label mapping
        merged = picks + inplay_suggestions
        # dedupe by pick string
        seen = set()
        unique_merged = []
        priority = {"very_high": 5, "high": 4, "medium": 3, "low": 2, "very_low": 1}
        for p in merged:
            key = _pick_label_safe(p.pick)
            if key in seen:
                continue
            seen.add(key)
            unique_merged.append(p)
        unique_merged.sort(key=lambda x: priority.get(x.confidence, 2), reverse=True)
        tip_out.picks = unique_merged[:3]
        tip_out.live_signals = signals
        # recompute confidence overall simply from picks
        label_map = {"very_high": 1.0, "high": 0.8, "medium": 0.6, "low": 0.4, "very_low": 0.2}
        nums = [label_map.get(p.confidence, 0.4) for p in tip_out.picks]
        avg = sum(nums) / len(nums) if nums else 0.4
        tip_out.confidence_overall = _map_score_to_confidence_label(_normalize_score_raw(avg * tipster.profile.get("score_scale", 5.0), tipster.profile.get("score_scale",5.0)), tipster.profile.get("score_scale",5.0))
        tip_out.updated_at = now_ts()

        # audit
        log_audit(req.match_id, tip_out, stage="live")
        return JSONResponse(content=asdict(tip_out))
    except Exception as e:
        logger.error("Error in /analyze/live: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------
# Examples (curl and python) - use these as templates
# -----------------------
EXAMPLE_CURL_PRE = """
curl -X POST "http://localhost:8000/analyze/pre-game" -H "Content-Type: application/json" -d '{
  "sport": "Football",
  "match_id": "teamA_vs_teamB_2025-09-01",
  "home_lastN": {"goals_for":[2,1,3,0,2],"goals_against":[1,1,0,2,2],"corners":[5,6,4,7,5],"cards":[1,2,1,0,1]},
  "away_lastN": {"goals_for":[1,0,2,1,0],"goals_against":[2,1,3,0,1],"corners":[3,4,2,5,4],"cards":[2,1,1,1,0]},
  "h2h_raw": [{"home_goals":2,"away_goals":1},{"home_goals":1,"away_goals":0}],
  "market_odds_raw": {"home":2.1,"draw":3.3,"away":3.5}
}'
"""

EXAMPLE_CURL_LIVE = """
curl -X POST "http://localhost:8000/analyze/live" -H "Content-Type: application/json" -d '{
  "sport": "Football",
  "match_id": "teamA_vs_teamB_2025-09-01",
  "live_data": {"home_possession_15m": 68.0, "home_shots_on_target_10m": 2}
}'
"""

PYTHON_EXAMPLE = """
from sports_betting_analyzer import SportsTipster, build_tipster_output
tipster = SportsTipster("Football")
out = build_tipster_output(tipster, "match_123", home_lastN, away_lastN, h2h_raw, {"home_possession_15m": 68}, {"home":2.1})
print(out.to_json())
"""

# -----------------------
# Sanity tests / pytest-style functions
# -----------------------
def _sanity_test_basic_flow():
    tipster = SportsTipster("Football")
    home_lastN = {"goals_for":[2,1,3,0,2],"goals_against":[1,1,0,2,2],"corners":[5,6,4,7,5],"cards":[1,2,1,0,1]}
    away_lastN = {"goals_for":[1,0,2,1,0],"goals_against":[2,1,3,0,1],"corners":[3,4,2,5,4],"cards":[2,1,1,1,0]}
    h2h_raw = [{"home_goals":2,"away_goals":1},{"home_goals":1,"away_goals":0}]
    market_odds = {"home":2.1,"draw":3.3,"away":3.5}
    out = build_tipster_output(tipster, "test_match_1", home_lastN, away_lastN, h2h_raw, {"home_possession_15m": 68}, market_odds)
    assert isinstance(out, TipsterOutput)
    assert out.sport == "Football"
    assert len(out.picks) >= 1 and len(out.picks) <= 3
    logger.info("Sanity test passed: picks=%s confidence=%s", [p.pick for p in out.picks], out.confidence_overall)

# -----------------------
# Run server helper
# -----------------------
def run_dev():
    """Helper to run uvicorn when executing this file directly"""
    uvicorn.run("sports_betting_analyzer:app", host="0.0.0.0", port=8000, reload=True)

# -----------------------
# If executed directly (for quick manual test)
# -----------------------
if __name__ == "__main__":
    logger.info("Starting quick sanity checks...")
    try:
        _sanity_test_basic_flow()
        logger.info("Sanity checks OK. You can run the server with run_dev() or 'python -m sports_betting_analyzer'")
    except AssertionError as e:
        logger.error("Sanity check failed: %s", e)
    except Exception as e:
        logger.error("Unexpected error in sanity checks: %s\n%s", e, traceback.format_exc())
