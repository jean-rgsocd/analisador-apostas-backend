# 📊 Tipster IA – Analisador de Apostas Esportivas

Backend em **FastAPI** que fornece dados e análises pré-jogo para **Futebol, NBA e NFL**.

---

## 🚀 Endpoints

### Ligas
Retorna todas as ligas disponíveis de Futebol.

---

### Jogos por Liga
Retorna os jogos disponíveis (hoje e próximos) para uma liga específica.

---

### Jogos por Esporte
- `sport` pode ser `nba` ou `nfl`.  
Retorna os jogos disponíveis (hoje e próximos) sem precisar de liga.

---

### Análise de Jogo
Retorna análise detalhada do jogo com:
- Mercado
- Sugestão
- Justificativa
- Confiança (%)

---

## 🛠️ Execução Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar servidor local
uvicorn sports_betting_analyzer:app --reload
http://127.0.0.1:8000
