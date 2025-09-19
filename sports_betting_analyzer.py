# Adicione estas novas importações no início do seu arquivo
from typing import Optional

# ... (resto do seu código existente) ...

# --- NOVOS ENDPOINTS PARA FILTROS DINÂMICOS ---

@app.get("/paises")
async def get_countries():
    """Retorna uma lista de países disponíveis na API."""
    # Este endpoint idealmente teria cache também
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    
    url = "https://v3.football.api-sports.io/countries"
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    
    async with httpx.AsyncClient() as client:
        data = await fetch_api_data_async(client, {}, headers, url)
        
    # Formata para ser fácil de usar no frontend (ex: [{ "name": "Brazil", "code": "BR" }])
    return [{"name": c.get("name"), "code": c.get("code")} for c in data if c.get("code")]

@app.get("/ligas")
async def get_leagues_by_country(country_code: str):
    """Retorna as ligas de um país específico."""
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")
    
    url = "https://v3.football.api-sports.io/leagues"
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    querystring = {"code": country_code, "season": str(datetime.now().year)} # Busca pela temporada atual
    
    async with httpx.AsyncClient() as client:
        data = await fetch_api_data_async(client, querystring, headers, url)
        
    # Formata para o frontend (ex: [{ "id": 123, "name": "Serie A" }])
    return [{"id": l.get("league", {}).get("id"), "name": l.get("league", {}).get("name")} for l in data]

# --- ATUALIZAÇÃO NO ENDPOINT DE JOGOS ---
# Vamos modificar o endpoint `/jogos-do-dia` para aceitar filtros
@app.get("/jogos") # Renomeado para maior clareza
async def get_games_by_filter(league_id: int, date: Optional[str] = None):
    """
    Busca jogos por liga e, opcionalmente, por data.
    Se a data não for fornecida, busca a data de hoje.
    """
    api_key = os.getenv("API_KEY")
    if not api_key: raise HTTPException(status_code=500, detail="Chave da API não configurada.")

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    url = "https://v3.football.api-sports.io/fixtures"
    headers = {'x-rapidapi-host': "v3.football.api-sports.io", 'x-rapidapi-key': api_key}
    querystring = {"league": str(league_id), "season": str(datetime.now().year), "date": date}

    async with httpx.AsyncClient() as client:
        fixtures_data = await fetch_api_data_async(client, querystring, headers, url)

    # Reutiliza sua lógica de formatação de jogos
    games_list = []
    if not fixtures_data:
        return []

    for item in fixtures_data:
        home_team = item.get("teams", {}).get("home", {}).get("name", "N/A")
        away_team = item.get("teams", {}).get("away", {}).get("name", "N/A")
        game_id = item.get("fixture", {}).get("id", 0)
        status = item.get("fixture", {}).get("status", {}).get("short", "N/A")
        timestamp = item.get("fixture", {}).get("timestamp")
        game_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else "N/A"
        
        games_list.append(GameInfo(home=home_team, away=away_team, time=game_time, game_id=game_id, status=status))
    
    return games_list
