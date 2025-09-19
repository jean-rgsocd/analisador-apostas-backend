# sport_betting_analyzer_by_country.py
# Versão Profissional - Multi-Esportivo com Agrupamento por País
# Mantém Tipster Profile completo e endpoint by_country funcional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import httpx
import os

# ==========================
# Configuração da API-Sports
# ==========================
API_SPORTS_KEY = os.getenv("API_SPORTS_KEY")
API_SPORTS_HOSTS = {
    "football": "v3.football.api-sports.io",
    "basketball": "v1.basketball.api-sports.io",
    "nba": "v2.nba.api-sports.io",
    "american_football": "v1.american-football.api-sports.io",
    "baseball": "v1.baseball.api-sports.io",
    "formula1": "v1.formula-1.api-sports.io",
    "handball": "v1.handball.api-sports.io",
    "hockey": "v1.hockey.api-sports.io",
    "mma": "v1.mma.api-sports.io",
    "rugby": "v1.rugby.api-sports.io",
    "volleyball": "v1.volleyball.api-sports.io"
}

BASE_URLS = {sport: f"https://{host}/" for sport, host in API_SPORTS_HOSTS.items()}

# ==========================
# FastAPI App
# ==========================
app = FastAPI(title="Sports Betting Analyzer by Country")

# ==========================
# Modelos Pydantic
# ==========================
class TipsterOutput(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    start_time: datetime
    h2h_raw: List[Dict]
    predicted_pick: str = None
    confidence: float = 0.0
    tipster_profile: Dict = {}

# ==========================
# Perfil detalhado Tipster
# ==========================
TIPSTER_PROFILES_DETAILED = {
    "football": {
        "indicators": [
            "Últimos 5 jogos do time casa / visitante",
            "Últimos 5 confrontos diretos",
            "Média de gols marcados/sofridos (últimos 5)",
            "Média de escanteios (últimos 5)",
            "Média de cartões (últimos 5)",
            "Chutes ao alvo — totais e no 1º tempo (últimos 5)",
            "xG médio (se disponível)",
            "Formações/lesões-chave e odds pré-jogo"
        ],
        "pre_game": [
            "Forma recente, vantagem casa, xG vs gols reais, over/under histórico, movimentação de odds"
        ],
        "in_play_triggers": [
            "Domínio de posse >65% nos últimos 15', 2+ finalizações gol-a-alvo em <10', faltas acumuladas >X → aposta em cartão"
        ],
        "typical_picks": [
            "Vitória casa / visitante",
            "Over 1.5/2.5 gol (1º tempo ou total)",
            "Over escanteios",
            "Over cartões",
            "Ambos marcam (BTTS)"
        ],
        "required_data": [
            "Resultados",
            "Eventos por jogo (escanteios, cartões, chutes)",
            "xG se possível"
        ]
    },
    "basketball": {
        "indicators": [
            "Últimos 5 jogos de cada time (inclui D+/D- por jogador)",
            "Pontos por quarto (média últimos 5)",
            "% de aproveitamento de arremessos (FG%, 3P%, FT%)",
            "Rebotes (ofensivos/defensivos), assistências, turnovers",
            "Pace (possessões por jogo) e eficiência ofensiva/defensiva",
            "Lesões de jogadores-chave (minutes impact)"
        ],
        "pre_game": [
            "Matchup defesa vs ataque, vantagem do banco, back-to-back, viagens"
        ],
        "in_play_triggers": [
            "Variação no pace, faltas dos titulares, séries de pontos (run >10)"
        ],
        "typical_picks": [
            "Vitória moneyline",
            "Over/Under pontos totais",
            "Handicap (spread)",
            "Over de pontos de jogador",
            "Totais por quarto (1ºQ Over)"
        ],
        "required_data": ["Boxscore por jogo", "Play-by-play para triggers ao vivo"]
    },
    "nba": {
        "indicators": [
            "Últimos 5 jogos de cada time (inclui D+/D- por jogador)",
            "Pontos por quarto",
            "% de aproveitamento de arremessos",
            "Rebotes, assistências, turnovers",
            "Pace e eficiência ofensiva/defensiva",
            "Lesões de jogadores-chave"
        ],
        "pre_game": ["Matchup defesa vs ataque, vantagem do banco, back-to-back, viagens"],
        "in_play_triggers": ["Variação no pace, faltas dos titulares, séries de pontos (run >10)"],
        "typical_picks": ["Vitória moneyline", "Over/Under pontos totais", "Handicap (spread)"],
        "required_data": ["Boxscore por jogo", "Play-by-play para triggers ao vivo"]
    },
    "american_football": {
        "indicators": [
            "Últimos 5 jogos (incluindo performance por quarto)",
            "Yards oferecidas/permitidas por jogo (total e por passe/corrida)",
            "Turnovers (últimos 5)",
            "Red zone efficiency, 3rd down conversion",
            "Lesões QB/skill positions"
        ],
        "pre_game": [
            "Matchup de ataque/defesa, clima (outdoor), lesões e tempo de posse estimada"
        ],
        "in_play_triggers": ["Falhas de 3rd down, sacks, turnover momentum"],
        "typical_picks": [
            "Moneyline",
            "Spread",
            "Over/Under pontos totais",
            "Props (QB yards, TDs)"
        ],
        "required_data": ["Drive charts", "Play-by-play", "Estatísticas avançadas (DVOA se disponível)"]
    },
    "baseball": {
        "indicators": [
            "Últimos 5 jogos (incluir estatística por starting pitcher)",
            "ERA, WHIP, K/BB, FIP do arremessador titular",
            "OPS / wOBA dos rebatedores",
            "Probabilidade de vitória via simulador (Elo/xStat)",
            "Lesões/closer status"
        ],
        "pre_game": ["Matchup pitcher vs lineup (platoon splits L/R), clima/vento"],
        "in_play_triggers": ["Desempenho do pitcher por inning, bullpen usage"],
        "typical_picks": [
            "Moneyline",
            "Over/Under runs",
            "Run line (handicap)",
            "Props (total de hits/RBI para jogador)"
        ],
        "required_data": ["Boxscore", "Pitching lines", "Splits L/R"]
    },
    "formula1": {
        "indicators": [
            "Desempenho qualifying e corrida nas últimas 5 corridas",
            "Média de voltas no Top-10 por treino",
            "Tempo de volta médio, degradação de pneus, estratégia pit stops",
            "Condições meteorológicas previstas"
        ],
        "pre_game": ["Classificação, setup, histórico do circuito"],
        "in_play_triggers": ["Safety car probability, ritmo após pit, desgaste de pneus"],
        "typical_picks": [
            "Podium (top-3) / vitória",
            "Top-6/Top-10",
            "Mais rápido da corrida (fastest lap)",
            "Estratégia vencedora (número de paradas)"
        ],
        "required_data": ["Telemetria básica", "Tempos por setor", "Status de pneus"]
    },
    "handball": {
        "indicators": [
            "Últimos 5 jogos; média de gols marcados/sofridos",
            "Eficiência de arremessos (% acerto)",
            "Goleiros: % defesas",
            "Turnovers e superioridade numérica (2 min)"
        ],
        "pre_game": ["Ritmo de jogo, rotação de goleiro, forma física"],
        "in_play_triggers": ["Sequência de gols, superioridades"],
        "typical_picks": ["Vitória", "Over gols totais", "Handicap", "Over gols 1º tempo"],
        "required_data": ["Estatísticas por parcial", "Eficiência dos goleiros"]
    },
    "hockey": {
        "indicators": [
            "Últimos 5 jogos; média de gols",
            "Shots on goal (SOG) por jogo",
            "Save% dos goalies, PDO",
            "Powerplay/penalty kill %",
            "Faceoff % (quando aplicável)"
        ],
        "pre_game": ["Goalie provável, special teams"],
        "in_play_triggers": ["SOG por 20' e goalie stamina/shot volume"],
        "typical_picks": ["Moneyline", "Over/Under gols", "Puck line (handicap)", "Over powerplay chances"],
        "required_data": ["Boxscore", "SOG", "PK/PP stats"]
    },
    "mma": {
        "indicators": [
            "Últimas 5 lutas para cada lutador (stoppages vs decisão)",
            "Strikes por minuto (S/M), takedown accuracy/defense, control time",
            "Alcance, idade, layoff time",
            "Lesões e corte de peso (weigh-in issues)"
        ],
        "pre_game": ["Estilo matchup (striker vs grappler), histórico de camp e layoff"],
        "in_play_triggers": ["Ritmo da luta, clinch dominance, damage acumulado"],
        "typical_picks": [
            "Vitória por método (KO/TKO, Submission, Decision)",
            "Round total (over/under)",
            "Prop: luta vai até decisão / termina antes"
        ],
        "required_data": ["Fight metrics (FightMetric)", "Histórico de stoppages"]
    },
    "rugby": {
        "indicators": [
            "Últimos 5 jogos; média de pontos marcados/sofridos",
            "Tries por jogo, conversões, penalties",
            "Possession %, territory %, tackles missed",
            "Cartões amarelos/vermelhos"
        ],
        "pre_game": ["Clima, disciplina (cartões), força do scrum/lineout"],
        "in_play_triggers": ["Momentum de tries, penalidades acumuladas"],
        "typical_picks": ["Moneyline", "Handicap", "Over/Under pontos", "Total de tries"],
        "required_data": ["Estatísticas por fase", "Penalties"]
    },
    "volleyball": {
        "indicators": [
            "Últimos 5 jogos (sets e pontos por set)",
            "% de ataques convertidos, blocks por set, aces por set",
            "Erros de saque e recepção (efficiency)",
            "Rotação e presença de opostos/pontos fortes"
        ],
        "pre_game": ["Vantagem em saque, bloqueio, injuries"],
        "in_play_triggers": ["Runs de pontos seguidos, substituições táticas"],
        "typical_picks": ["Vitória", "Handicap (sets)", "Over/Under pontos em set/partida", "Totais de aces/blocks"],
        "required_data": ["Set-by-set stats", "Efficiency metrics"]
    }
},

# ==========================
# Funções utilitárias
# ==========================
def _is_number_str(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def evaluate_live_triggers(lhs, operator, rhs):
    if _is_number_str(lhs):
        lhs = float(lhs)
    if _is_number_str(rhs):
        rhs = float(rhs)
    if operator == ">":
        return lhs > rhs
    if operator == "<":
        return lhs < rhs
    if operator == ">=":
        return lhs >= rhs
    if operator == "<=":
        return lhs <= rhs
    if operator == "==":
        return lhs == rhs
    return False

def parse_h2h(h2h_raw, sport):
    normalized = []
    for match in h2h_raw:
        home_score = match.get("score", {}).get("home") or match.get("runs_home") or None
        away_score = match.get("score", {}).get("away") or match.get("runs_away") or None
        normalized.append({"home_score": home_score, "away_score": away_score, "winner": match.get("winner")})
    return normalized

# ==========================
# Fetch Fixtures
# ==========================
async def fetch_fixtures_from_api(sport: str) -> List[Dict]:
    host = API_SPORTS_HOSTS.get(sport)
    if not host:
        raise ValueError(f"API para {sport} não configurada")
    url = f"https://{host}/fixtures"
    headers = {"X-RapidAPI-Key": API_SPORTS_KEY, "X-RapidAPI-Host": host}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, headers=headers)
        data = response.json()
    fixtures = []
    for item in data.get("response", []):
        fixtures.append({
            "match_id": item["fixture"]["id"],
            "home_team": item["teams"]["home"]["name"],
            "away_team": item["teams"]["away"]["name"],
            "start_time": datetime.fromisoformat(item["fixture"]["date"].replace("Z","+00:00")),
            "country": item["league"]["country"],
            "league_name": item["league"]["name"],
            "h2h_raw": [],
            "home_recent_wins": None,
            "away_recent_wins": None
        })
    return fixtures

# ==========================
# Generate Picks
# ==========================
def generate_picks(match_data: Dict, sport: str) -> Dict:
    pick, confidence = "draw", 0.5
    h2h_normalized = parse_h2h(match_data.get("h2h_raw", []), sport)
    home_score_sum = sum([m["home_score"] for m in h2h_normalized if m["home_score"] is not None])
    away_score_sum = sum([m["away_score"] for m in h2h_normalized if m["away_score"] is not None])

    if sport in ["football", "basketball", "nba", "american_football", "rugby", "handball", "volleyball"]:
        if home_score_sum > away_score_sum: pick, confidence = "home", 0.7
        elif away_score_sum > home_score_sum: pick, confidence = "away", 0.7
    elif sport == "mma":
        hw, aw = match_data.get("home_recent_wins",0), match_data.get("away_recent_wins",0)
        if hw>aw: pick, confidence = "home",0.8
        elif aw>hw: pick, confidence = "away",0.8
    elif sport == "formula1":
        pick, confidence = "favorite", 0.6

    return {"predicted_pick": pick, "confidence": confidence, "tipster_profile": TIPSTER_PROFILES_DETAILED.get(sport, {})}

def build_tipster_output(matches: List[Dict], sport: str) -> List[TipsterOutput]:
    outputs=[]
    for match in matches:
        info = generate_picks(match,sport)
        outputs.append(TipsterOutput(
            match_id=match["match_id"],
            home_team=match["home_team"],
            away_team=match["away_team"],
            start_time=match["start_time"],
            h2h_raw=match.get("h2h_raw",[]),
            predicted_pick=info["predicted_pick"],
            confidence=info["confidence"],
            tipster_profile=info["tipster_profile"]
        ))
    return outputs

# ==========================
# Endpoints FastAPI
# ==========================
@app.get("/fixtures/{sport}", response_model=List[TipsterOutput])
async def get_fixtures_real(sport: str):
    try:
        matches = await fetch_fixtures_from_api(sport)
        return build_tipster_output(matches, sport)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fixtures/{sport}/by_country")
async def get_fixtures_by_country(sport: str):
    try:
        matches = await fetch_fixtures_from_api(sport)
        grouped = {}
        for m in matches:
            country = m.get("country", "Unknown")
            league = m.get("league_name", "Unknown League")
            grouped.setdefault(country, {}).setdefault(league, []).append({
                "match_id": m["match_id"],
                "home_team": m["home_team"],
                "away_team": m["away_team"],
                "start_time": m["start_time"].isoformat()
            })
        return grouped
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================
# Sanity Test
# ==========================
if __name__=="__main__":
    import asyncio
    dummy_matches=[{
        "match_id":1,"home_team":"A","away_team":"B","start_time":datetime.utcnow(),
        "h2h_raw":[{"score":{"home":2,"away":1}}],"home_recent_wins":3,"away_recent_wins":2,
        "country":"Brasil","league_name":"Serie A"
    }]
    outputs=build_tipster_output(dummy_matches,"football")
    print(outputs)
