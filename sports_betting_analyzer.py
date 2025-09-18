# Filename: sports_betting_analyzer.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import math

# Adicionando CORS para permitir que seu site GitHub se conecte
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sports Betting Analyzer", version="0.1")

# --- Configuração do CORS ---
origins = [
    "*"  # Permite todas as origens.
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------------


class MatchInput(BaseModel):
    home_team: str
    away_team: str
    competition: str
    status: str
    minute: Optional[int] = 0

class BettingTip(BaseModel):
    market: str
    probability_pct: int
    justification: str

class MatchAnalysis(BaseModel):
    match_title: str
    top_tips: list[BettingTip]

def get_simulated_analysis(match: MatchInput):
    tips = [
        BettingTip(market=f"Vitória do {match.away_team}", probability_pct=65, justification="Time visitante tem um histórico melhor na competição."),
        BettingTip(market="Mais de 1.5 Gols no Jogo", probability_pct=78, justification="Ambos os times têm ataques fortes e o jogo está aberto."),
        BettingTip(market="Mais de 8.5 Escanteios", probability_pct=82, justification="O estilo de jogo de ambas as equipes favorece muitos cruzamentos.")
    ]
    return tips


@app.post("/analyze", response_model=MatchAnalysis)
def analyze_match(match: MatchInput):
    try:
        tips = get_simulated_analysis(match)

        report = MatchAnalysis(
            match_title=f"Análise para: {match.home_team} vs {match.away_team}",
            top_tips=tips
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"Status": "API do Analisador de Apostas está online!"}
