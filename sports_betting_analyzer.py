# sports_betting_analyzer_part1.py
"""
Sports Betting Analyzer - Parte 1/4
- Base, dataclasses, utilitários
- SPORT_INDICATORS padronizado (em inglês)
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from statistics import mean, stdev
from datetime import datetime
import math

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

# -----------------------
# SPORT_INDICATORS padronizado (em inglês)
# -----------------------
SPORT_INDICATORS = {
    "Football": {
        "required_series": ["goals_for", "goals_against", "corners", "cards", "shots_on_target", "xg"],
        "live_triggers": [
            ("home_possession_15m>=65", "consider_add_pick", "dominance prolonged"),
            ("home_shots_on_target_10m>=2", "bet_over_first_half_goals", "shots first half"),
        ],
        "typical_picks": ["Moneyline", "Over_total_goals", "Over_first_half_goals", "Over_corners", "Over_cards", "BTTS"],
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
            ("starter_allowed_runs>3_in_3", "consider_bullpen_runline", "starter in trouble"),
        ],
        "typical_picks": ["Moneyline", "Over_total_runs", "Run_line", "Player_hits_prop"],
        "score_scale": 10.0
    },
    "Formula1": {
        "required_series": ["qualifying_pos", "race_finish", "lap_times", "pit_stops"],
        "live_triggers": [
            ("safety_car", "delay_aggressive_bets", "safety car active"),
        ],
        "typical_picks": ["Winner", "Podium", "Fastest_lap", "Top6"],
        "score_scale": 5.0
    },
    "Handball": {
        "required_series": ["goals_for", "goals_against", "shot_efficiency", "goalkeeper_save_pct"],
        "live_triggers": [
            ("man_up_sequence", "bet_over_goals", "numerical superiority"),
        ],
        "typical_picks": ["Moneyline", "Over_goals", "Handicap"],
        "score_scale": 5.0
    },
    "Hockey": {
        "required_series": ["goals_for", "goals_against", "shots_on_goal", "save_pct"],
        "live_triggers": [
            ("sog_20min_high", "bet_over_period_goals", "early shot volume")
        ],
        "typical_picks": ["Moneyline", "Over_goals", "Puck_line", "PP_chances"],
        "score_scale": 5.0
    },
    "MMA": {
        "required_series": ["stoppage_rate", "strikes_per_min", "td_accuracy", "control_time"],
        "live_triggers": [
            ("damage_accumulated", "consider_stop_prop", "strikes dominance")
        ],
        "typical_picks": ["Winner_method", "Over_rounds", "Fight_will_finish"],
        "score_scale": 5.0
    },
    "Rugby": {
        "required_series": ["points_for", "points_against", "tries", "penalties"],
        "live_triggers": [
            ("sin_bin_event", "bet_temp_handicap", "sin bin affects momentum")
        ],
        "typical_picks": ["Moneyline", "Handicap", "Over_points"],
        "score_scale": 10.0
    },
    "Volleyball": {
        "required_series": ["sets_for", "sets_against", "attack_pct", "blocks", "aces"],
        "live_triggers": [
            ("serve_run", "bet_set_points_over", "serve streak")
        ],
        "typical_picks": ["Match_winner", "Set_handicap", "Over_points_set"],
        "score_scale": 5.0
    }
}

# -----------------------
# Classe principal: SportsTipster
# -----------------------
class SportsTipster:
    def __init__(self, sport: str, default_N: int = 5):
        self.sport = sport if sport in SPORT_INDICATORS else sport.title()
        self.N = default_N
        self.profile = SPORT_INDICATORS.get(self.sport, {"required_series": [], "live_triggers": [], "typical_picks": ["Moneyline"], "score_scale":5.0})

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
                    numeric = [float(x) for x in v if isinstance(x, (int,float)) or (isinstance(x,str) and _is_number_str(x))]
                    if numeric:
                        additional[f"avg_{k}"] = safe_mean(numeric)
            return SeriesSummary(results=results, avg_scores_for=avg_f, avg_scores_against=avg_a, additional=additional)

        home_summary = build_summary(lastN_home or {})
        away_summary = build_summary(lastN_away or {})
        h2h_summary = build_summary(hh_lastN or {})

        return PreGameSummary(home_lastN=home_summary, away_lastN=away_summary, head2head_lastN=h2h_summary, advanced={}, market_odds={})
                             # sports_betting_analyzer_part2.py
"""
Sports Betting Analyzer - Parte 2/4
- Parsing de odds, H2H
- Normalização de scores
- Avaliação de triggers ao vivo
"""

from typing import Dict, Any, List, Optional
from .sports_betting_analyzer_part1 import safe_mean, safe_stdev, _is_number_str, clamp, _pick_label_safe, SeriesSummary, PreGameSummary, LiveSignal, Pick, TipsterOutput, SPORT_INDICATORS

# -----------------------
# Parsing e normalização
# -----------------------
def parse_market_odds(odds_dict: Dict[str, Any]) -> Dict[str, float]:
    """Converte odds do mercado para float, ignora valores inválidos"""
    parsed = {}
    for k, v in odds_dict.items():
        try:
            if isinstance(v, (int, float)):
                parsed[k] = float(v)
            elif isinstance(v, str) and _is_number_str(v):
                parsed[k] = float(v.replace(",", "."))
        except Exception:
            continue
    return parsed

def parse_h2h(h2h_raw: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """
    Converte histórico de confrontos diretos em dicionário de séries numéricas
    Ex: [{'home_goals':2, 'away_goals':1}, ...] -> {'goals_for':[2,...], 'goals_against':[1,...]}
    """
    series = {"goals_for": [], "goals_against": []}
    for match in h2h_raw:
        gf = match.get("home_goals") or match.get("goals_for")
        ga = match.get("away_goals") or match.get("goals_against")
        if _is_number_str(gf):
            series["goals_for"].append(float(gf))
        if _is_number_str(ga):
            series["goals_against"].append(float(ga))
    return series

def _normalize_score(value: float, scale: float) -> float:
    """Normaliza score entre 0 e scale"""
    return clamp(value, 0, scale)

def _map_score_to_confidence(score: float, scale: float) -> str:
    """Converte score numérico em label de confiança"""
    pct = (score / scale) * 100
    if pct >= 85:
        return "very_high"
    elif pct >= 70:
        return "high"
    elif pct >= 50:
        return "medium"
    elif pct >= 30:
        return "low"
    else:
        return "very_low"

# -----------------------
# Avaliação de triggers ao vivo
# -----------------------
def evaluate_live_triggers(sport: str, live_data: Dict[str, Any]) -> List[LiveSignal]:
    """
    Recebe dados ao vivo e retorna lista de LiveSignals acionados
    Exemplo: ("home_possession_15m>=65", "consider_add_pick", "dominance prolonged")
    """
    signals = []
    indicators = SPORT_INDICATORS.get(sport, {})
    for cond, action, note in indicators.get("live_triggers", []):
        try:
            # Segurança: cond = 'home_possession_15m>=65'
            field, expr = cond.split(">=") if ">=" in cond else (cond.split("<=")[0], cond.split("<=")[1])
            field_val = live_data.get(field.strip())
            if field_val is None:
                continue
            # Converte string numérica
            if isinstance(field_val, str) and _is_number_str(field_val):
                field_val = float(field_val.replace(",", "."))
            expr_val = float(expr)
            # Avalia condição
            if ">=" in cond and field_val >= expr_val:
                signals.append(LiveSignal(trigger=cond, action=action, note=note))
            elif "<=" in cond and field_val <= expr_val:
                signals.append(LiveSignal(trigger=cond, action=action, note=note))
        except Exception:
            continue
    return signals
# sports_betting_analyzer_part3.py
"""
Sports Betting Analyzer - Parte 3/4
- Análise pré-jogo
- Geração de picks
- Consolidação de outputs do tipster
"""

from typing import Dict, Any, List
from .sports_betting_analyzer_part1 import (
    SportsTipster, PreGameSummary, Pick, TipsterOutput, LiveSignal,
    safe_mean, safe_stdev, _map_score_to_confidence
)
from .sports_betting_analyzer_part2 import parse_market_odds, evaluate_live_triggers

# -----------------------
# Análise pré-jogo
# -----------------------
def analyze_pre_game(tipster: SportsTipster, lastN_home: Dict[str, List[float]],
                     lastN_away: Dict[str, List[float]], hh_lastN: Dict[str, List[float]],
                     market_odds: Dict[str, Any]) -> PreGameSummary:
    """
    Retorna PreGameSummary completo incluindo odds parseadas
    """
    summary = tipster.summarize_series(lastN_home, lastN_away, hh_lastN)
    summary.market_odds = parse_market_odds(market_odds)
    return summary

# -----------------------
# Geração de picks
# -----------------------
def generate_picks(pre_game_summary: PreGameSummary, sport: str, score_scale: float) -> List[Pick]:
    """
    Gera picks baseados em séries, média de gols/pontos e escala de pontuação
    """
    picks: List[Pick] = []
    indicators = SPORT_INDICATORS.get(sport, {})
    for pick_label in indicators.get("typical_picks", []):
        # Exemplo simples: confiança baseada na média de scores
        avg_home = pre_game_summary.home_lastN.avg_scores_for or 0
        avg_away = pre_game_summary.away_lastN.avg_scores_against or 0
        score = (avg_home - avg_away) + 0.5  # bias mínimo
        confidence = _map_score_to_confidence(score, indicators.get("score_scale", score_scale))
        rationale = f"Avg home {avg_home:.2f} vs Avg away {avg_away:.2f}"
        picks.append(Pick(pick=pick_label, confidence=confidence, rationale=rationale))
    return picks

# -----------------------
# Consolidação do output do tipster
# -----------------------
def build_tipster_output(tipster: SportsTipster, match_id: str,
                         lastN_home: Dict[str, List[float]], lastN_away: Dict[str, List[float]],
                         hh_lastN: Dict[str, List[float]], live_data: Dict[str, Any],
                         market_odds: Dict[str, Any]) -> TipsterOutput:
    """
    Consolida PreGameSummary, LiveSignals e Picks em um único objeto TipsterOutput
    """
    pre_game = analyze_pre_game(tipster, lastN_home, lastN_away, hh_lastN, market_odds)
    live_signals = evaluate_live_triggers(tipster.sport, live_data)
    picks = generate_picks(pre_game, tipster.sport, tipster.profile.get("score_scale", 5.0))
    overall_score = sum([(picks.index(p)+1) for p in picks]) / len(picks) if picks else 0
    confidence_overall = _map_score_to_confidence(overall_score, tipster.profile.get("score_scale",5.0))
    return TipsterOutput(
        sport=tipster.sport,
        match_id=match_id,
        pre_game_summary=pre_game,
        live_signals=live_signals,
        picks=picks,
        confidence_overall=confidence_overall,
        updated_at=now_ts()
    )
# sports_betting_analyzer_part4.py
"""
Sports Betting Analyzer - Parte 4/4
- Avaliação avançada de séries
- Suporte a múltiplos esportes e triggers complexos
- Funções helper para predição e scoring
"""

from typing import Dict, Any, List
from .sports_betting_analyzer_part1 import (
    SeriesSummary, PreGameSummary, Pick, TipsterOutput,
    safe_mean, safe_stdev, clamp
)
from .sports_betting_analyzer_part2 import evaluate_live_triggers
from .sports_betting_analyzer_part3 import generate_picks

# -----------------------
# Funções avançadas de avaliação
# -----------------------
def weighted_series_score(series: SeriesSummary, weights: Dict[str, float]) -> float:
    """
    Calcula score ponderado de uma série baseado em pesos para cada indicador
    """
    score = 0.0
    for key, weight in weights.items():
        val = series.additional.get(f"avg_{key}")
        if val is not None:
            score += val * weight
    # Normaliza score para escala 0-1
    return clamp(score, 0, 1)

def evaluate_multi_sport(pre_game: PreGameSummary, sport: str) -> Dict[str, float]:
    """
    Avalia séries avançadas dependendo do esporte
    Retorna dicionário de métricas ponderadas
    """
    indicators = pre_game.market_odds or {}
    scores = {}
    # Exemplo simplificado: soma média de gols/pontos e rebounds se disponíveis
    if sport in ["Football", "Soccer"]:
        scores["attack_vs_defense"] = ((pre_game.home_lastN.avg_scores_for or 0) -
                                       (pre_game.away_lastN.avg_scores_against or 0))
    elif sport in ["Basketball", "NBA"]:
        scores["efficiency"] = ((pre_game.home_lastN.additional.get("avg_fg_pct") or 0) -
                                (pre_game.away_lastN.additional.get("avg_fg_pct") or 0))
    return scores

# -----------------------
# Helper para scoring robusto
# -----------------------
def robust_confidence_mapping(score: float, scale: float) -> str:
    """
    Mapear score ponderado para labels de confiança, considerando outliers
    """
    normalized = clamp(score / scale, 0, 1)
    if normalized >= 0.85:
        return "very_high"
    elif normalized >= 0.7:
        return "high"
    elif normalized >= 0.5:
        return "medium"
    elif normalized >= 0.3:
        return "low"
    else:
        return "very_low"

# -----------------------
# Função helper final para predição completa
# -----------------------
def predict_tipster_output(tipster, match_id: str,
                           lastN_home: Dict[str, List[float]],
                           lastN_away: Dict[str, List[float]],
                           hh_lastN: Dict[str, List[float]],
                           live_data: Dict[str, Any],
                           market_odds: Dict[str, Any]) -> TipsterOutput:
    """
    Função completa para gerar TipsterOutput usando todas as avaliações avançadas
    """
    pre_game = tipster.summarize_series(lastN_home, lastN_away, hh_lastN)
    pre_game.market_odds = market_odds
    live_signals = evaluate_live_triggers(tipster.sport, live_data)
    picks = generate_picks(pre_game, tipster.sport, tipster.profile.get("score_scale",5.0))
    
    multi_scores = evaluate_multi_sport(pre_game, tipster.sport)
    combined_score = sum(multi_scores.values()) if multi_scores else 0
    confidence_overall = robust_confidence_mapping(combined_score, tipster.profile.get("score_scale",5.0))
    
    return TipsterOutput(
        sport=tipster.sport,
        match_id=match_id,
        pre_game_summary=pre_game,
        live_signals=live_signals,
        picks=picks,
        confidence_overall=confidence_overall,
        updated_at=now_ts()
    )

