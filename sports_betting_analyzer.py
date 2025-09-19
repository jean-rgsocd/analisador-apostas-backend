// --- LÓGICA PARA O ANALISADOR DE APOSTAS (VERSÃO TIPSTER IA) ---
const sportSelect = document.getElementById('sport-select');
const leagueSelect = document.getElementById('league-select');
const gameSelect = document.getElementById('game-select');
const bettingResultsDiv = document.getElementById('bettingResults');
let allGamesData = {};

async function fetchLeaguesBySport(sport) {
    // ... (código da função fetchLeaguesBySport que já temos, agora renomeada)
    if (!sport) return;
    const apiUrl = `https://analisador-apostas.onrender.com/jogos-do-dia?sport=${sport}`;
    leagueSelect.innerHTML = '<option value="">Carregando ligas...</option>';
    leagueSelect.disabled = true;
    try {
        const response = await fetch(apiUrl);
        if (!response.ok) throw new Error('Falha na API.');
        const data = await response.json();
        if (data.Erro || data.Info) throw new Error(data.Erro ? data.Erro[0].home : data.Info[0].home);
        
        allGamesData = data;
        leagueSelect.innerHTML = '<option value="">Selecione uma liga</option>';
        for (const leagueName in data) {
            if (Object.prototype.hasOwnProperty.call(data, leagueName) && data[leagueName].length > 0) {
                const option = document.createElement('option');
                option.value = leagueName;
                option.textContent = leagueName;
                leagueSelect.appendChild(option);
            }
        }
        leagueSelect.disabled = false;
    } catch (error) {
        leagueSelect.innerHTML = `<option value="">Erro: ${error.message}</option>`;
    }
}

// **NOVA FUNÇÃO** para buscar e mostrar a análise de um jogo
async function fetchAndDisplayAnalysis(gameId) {
    if (!gameId) {
        bettingResultsDiv.classList.add('hidden');
        return;
    }

    bettingResultsDiv.classList.remove('hidden');
    bettingResultsDiv.innerHTML = `<p class="text-slate-400 text-center">Analisando estatísticas... 🧠</p>`;

    const analyzeUrl = `https://analisador-apostas.onrender.com/analisar-jogo?game_id=${gameId}`;

    try {
        const response = await fetch(analyzeUrl);
        if (!response.ok) throw new Error('O servidor de análise retornou um erro.');
        
        const tips = await response.json();
        
        const selectedLeague = leagueSelect.value;
        const selectedGameIndex = gameSelect.value;
        const selectedGame = allGamesData[selectedLeague][selectedGameIndex];

        let htmlResult = `<h3 class="font-bold text-xl text-cyan-300">Análise Inteligente para: ${selectedGame.home} vs ${selectedGame.away}</h3>`;
        
        if (tips.length === 0 || tips[0].confidence === 0) {
             htmlResult += `<div class="p-4 border rounded-lg border-slate-700 bg-slate-900"><p class="text-slate-400">Não há dados suficientes para gerar uma análise de alta confiança para esta partida.</p></div>`;
        } else {
            tips.forEach(tip => {
                htmlResult += `
                    <div class="p-4 border rounded-lg border-slate-700 bg-slate-900">
                        <p class="text-slate-300"><strong class="text-cyan-400">Mercado:</strong> ${tip.market}</p>
                        <p class="text-slate-300"><strong class="text-cyan-400">Sugestão:</strong> ${tip.suggestion}</p>
                        <p class="text-slate-400 mt-2"><i>${tip.justification}</i></p>
                        <div class="w-full bg-slate-700 rounded-full h-2.5 mt-3">
                           <div class="bg-cyan-500 h-2.5 rounded-full" style="width: ${tip.confidence}%"></div>
                        </div>
                        <p class="text-xs text-slate-500 text-right mt-1">Confiança: ${tip.confidence}%</p>
                    </div>
                `;
            });
        }
        bettingResultsDiv.innerHTML = htmlResult;

    } catch (error) {
        bettingResultsDiv.innerHTML = `<div class="p-4 border rounded-lg border-red-500/50 bg-red-900/50 text-red-300"><strong>Erro na Análise:</strong> ${error.message}</div>`;
    }
}


// Listeners dos menus (a lógica de preenchimento continua a mesma)
sportSelect.addEventListener('change', () => fetchLeaguesBySport(sportSelect.value));
leagueSelect.addEventListener('change', () => {
    // ... (código que preenche o menu de jogos, igual ao anterior)
    const selectedLeague = leagueSelect.value;
    gameSelect.innerHTML = '<option value="">Selecione um jogo</option>';
    bettingResultsDiv.classList.add('hidden');
    if (selectedLeague && allGamesData[selectedLeague]) {
        gameSelect.disabled = false;
        allGamesData[selectedLeague].forEach((game, index) => {
            const option = document.createElement('option');
            // Agora o valor da opção será o ID do jogo!
            option.value = game.game_id; 
            option.textContent = `${game.home} vs ${game.away} (${game.time})`;
            gameSelect.appendChild(option);
        });
    } else {
        gameSelect.disabled = true;
    }
});

// **GATILHO FINAL:** Quando o usuário seleciona um JOGO
gameSelect.addEventListener('change', () => {
    const selectedGameId = gameSelect.value;
    // Chama a nova função de análise
    fetchAndDisplayAnalysis(selectedGameId);
});
