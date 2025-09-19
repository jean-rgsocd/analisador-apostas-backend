# tipster_ia_part1.py
"""
TIPSTER IA - Parte 1/4
Base, dataclasses, utilitários, perfis por esporte e resumo de séries.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from statistics import mean, stdev
from datetime import datetime
import json
import math

# -----------------------
# Utilitários
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

# -----------------------
# Dataclasses de saída
# -----------------------
@dataclass
class SeriesSummary:
    results: Dict[str, int] = field(default_factory=dict)   # exemplo: {'W': 3, 'L':2}
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
    confidence: str  # 'baixa' / 'média' / 'alta'
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
# SPORT_INDICATORS (perfil por esporte)
# - required_series: séries que esperamos no input
# - live_triggers: triggers simples em formato string para avaliação básica
# - typical_picks: mercados comuns por esporte
# -----------------------
SPORT_INDICATORS = {
    "Futebol": {
        "required_series": ["goals_for", "goals_against", "corners", "cards", "shots_on_target", "xg"],
        "live_triggers": [
            ("home_possession_15m>65", "consider_add_pick", "dominio prolongado"),
            ("home_shots_on_target_10m>=2", "bet_over_first_half_goals", "finalizacoes no 1º tempo"),
        ],
        "typical_picks": ["Moneyline", "Over_total_goals", "Over_first_half_goals", "Over_corners", "Over_cards", "BTTS"]
    },
    "Basquete": {
        "required_series": ["points_for", "points_against", "fg_pct", "three_pct", "rebounds", "turnovers", "pace"],
        "live_triggers": [
            ("team_fouls_quarter>=5", "bet_over_team_fouls", "fouls acumuladas"),
            ("run_points>=10", "consider_handicap_shift", "serie de pontos")
        ],
        "typical_picks": ["Moneyline", "Over_total_points", "Spread", "Player_points_over"]
    },
    "NBA": {
        "required_series": ["points_for", "points_against", "pace", "fg_pct"],
        "live_triggers": [
            ("team_fouls_quarter>=5", "bet_over_team_fouls", "fouls acumuladas"),
        ],
        "typical_picks": ["Moneyline", "Over_total_points", "Spread"]
    },
    "NFL": {
        "required_series": ["yards_for", "yards_against", "turnovers", "redzone_eff"],
        "live_triggers": [
            ("third_down_failures>=3", "consider_pbp_prop", "3rd down failures"),
        ],
        "typical_picks": ["Moneyline", "Spread", "Over_total_points", "Prop_QB_yards"]
    },
    "Baseball": {
        "required_series": ["runs_for", "runs_against", "starter_era", "starter_whip", "ops_lineup"],
        "live_triggers": [
            ("starter_allowed_runs>3_in_3", "consider_bullpen_runline", "starter em apuros"),
        ],
        "typical_picks": ["Moneyline", "Over_total_runs", "Run_line", "Player_hits_prop"]
    },
    "Fórmula 1": {
        "required_series": ["qualifying_pos", "race_finish", "lap_times", "pit_stops"],
        "live_triggers": [
            ("safety_car", "delay_aggressive_bets", "safety car ativo"),
        ],
        "typical_picks": ["Winner", "Podium", "Fastest_lap", "Top6"]
    },
    "Handebol": {
        "required_series": ["goals_for", "goals_against", "shot_efficiency", "goalkeeper_save%"],
        "live_triggers": [
            ("man_up_sequence", "bet_over_goals", "superioridade numerica"),
        ],
        "typical_picks": ["Moneyline", "Over_goals", "Handicap"]
    },
    "Hóquei": {
        "required_series": ["goals_for", "goals_against", "shots_on_goal", "save%"],
        "live_triggers": [
            ("sog_20min_high", "bet_over_period_goals", "volume de chutes early")
        ],
        "typical_picks": ["Moneyline", "Over_goals", "Puck_line", "PP_chances"]
    },
    "MMA": {
        "required_series": ["stoppage_rate", "strikes_per_min", "td_accuracy", "control_time"],
        "live_triggers": [
            ("damage_accumulated", "consider_stop_prop", "dominancia de strikes")
        ],
        "typical_picks": ["Winner_method", "Over_rounds", "Fight_will_finish"]
    },
    "Rugby": {
        "required_series": ["points_for", "points_against", "tries", "penalties"],
        "live_triggers": [
            ("sin_bin_event", "bet_temp_handicap", "sin bin altera momentum")
        ],
        "typical_picks": ["Moneyline", "Handicap", "Over_points"]
    },
    "Vôlei": {
        "required_series": ["sets_for", "sets_against", "attack_pct", "blocks", "aces"],
        "live_triggers": [
            ("serve_run", "bet_set_points_over", "sequencia de saque")
        ],
        "typical_picks": ["Match_winner", "Set_handicap", "Over_points_set"]
    }
}

# -----------------------
# Classe principal (início)
# - __init__
# - summarize_series
# -----------------------
class SportsTipster:
    def __init__(self, sport: str, default_N: int = 5):
        # normaliza o nome (aceita 'basketball', 'Basquete', etc)
        self.sport = sport if sport in SPORT_INDICATORS else (sport.title() if sport.title() in SPORT_INDICATORS else sport)
        self.N = default_N
        # fallback profile
        if isinstance(self.sport, str) and self.sport in SPORT_INDICATORS:
            self.profile = SPORT_INDICATORS[self.sport]
        else:
            # tenta mapear por keywords
            if "basket" in sport.lower():
                self.profile = SPORT_INDICATORS.get("Basquete", SPORT_INDICATORS["Futebol"])
            elif "football" in sport.lower() and "american" not in sport.lower():
                self.profile = SPORT_INDICATORS.get("Futebol", SPORT_INDICATORS["Futebol"])
            else:
                # perfil genérico
                self.profile = {"required_series": [], "live_triggers": [], "typical_picks": ["Moneyline"]}

    def summarize_series(self, lastN_home: Dict[str, List[float]],
                         lastN_away: Dict[str, List[float]],
                         hh_lastN: Dict[str, List[float]]) -> PreGameSummary:
        """
        Recebe dicionários de séries e retorna um PreGameSummary com médias calculadas
        e campos 'additional' preenchidos com médias de outras métricas.
        """

        def build_summary(series_dict: Dict[str, Any]) -> SeriesSummary:
            results = {}
            avg_f = None
            avg_a = None
            additional = {}
            # results podem vir como dict com W/D/L ou similar
            if isinstance(series_dict.get("results"), dict):
                results = series_dict.get("results", {})
            # mapeia gols/pontos se existirem
            if "goals_for" in series_dict and isinstance(series_dict["goals_for"], list):
                avg_f = safe_mean([float(x) for x in series_dict["goals_for"] if isinstance(x, (int, float)) or (isinstance(x, str) and x.isnumeric())])
            if "goals_against" in series_dict and isinstance(series_dict["goals_against"], list):
                avg_a = safe_mean([float(x) for x in series_dict["goals_against"] if isinstance(x, (int, float)) or (isinstance(x, str) and x.isnumeric())])
            # copia outras medias numericas
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

        # advanced: placeholders para xG, forma, consistencia (ex: stdev)
        advanced = {}
        required = self.profile.get("required_series", [])
        for k in required:
            advanced[k] = {"note": "use API data if available", "avg": None, "stdev": None}

        # preenche advanced com o que for possível
        for k in required:
            # checa nos adicionais home/away/h2h
            val = None
            if f"avg_{k}" in home_summary.additional:
                val = home_summary.additional.get(f"avg_{k}")
            elif f"avg_{k}" in away_summary.additional:
                val = away_summary.additional.get(f"avg_{k}")
            advanced[k]["avg"] = val

        # market_odds ficará para o integrador preencher
        market_odds = {}
        return PreGameSummary(home_summary, away_summary, h2h_summary, advanced, market_odds)

# Helper local para checar strings numericas
def _is_number_str(s: Any) -> bool:
    try:
        if isinstance(s, str):
            # aceita floats com ponto ou vírgula
            ss = s.replace(",", ".")
            float(ss)
            return True
        return False
    except Exception:
        return False

# Fim da PARTE 1/4
# tipster_ia_part2.py
"""
TIPSTER IA - Parte 2/4
- pre_game_analysis (avançado)
- heurísticas por esporte (prioritárias)
- evaluate_live_triggers
- live_analysis (merge in-play)
"""

from typing import Tuple

# -----------------------
# Helpers internos
# -----------------------
def _map_score_to_confidence(score_norm: float) -> str:
    """Mapeia score normalizado [0..1] para 'baixa'/'média'/'alta'"""
    if score_norm >= 0.75:
        return "alta"
    if score_norm >= 0.45:
        return "média"
    return "baixa"

def _normalize_score(score: float, scale: float = 10.0) -> float:
    """
    Normaliza um score arbitrário para [0..1] usando uma sigmoide suave
    para evitar extremos erráticos em casos de outliers.
    """
    try:
        x = float(score) / float(scale)
        # sigmoid-like mapping
        return 1 / (1 + math.exp(- (x - 0.5) * 3.0))
    except Exception:
        return 0.5

def _pick_label_safe(label: str) -> str:
    return label if isinstance(label, str) else str(label)

# -----------------------
# Pre-game analysis (método que pode ser usado externo)
# -----------------------
def pre_game_analysis(self: SportsTipster, match_id: str, data: Dict[str, Any]) -> TipsterOutput:
    """
    Gera TipsterOutput usando heurísticas:
      - usa summarize_series já implementado
      - aplica heurísticas por esporte
      - garante de 1 a 3 picks (fallback seguro)
    Espera que 'data' contenha:
      - home_lastN, away_lastN, head2head_lastN
      - market_odds (opcional)
      - optional advanced metrics
    """
    # recuperar e sumarizar
    home = data.get("home_lastN", {}) or {}
    away = data.get("away_lastN", {}) or {}
    h2h = data.get("head2head_lastN", {}) or {}
    market_odds = data.get("market_odds", {}) or {}
    advanced = data.get("advanced", {}) or {}

    pre = self.summarize_series(home, away, h2h)
    pre.market_odds = market_odds
    # heurísticas
    picks: List[Pick] = []
    rationale_components: List[str] = []
    base_score = 0.0

    sport_key = self.sport

    # --- Futebol heurísticas mais robustas ---
    if sport_key.lower().startswith("futebol") or sport_key == "Futebol":
        hf = pre.home_lastN.avg_scores_for or 0.0
        ha = pre.home_lastN.avg_scores_against or 0.0
        af = pre.away_lastN.avg_scores_for or 0.0
        aa = pre.away_lastN.avg_scores_against or 0.0

        # consistência: usa stdev se enviado como lista em 'additional' (opcional)
        hf_stdev = None
        if "goals_for" in (home or {}):
            vals = home.get("goals_for", [])
            hf_stdev = safe_stdev([float(x) for x in vals if _is_number_str(x)]) if vals else None
        af_stdev = None
        if "goals_for" in (away or {}):
            vals = away.get("goals_for", [])
            af_stdev = safe_stdev([float(x) for x in vals if _is_number_str(x)]) if vals else None

        # cálculo de vantagem ofensiva e defensiva
        off_edge = (hf - af)
        def_edge = (aa - ha)
        score_raw = off_edge - def_edge
        rationale_components.append(f"off_edge={off_edge:.2f},def_edge={def_edge:.2f}")

        # favorito por moneyline
        if score_raw > 0.5:
            picks.append(Pick("Moneyline Home", "média" if score_raw < 1.5 else "alta", f"home edge {score_raw:.2f}"))
        elif score_raw < -0.5:
            picks.append(Pick("Moneyline Away", "média" if score_raw > -1.5 else "alta", f"away edge {score_raw:.2f}"))
        else:
            # pick de goals (over/under)
            avg_total_goals = (hf + af) / 2.0 + (ha + aa) / 4.0  # heurística combinada
            if avg_total_goals >= 2.4:
                picks.append(Pick("Over 2.5 Total Goals", "média", f"avg_total_goals~{avg_total_goals:.2f}"))
            else:
                picks.append(Pick("Under 2.5 Total Goals", "baixa", f"avg_total_goals~{avg_total_goals:.2f}"))

        # BTTS (both teams to score) heurística simples
        btts_score = 0.0
        if (pre.home_lastN.avg_scores_for or 0) >= 1.0 and (pre.away_lastN.avg_scores_for or 0) >= 1.0:
            btts_score += 0.4
        if (pre.home_lastN.avg_scores_against or 0) >= 1.0 or (pre.away_lastN.avg_scores_against or 0) >= 1.0:
            btts_score += 0.2
        if btts_score >= 0.5:
            picks.append(Pick("BTTS - Sim", "baixa", f"btts_score={btts_score:.2f}"))

        # corners/cards (se disponível)
        avg_corners = (pre.home_lastN.additional.get("avg_corners") or 0) + (pre.away_lastN.additional.get("avg_corners") or 0)
        if avg_corners >= 10:
            picks.append(Pick("Over Total Corners", "média", f"avg_corners_comb={avg_corners:.1f}"))
        avg_cards = (pre.home_lastN.additional.get("avg_cards") or 0) + (pre.away_lastN.additional.get("avg_cards") or 0)
        if avg_cards >= 3:
            picks.append(Pick("Over Total Cards", "baixa", f"avg_cards_comb={avg_cards:.1f}"))

        base_score = score_raw

    # --- Basquete / NBA heurísticas ---
    elif "basket" in sport_key.lower() or sport_key in ("Basquete", "NBA"):
        # tenta extrair médias pontuais dos adicionais
        home_pts = pre.home_lastN.additional.get("avg_points_for") or pre.home_lastN.avg_scores_for or 0.0
        away_pts = pre.away_lastN.additional.get("avg_points_for") or pre.away_lastN.avg_scores_for or 0.0
        diff = home_pts - away_pts
        rationale_components.append(f"home_pts={home_pts:.1f},away_pts={away_pts:.1f}")
        if diff >= 6:
            picks.append(Pick("Moneyline Home", "média", f"home_pts_adv {diff:.1f}"))
        elif diff <= -6:
            picks.append(Pick("Moneyline Away", "média", f"away_pts_adv {abs(diff):.1f}"))
        else:
            picks.append(Pick("Over Total Points (watch market)", "baixa", "small diff in averages"))
        base_score = diff

    # --- Baseball heurísticas ---
    elif "baseball" in sport_key.lower():
        h_runs = pre.home_lastN.additional.get("avg_runs_for") or pre.home_lastN.avg_scores_for or 0.0
        a_runs = pre.away_lastN.additional.get("avg_runs_for") or pre.away_lastN.avg_scores_for or 0.0
        if h_runs - a_runs >= 1.0:
            picks.append(Pick("Moneyline Home", "média", f"avg_runs {h_runs:.2f} vs {a_runs:.2f}"))
        elif a_runs - h_runs >= 1.0:
            picks.append(Pick("Moneyline Away", "média", f"avg_runs {a_runs:.2f} vs {h_runs:.2f}"))
        else:
            picks.append(Pick("Run Line / Under consideration", "baixa", "diferença pequena em corridas"))
        base_score = h_runs - a_runs

    # --- F1 heurísticas ---
    elif "formula" in sport_key.lower() or "fórmula" in sport_key.lower():
        # placeholder: se pole disponível, sugere vencedor (mais tarde melhorar com pit strategy)
        pole = advanced.get("pole_position") or None
        if pole:
            picks.append(Pick("Winner", "média", f"pole: {pole}"))
        else:
            picks.append(Pick("Top6", "baixa", "dados de grid ausentes"))
        base_score = 0.0

    # --- MMA heurísticas ---
    elif "mma" in sport_key.lower() or sport_key == "MMA":
        # tentar usar record/finishing rate
        home_fin = pre.home_lastN.additional.get("avg_fin_rate") or 0.0
        away_fin = pre.away_lastN.additional.get("avg_fin_rate") or 0.0
        home_win = pre.home_lastN.results.get("W", 0) if pre.home_lastN.results else 0
        away_win = pre.away_lastN.results.get("W", 0) if pre.away_lastN.results else 0
        # heurística simples
        if (home_win - away_win) >= 3 or (home_fin - away_fin) >= 0.15:
            picks.append(Pick("Winner - Home", "média", "record/finish advantage"))
        elif (away_win - home_win) >= 3 or (away_fin - home_fin) >= 0.15:
            picks.append(Pick("Winner - Away", "média", "record/finish advantage"))
        else:
            picks.append(Pick("Method prop / Over rounds", "baixa", "no clear advantage"))
        base_score = home_win - away_win

    # --- Generic fallback for other sports ---
    else:
        # tenta um moneyline baseado em avg_scores_for
        hf = pre.home_lastN.avg_scores_for or 0.0
        af = pre.away_lastN.avg_scores_for or 0.0
        diff = hf - af
        if diff > 1.5:
            picks.append(Pick("Moneyline Home", "média", f"home avg advantage {diff:.2f}"))
        elif diff < -1.5:
            picks.append(Pick("Moneyline Away", "média", f"away avg advantage {abs(diff):.2f}"))
        else:
            picks.append(Pick("Moneyline (tight)", "baixa", "diferença pequena"))
        base_score = diff

    # --- Odds influence: se mercado indicar favorito forte, adiciona pick (aprimora confidence) ---
    try:
        if market_odds:
            # market_odds expected format {'home': 2.1, 'draw': 3.3, 'away': 3.4}
            # converter para implied probabilities
            probs = {}
            for k, v in market_odds.items():
                try:
                    odd = float(v)
                    if odd > 1e-6:
                        probs[k] = 1.0 / odd
                except Exception:
                    continue
            if probs:
                # normaliza
                s = sum(probs.values())
                for k in list(probs.keys()):
                    probs[k] = (probs[k] / s) if s > 0 else probs[k]
                # achar favorito
                fav = max(probs.items(), key=lambda x: x[1])
                fav_name, fav_prob = fav
                if fav_prob >= 0.6:
                    # reforça favoritismo
                    picks.insert(0, Pick(f"Odds favorite: {fav_name}", "média", f"implied_prob={fav_prob:.2f}"))
                    rationale_components.append(f"odds_fav={fav_name}:{fav_prob:.2f}")
    except Exception:
        pass

    # --- Garantir 1..3 picks: dedupe e trim ---
    # remove duplicatas por 'pick' texto
    seen = set()
    unique_picks: List[Pick] = []
    for p in picks:
        key = _pick_label_safe(p.pick).lower()
        if key in seen:
            continue
        seen.add(key)
        unique_picks.append(p)
    # if none, add fallback
    if not unique_picks:
        # fallback seguro por esporte
        if "futebol" in sport_key.lower():
            unique_picks.append(Pick("Moneyline or Over 1.5", "baixa", "fallback default futebol"))
        else:
            unique_picks.append(Pick("Moneyline (fallback)", "baixa", "fallback default"))
    # limit to 3
    unique_picks = unique_picks[:3]

    # recompute overall confidence from base_score + picks
    score_norm = _normalize_score(base_score, scale=5.0)
    # also boost if any pick has 'alta'
    if any(p.confidence == "alta" for p in unique_picks):
        score_norm = min(1.0, score_norm + 0.15)
    confidence_overall = _map_score_to_confidence(score_norm)

    # montar output
    output = TipsterOutput(
        sport=self.sport,
        match_id=match_id,
        pre_game_summary=pre,
        live_signals=[],  # pre-game none
        picks=unique_picks,
        confidence_overall=confidence_overall,
        updated_at=now_ts()
    )
    return output

# atacha o método à classe (se estiver em mesmo módulo, ou substitua referencia)
SportsTipster.pre_game_analysis = pre_game_analysis

# -----------------------
# Live triggers evaluation
# -----------------------
def evaluate_live_triggers(self: SportsTipster, live_state: Dict[str, Any]) -> List[LiveSignal]:
    """
    Avalia triggers simples definidos no profile (strings como 'metric>value').
    Retorna lista de LiveSignal.
    """
    active_signals: List[LiveSignal] = []
    triggers = self.profile.get("live_triggers", []) or []
    for trig in triggers:
        try:
            expression = trig[0]
            action = trig[1] if len(trig) > 1 else "action"
            note = trig[2] if len(trig) > 2 else None
            # suportar >=, >, == simples
            if ">=" in expression:
                left, right = expression.split(">=", 1)
                left = left.strip(); right_val = float(right.strip())
                val = live_state.get(left, None)
                if val is not None and float(val) >= right_val:
                    active_signals.append(LiveSignal(expression, action, note))
            elif ">" in expression:
                left, right = expression.split(">", 1)
                left = left.strip(); right_val = float(right.strip())
                val = live_state.get(left, None)
                if val is not None and float(val) > right_val:
                    active_signals.append(LiveSignal(expression, action, note))
            elif "==" in expression:
                left, right = expression.split("==", 1)
                left = left.strip(); right_val = right.strip()
                val = live_state.get(left, None)
                if val is not None and str(val) == right_val:
                    active_signals.append(LiveSignal(expression, action, note))
        except Exception:
            continue
    return active_signals

SportsTipster.evaluate_live_triggers = evaluate_live_triggers

# -----------------------
# Live analysis: mescla picks e sinais ao vivo
# -----------------------
def live_analysis(self: SportsTipster, tipster_output: TipsterOutput, live_state: Dict[str, Any]) -> TipsterOutput:
    """
    Dado um TipsterOutput pré-existente, adiciona sinais ao vivo e possivelmente propostas in-play.
    Mantém no máximo 3 picks (prioriza picks com maior confiança).
    """
    signals = self.evaluate_live_triggers(live_state)
    added_picks: List[Pick] = []

    for s in signals:
        action = s.action.lower()
        if "first_half" in action or "firsthalf" in action:
            added_picks.append(Pick("Over 0.5 First Half", "média", f"trigger: {s.trigger}"))
        elif "consider_add_pick" in action:
            added_picks.append(Pick("In-play Over momentum", "baixa", f"trigger: {s.trigger}"))
        elif "handicap" in action or "spread" in action:
            added_picks.append(Pick("In-play Handicap shift", "média", f"trigger: {s.trigger}"))
        else:
            # generic signal -> small value in-play suggestion
            added_picks.append(Pick(f"In-play suggestion ({s.action})", "baixa", f"trigger: {s.trigger}"))

    # combine and sort by confidence (alta > média > baixa)
    priority = {"alta": 3, "média": 2, "media": 2, "baixa": 1}
    combined = tipster_output.picks + added_picks
    # remove duplicates by pick text
    seen = set()
    unique_combined = []
    for p in combined:
        key = _pick_label_safe(p.pick).lower()
        if key in seen:
            continue
        seen.add(key)
        unique_combined.append(p)
    # sort by priority (descending)
    unique_combined.sort(key=lambda p: priority.get(p.confidence, 1), reverse=True)
    tipster_output.picks = unique_combined[:3]

    # recompute confidence_overall
    if any(p.confidence == "alta" for p in tipster_output.picks):
        tipster_output.confidence_overall = "alta"
    elif any(p.confidence == "média" for p in tipster_output.picks):
        tipster_output.confidence_overall = "média"
    else:
        tipster_output.confidence_overall = "baixa"

    tipster_output.live_signals = signals
    tipster_output.updated_at = now_ts()
    return tipster_output

SportsTipster.live_analysis = live_analysis

# Fim da PARTE 2/4
# tipster_ia_part3.py
"""
TIPSTER IA - Parte 3/4
- Serialização JSON
- Helpers para parsing de H2H / Odds
- Funções utilitárias para integração
"""

# -----------------------
# Serialização TipsterOutput
# -----------------------
def tipster_to_json(self: TipsterOutput) -> str:
    """
    Serializa TipsterOutput para JSON, garantindo que tipos como datetime
    e dataclasses sejam convertidos.
    """
    def default_serializer(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if hasattr(o, "__dict__"):
            return asdict(o)
        return str(o)

    return json.dumps(asdict(self), default=default_serializer, ensure_ascii=False, indent=2)

TipsterOutput.to_json = tipster_to_json

# -----------------------
# Helpers para parsing H2H (head-to-head) simplificado
# -----------------------
def parse_h2h(raw_h2h: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """
    Converte uma lista de confrontos diretos em dicionário de séries numéricas.
    Exemplo: [{'home_goals':2,'away_goals':1}, ...] -> {'goals_for':[2,3], 'goals_against':[1,1]}
    """
    goals_for, goals_against = [], []
    for entry in raw_h2h:
        try:
            hf = float(entry.get("home_goals", 0))
            af = float(entry.get("away_goals", 0))
            goals_for.append(hf)
            goals_against.append(af)
        except Exception:
            continue
    return {"goals_for": goals_for, "goals_against": goals_against}

# -----------------------
# Helpers para parsing de odds
# -----------------------
def parse_market_odds(raw_odds: Dict[str, Any]) -> Dict[str, float]:
    """
    Converte odds de formatos variados para float
    - suporta string '2.3' ou int/float
    - ignora valores inválidos
    """
    parsed = {}
    for k, v in raw_odds.items():
        try:
            parsed[k] = float(v)
        except Exception:
            continue
    return parsed

# -----------------------
# Exemplo helper: criar TipsterOutput diretamente de dados crus
# -----------------------
def create_tipster_from_raw(self: SportsTipster, match_id: str,
                             home_lastN: Dict[str, Any],
                             away_lastN: Dict[str, Any],
                             h2h_raw: Optional[List[Dict[str, Any]]] = None,
                             market_odds_raw: Optional[Dict[str, Any]] = None) -> TipsterOutput:
    """
    Constrói TipsterOutput diretamente de dados crus
    - aplica parsing H2H e odds
    - chama pre_game_analysis
    """
    h2h_parsed = parse_h2h(h2h_raw) if h2h_raw else {}
    market_odds_parsed = parse_market_odds(market_odds_raw) if market_odds_raw else {}
    data = {
        "home_lastN": home_lastN,
        "away_lastN": away_lastN,
        "head2head_lastN": h2h_parsed,
        "market_odds": market_odds_parsed
    }
    return self.pre_game_analysis(match_id, data)

SportsTipster.create_tipster_from_raw = create_tipster_from_raw

# -----------------------
# FastAPI endpoint helper (pseudo)
# -----------------------
def tipster_api_response(self: SportsTipster, match_id: str,
                         home_lastN: Dict[str, Any],
                         away_lastN: Dict[str, Any],
                         h2h_raw: Optional[List[Dict[str, Any]]] = None,
                         market_odds_raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Retorna dicionário pronto para JSONResponse no FastAPI
    """
    tipster_output = self.create_tipster_from_raw(match_id, home_lastN, away_lastN, h2h_raw, market_odds_raw)
    return asdict(tipster_output)

SportsTipster.tipster_api_response = tipster_api_response

# Fim da PARTE 3/4
# tipster_ia_part4.py
"""
TIPSTER IA - Parte 4/4
- Exemplos de uso
- Sanity checks / unit test templates
- Fallbacks e logs de auditoria
"""

import logging

# -----------------------
# Configuração básica de logs
# -----------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("TIPSTER_IA")

# -----------------------
# Exemplo de uso básico
# -----------------------
if __name__ == "__main__":
    # inicializa tipster para futebol
    tipster = SportsTipster("Futebol", default_N=5)

    # dados simulados
    home_lastN = {
        "results": {"W":3, "L":2},
        "goals_for":[2,1,3,0,2],
        "goals_against":[1,1,0,2,2],
        "corners":[5,6,4,7,5],
        "cards":[1,2,1,0,1]
    }

    away_lastN = {
        "results": {"W":2, "L":3},
        "goals_for":[1,0,2,1,0],
        "goals_against":[2,1,3,0,1],
        "corners":[3,4,2,5,4],
        "cards":[2,1,1,1,0]
    }

    h2h_raw = [
        {"home_goals":2,"away_goals":1},
        {"home_goals":1,"away_goals":0},
        {"home_goals":0,"away_goals":1}
    ]

    market_odds_raw = {"home":2.1,"draw":3.3,"away":3.5}

    # gera TipsterOutput
    output = tipster.create_tipster_from_raw(
        match_id="match_123",
        home_lastN=home_lastN,
        away_lastN=away_lastN,
        h2h_raw=h2h_raw,
        market_odds_raw=market_odds_raw
    )

    # log completo
    logger.info(f"Tipster Output:\n{output.to_json()}")

# -----------------------
# Sanity checks / template unit test
# -----------------------
def test_tipster_basic():
    tipster = SportsTipster("Futebol")
    output = tipster.create_tipster_from_raw("test_match", home_lastN, away_lastN, h2h_raw, market_odds_raw)
    assert isinstance(output, TipsterOutput)
    assert len(output.picks) >= 1 and len(output.picks) <= 3
    assert output.confidence_overall in ["baixa","média","alta"]
    logger.info("Sanity test passed")

# -----------------------
# Fallbacks de dados
# -----------------------
def safe_get_series(series: Dict[str, Any], key: str, fallback: float = 0.0) -> float:
    """
    Retorna valor seguro de série numérica, aplicando fallback
    """
    try:
        val = series.get(key)
        if isinstance(val, list) and val:
            return float(val[-1])
        if isinstance(val, (int,float)):
            return float(val)
        if isinstance(val, str) and _is_number_str(val):
            return float(val.replace(",","."))
    except Exception:
        pass
    return fallback

# -----------------------
# Auditoria simples
# -----------------------
def log_audit(match_id: str, tipster_output: TipsterOutput, stage: str = "pre_game"):
    """
    Loga informações resumidas para auditoria ou debugging
    """
    picks_str = ", ".join([p.pick for p in tipster_output.picks])
    logger.info(f"[AUDIT:{stage}] Match:{match_id} Picks:[{picks_str}] Confidence:{tipster_output.confidence_overall}")

SportsTipster.log_audit = log_audit
SportsTipster.safe_get_series = safe_get_series

# Fim da PARTE 4/4

