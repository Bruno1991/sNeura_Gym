/**
 * GymArena Mobile - Complete Interactive Client Engine
 * 100% Fidelity Mobile Experience matching Chess.com Android APK
 */

// ============================================================================
// AUDIO MANAGER (66 Efeitos Sonoros Oficiais Extraídos do APK)
// ============================================================================
class AudioManager {
  constructor() {
    this.soundCache = {};
    this.soundPaths = {
      'move-self': '/assets/sounds/move-self.mp3',
      'move-opponent': '/assets/sounds/move-opponent.mp3',
      'move': '/assets/sounds/move-self.mp3',
      'capture': '/assets/sounds/capture.mp3',
      'check': '/assets/sounds/move-check.mp3',
      'move-check': '/assets/sounds/move-check.mp3',
      'castle': '/assets/sounds/castle.mp3',
      'promote': '/assets/sounds/promote.mp3',
      'game-start': '/assets/sounds/game-start.mp3',
      'game-win': '/assets/sounds/game-win.mp3',
      'game-lose': '/assets/sounds/game-lose.mp3',
      'game-draw': '/assets/sounds/game-draw.mp3',
      'illegal': '/assets/sounds/illegal.mp3',
      'tenseconds': '/assets/sounds/tenseconds.mp3'
    };

    // Preload principais sons
    for (const [key, path] of Object.entries(this.soundPaths)) {
      const audio = new Audio();
      audio.src = path;
      audio.preload = 'auto';
      this.soundCache[key] = audio;
    }
  }

  play(soundKey) {
    try {
      const sound = this.soundCache[soundKey] || this.soundCache['move-self'];
      if (sound) {
        sound.currentTime = 0;
        sound.play().catch(e => {
          // Normal em navegadores antes da primeira interação
          console.debug(`Audio play deferred: ${soundKey}`);
        });
      }
    } catch (err) {
      console.warn("Audio error:", err);
    }
  }
}

// ============================================================================
// GYM ARENA STATE & APP CONTROLLER
// ============================================================================
class GymArenaApp {
  constructor() {
    this.audio = new AudioManager();
    this.bots = [];
    this.selectedBot = null;
    this.selectedMode = 'neural_vs_bot'; // 'neural_vs_bot', 'human_vs_bot', 'human_vs_neural'
    this.selectedColor = 'white'; // 'white', 'random', 'black'
    this.selectedSims = 50;
    this.mctsActive = true;

    // Estado da partida atual
    this.gameState = null;
    this.selectedSquare = null;
    this.legalMovesForSelected = [];
    this.isFlipped = false;
    this.autoPlayInterval = null;
    this.duelSpeed = 500;
    this.isProcessingMove = false;
    this.speechTimeout = null;
    this.ws = null;
    this.matchSessionId = 0;

    // Mapeamento de peças em caracteres para nomes de arquivos SVG
    this.pieceSvgMap = {
      'P': 'wp', 'N': 'wn', 'B': 'wb', 'R': 'wr', 'Q': 'wq', 'K': 'wk',
      'p': 'bp', 'n': 'bn', 'b': 'bb', 'r': 'br', 'q': 'bq', 'k': 'bk'
    };

    this.initElements();
    this.bindEvents();
    this.startClock();
    this.initWebSocket();
    this.loadBotsCatalog();
  }

  initElements() {
    // Cabeçalho e Telas
    this.statusClock = document.getElementById('statusClock');
    this.headerMainTitle = document.getElementById('headerMainTitle');
    this.headerSubBadge = document.getElementById('headerSubBadge');
    this.btnBackToCatalog = document.getElementById('btnBackToCatalog');
    this.catalogScreen = document.getElementById('catalogScreen');
    this.matchScreen = document.getElementById('matchScreen');
    this.botsListContainer = document.getElementById('botsListContainer');
    this.botSearchInput = document.getElementById('botSearchInput');
    this.btnClearSearch = document.getElementById('btnClearSearch');
    this.categoryTabs = document.getElementById('categoryTabs');

    // Drawer de Desafio
    this.challengeDrawer = document.getElementById('challengeDrawer');
    this.drawerBotAvatar = document.getElementById('drawerBotAvatar');
    this.drawerBotElo = document.getElementById('drawerBotElo');
    this.drawerBotName = document.getElementById('drawerBotName');
    this.drawerBotCategory = document.getElementById('drawerBotCategory');
    this.drawerBotBio = document.getElementById('drawerBotBio');
    this.drawerMctsStatus = document.getElementById('drawerMctsStatus');
    this.btnStartGameConfirmed = document.getElementById('btnStartGameConfirmed');

    // Tabuleiro e HUDs
    this.boardFrame = document.getElementById('boardFrame');
    this.chessGrid = document.getElementById('chessGrid');
    this.mobileEvalTrack = document.getElementById('mobileEvalTrack');
    this.mobileEvalFill = document.getElementById('mobileEvalFill');
    this.mobileEvalNumber = document.getElementById('mobileEvalNumber');
    
    this.oppAvatar = document.getElementById('oppAvatar');
    this.oppName = document.getElementById('oppName');
    this.oppElo = document.getElementById('oppElo');
    this.oppTurnRing = document.getElementById('oppTurnRing');
    this.oppCapturedTray = document.getElementById('oppCapturedTray');
    this.oppLeadPill = document.getElementById('oppLeadPill');
    this.botSpeechBubble = document.getElementById('botSpeechBubble');
    this.speechText = document.getElementById('speechText');

    this.meAvatar = document.getElementById('meAvatar');
    this.meName = document.getElementById('meName');
    this.meElo = document.getElementById('meElo');
    this.meRoleBadge = document.getElementById('meRoleBadge');
    this.meTurnRing = document.getElementById('meTurnRing');
    this.meCapturedTray = document.getElementById('meCapturedTray');
    this.meLeadPill = document.getElementById('meLeadPill');
    this.turnStatusBadge = document.getElementById('turnStatusBadge');

    // Telemetria e Ações
    this.telModeDisplay = document.getElementById('telModeDisplay');
    this.telBestMove = document.getElementById('telBestMove');
    this.telEvalScore = document.getElementById('telEvalScore');
    this.telConfidence = document.getElementById('telConfidence');
    this.btnHintMove = document.getElementById('btnHintMove');
    this.btnUndoMove = document.getElementById('btnUndoMove');
    this.btnToggleMcts = document.getElementById('btnToggleMcts');
    this.mctsBtnLabel = document.getElementById('mctsBtnLabel');
    this.btnFlipBoard = document.getElementById('btnFlipBoard');
    this.btnResignMatch = document.getElementById('btnResignMatch');

    this.duelSpeedControl = document.getElementById('duelSpeedControl');
    this.duelSpeedSlider = document.getElementById('duelSpeedSlider');
    this.duelSpeedVal = document.getElementById('duelSpeedVal');

    // Navegação Inferior
    this.tabNavPlay = document.getElementById('tabNavPlay');
    this.tabNavNeuralDuel = document.getElementById('tabNavNeuralDuel');
    this.tabNavMcts = document.getElementById('tabNavMcts');
    this.tabNavSettings = document.getElementById('tabNavSettings');

    // Modal Game Over
    this.gameOverModal = document.getElementById('gameOverModal');
    this.gameOverTrophy = document.getElementById('gameOverTrophy');
    this.gameOverTitle = document.getElementById('gameOverTitle');
    this.gameOverDesc = document.getElementById('gameOverDesc');
    this.modalRematchBtn = document.getElementById('modalRematchBtn');
    this.modalChooseBotBtn = document.getElementById('modalChooseBotBtn');
  }

  bindEvents() {
    // Relógio e Busca
    this.botSearchInput.addEventListener('input', () => this.filterBots());
    this.btnClearSearch.addEventListener('click', () => {
      this.botSearchInput.value = '';
      this.btnClearSearch.classList.add('hidden');
      this.filterBots();
    });

    // Abas de Categoria
    this.categoryTabs.addEventListener('click', (e) => {
      const pill = e.target.closest('.cat-pill');
      if (!pill) return;
      document.querySelectorAll('.cat-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      this.filterBots();
    });

    // Fechar Drawer ao clicar no backdrop
    this.challengeDrawer.addEventListener('click', (e) => {
      if (e.target === this.challengeDrawer) {
        this.closeChallengeDrawer();
      }
    });

    // Modos de jogo no Drawer
    document.querySelectorAll('.mode-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.mode-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        this.selectedMode = chip.dataset.mode;
      });
    });

    // Escolha de cor no Drawer
    document.querySelectorAll('.color-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.color-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        this.selectedColor = chip.dataset.color;
      });
    });

    // Escolha de simulações no Drawer
    document.querySelectorAll('.sim-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.sim-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        this.selectedSims = parseInt(chip.dataset.sims, 10);
        this.drawerMctsStatus.textContent = `Ativo (${this.selectedSims} nós)`;
      });
    });

    // Iniciar Partida
    this.btnStartGameConfirmed.addEventListener('click', () => this.startMatch());

    // Voltar para o Catálogo
    this.btnBackToCatalog.addEventListener('click', () => this.showCatalogScreen());

    // Inverter Tabuleiro
    this.btnFlipBoard.addEventListener('click', () => {
      this.isFlipped = !this.isFlipped;
      this.renderBoard();
    });

    // Dica Tática
    this.btnHintMove.addEventListener('click', () => this.requestHint());

    // Desfazer Lance
    this.btnUndoMove.addEventListener('click', () => this.undoMove());

    // Ligar / Desligar MCTS
    this.btnToggleMcts.addEventListener('click', () => this.toggleMcts());

    // Opções / Desistir
    this.btnResignMatch.addEventListener('click', () => this.confirmResign());

    // Slider de Velocidade
    this.duelSpeedSlider.addEventListener('input', (e) => {
      this.duelSpeed = parseInt(e.target.value, 10);
      this.duelSpeedVal.textContent = `${this.duelSpeed}ms`;
      if (this.autoPlayTimeout || this.autoPlayInterval) {
        this.restartAutoPlay();
      }
    });

    // Navegação Inferior
    this.tabNavPlay.addEventListener('click', () => {
      this.setActiveNavTab(this.tabNavPlay);
      this.showCatalogScreen();
    });
    this.tabNavNeuralDuel.addEventListener('click', () => {
      this.setActiveNavTab(this.tabNavNeuralDuel);
      const bot = this.bots.find(b => b.name === 'Nelson') || this.bots[1];
      if (bot) this.openChallengeDrawer(bot, 'neural_vs_bot');
    });
    this.tabNavMcts.addEventListener('click', () => {
      this.setActiveNavTab(this.tabNavMcts);
      const bot = this.bots.find(b => b.name === 'Neural_Bot') || this.bots[0];
      if (bot) this.openChallengeDrawer(bot, 'human_vs_neural');
    });
    this.tabNavSettings.addEventListener('click', () => {
      this.setActiveNavTab(this.tabNavSettings);
      alert("GymArena Mobile:\n- 100% Offline & Local\n- 218 Bots Oficiais do APK\n- Neural_Bot (3200 Elo ResNet MCTS)\n- Sons e Avatares Nativos");
    });

    // Modal Game Over Ações
    this.modalRematchBtn.addEventListener('click', () => {
      this.gameOverModal.classList.add('hidden');
      this.startMatch();
    });
    this.modalChooseBotBtn.addEventListener('click', () => {
      this.gameOverModal.classList.add('hidden');
      this.showCatalogScreen();
    });
  }

  initWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws/match`;
    try {
      this.ws = new WebSocket(wsUrl);
      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'state_update' && msg.state) {
            this.handleIncomingState(msg.state);
          }
        } catch (e) {
          console.warn("WS Parse error:", e);
        }
      };
      this.ws.onclose = () => {
        setTimeout(() => this.initWebSocket(), 3000);
      };
    } catch (e) {
      console.warn("WebSocket connect failed:", e);
    }
  }

  handleIncomingState(state) {
    this.gameState = state;
    this.renderBoard();
    this.updateHUD();

    if (state.current_speech && state.current_speech.text) {
      this.showBotSpeech(state.current_speech.text);
    }

    if (state.is_game_over) {
      this.handleGameOver();
    }
  }

  startClock() {
    const updateTime = () => {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      this.statusClock.textContent = `${hours}:${minutes}`;
    };
    updateTime();
    setInterval(updateTime, 10000);
  }

  setActiveNavTab(activeEl) {
    [this.tabNavPlay, this.tabNavNeuralDuel, this.tabNavMcts, this.tabNavSettings].forEach(tab => {
      tab.classList.remove('active');
    });
    activeEl.classList.add('active');
  }

  // ============================================================================
  // CATÁLOGO DE BOTS
  // ============================================================================
  async loadBotsCatalog() {
    try {
      const res = await fetch('/api/bots');
      const data = await res.json();
      let rawBots = [];
      if (Array.isArray(data.bots)) {
        rawBots = data.bots;
      } else if (Array.isArray(data.categories)) {
        rawBots = data.categories.flatMap(c => c.bots || []);
      }

      this.bots = rawBots.map(b => ({
        id: b.username || b.name,
        name: b.name,
        elo: parseInt(b.rating || b.elo || 1500, 10),
        category: b.group || b.category || 'Oficial',
        avatar: b.avatar || `/assets/avatars/${b.name}.png`,
        bio: b.description || b.bio || 'Bot oficial do app mobile.',
        greeting: b.greeting || `Olá, eu sou ${b.name}!`,
        is_neural: Boolean(b.is_neural)
      }));

      this.headerSubBadge.textContent = `${this.bots.length} Bots`;
      this.renderBotsList(this.bots);
    } catch (err) {
      console.error("Erro ao carregar catálogo de bots:", err);
    }
  }

  filterBots() {
    const query = this.botSearchInput.value.toLowerCase().trim();
    if (query.length > 0) {
      this.btnClearSearch.classList.remove('hidden');
    } else {
      this.btnClearSearch.classList.add('hidden');
    }

    const activePill = document.querySelector('.cat-pill.active');
    const category = activePill ? activePill.dataset.category : 'all';

    const filtered = this.bots.filter(bot => {
      // Filtro de Categoria
      let matchesCategory = true;
      if (category === '🧠 Neural_Bot 3200') {
        matchesCategory = bot.name === 'Neural_Bot' || bot.is_neural;
      } else if (category !== 'all') {
        matchesCategory = (bot.category || '').toLowerCase().includes(category.toLowerCase());
      }

      // Filtro de Busca
      let matchesSearch = true;
      if (query) {
        matchesSearch = (
          bot.name.toLowerCase().includes(query) ||
          (bot.category || '').toLowerCase().includes(query) ||
          String(bot.elo).includes(query) ||
          (bot.bio || '').toLowerCase().includes(query)
        );
      }

      return matchesCategory && matchesSearch;
    });

    this.renderBotsList(filtered);
  }

  renderBotsList(bots) {
    this.botsListContainer.innerHTML = '';
    if (bots.length === 0) {
      this.botsListContainer.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); padding: 40px 10px;">
          Nenhum bot encontrado com esse filtro.
        </div>`;
      return;
    }

    bots.forEach(bot => {
      const card = document.createElement('div');
      card.className = `bot-card-item ${bot.name === 'Neural_Bot' ? 'featured-bot' : ''}`;
      card.innerHTML = `
        <div class="bot-avatar-container">
          <img src="${bot.avatar}" alt="" class="bot-avatar-img" onerror="this.onerror=null; this.src='/assets/avatars/default.png'">
          <span class="bot-elo-badge">${bot.elo}</span>
        </div>
        <div class="bot-meta-info">
          <div class="bot-name-row">
            <span class="bot-title-name">${bot.name}</span>
            <span class="bot-category-tag">• ${bot.category || 'Mestre'}</span>
          </div>
          <p class="bot-bio-snippet">${bot.bio || 'Desafie este bot oficial em GymArena.'}</p>
        </div>
        <button class="bot-play-btn-mini" title="Desafiar ${bot.name}">▶</button>
      `;

      card.addEventListener('click', () => {
        this.openChallengeDrawer(bot);
      });

      this.botsListContainer.appendChild(card);
    });
  }

  // ============================================================================
  // DRAWER INFERIOR DE DESAFIO
  // ============================================================================
  openChallengeDrawer(bot, presetMode = null) {
    this.selectedBot = bot;
    this.drawerBotAvatar.src = bot.avatar;
    this.drawerBotElo.textContent = bot.elo;
    this.drawerBotName.textContent = bot.name;
    this.drawerBotCategory.textContent = bot.category || 'Bot Oficial';
    this.drawerBotBio.textContent = bot.bio || 'Preparado para jogar com fidelidade 100% nativa.';

    if (presetMode) {
      this.selectedMode = presetMode;
      document.querySelectorAll('.mode-chip').forEach(c => {
        c.classList.toggle('active', c.dataset.mode === presetMode);
      });
    }

    this.challengeDrawer.classList.remove('hidden');
  }

  closeChallengeDrawer() {
    this.challengeDrawer.classList.add('hidden');
  }

  // ============================================================================
  // TRANSIÇÕES DE TELA E PARTIDA
  // ============================================================================
  showCatalogScreen() {
    this.matchSessionId++;
    this.stopAutoPlay();
    this.isProcessingMove = false;
    this.selectedSquare = null;
    this.legalMovesForSelected = [];
    this.matchScreen.classList.add('hidden');
    this.catalogScreen.classList.remove('hidden');
    this.btnBackToCatalog.classList.add('hidden');
    this.headerMainTitle.textContent = "Computador";
    this.headerSubBadge.textContent = `${this.bots.length} Bots`;
    this.setActiveNavTab(this.tabNavPlay);
  }

  showMatchScreen() {
    this.catalogScreen.classList.add('hidden');
    this.matchScreen.classList.remove('hidden');
    this.btnBackToCatalog.classList.remove('hidden');
    this.headerMainTitle.textContent = "Partida";
    this.headerSubBadge.textContent = this.selectedBot ? this.selectedBot.name : "GymArena";
  }

  async startMatch() {
    if (!this.selectedBot) return;
    this.matchSessionId++;
    const session = this.matchSessionId;
    this.closeChallengeDrawer();
    this.showMatchScreen();
    this.stopAutoPlay();
    this.isProcessingMove = false;
    this.selectedSquare = null;
    this.legalMovesForSelected = [];

    const payload = {
      mode: this.selectedMode,
      player_color: this.selectedColor,
      bot_name: this.selectedBot.name,
      bot_elo: this.selectedBot.elo,
      neural_mode: this.mctsActive ? "mcts" : "direct",
      mcts_sims: this.selectedSims,
      step_delay: 0.5,
      auto_play: (this.selectedMode === 'neural_vs_bot')
    };

    try {
      const res = await fetch('/api/match/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success || data.status === 'success') {
        this.gameState = data.state;
        this.audio.play('game-start');
        this.setupMatchLayout();
        this.renderBoard();
        this.updateHUD();

        // Frase de abertura do bot
        if (this.gameState.current_speech && this.gameState.current_speech.text) {
          this.showBotSpeech(this.gameState.current_speech.text);
        } else if (this.selectedBot.greeting) {
          this.showBotSpeech(this.selectedBot.greeting);
        }

        // Se for duelo neural automático, inicia o loop
        if (this.selectedMode === 'neural_vs_bot') {
          this.duelSpeedControl.style.display = 'flex';
          this.startAutoPlay();
        } else {
          this.duelSpeedControl.style.display = 'none';
          const humanColor = (payload.player_color === 'black') ? 'b' : 'w';
          if (this.gameState.turn !== humanColor && !this.gameState.is_game_over) {
            setTimeout(() => this.triggerBotStep(), 600);
          }
        }
      }
    } catch (err) {
      console.error("Erro ao iniciar partida:", err);
    }
  }

  setupMatchLayout() {
    const state = this.gameState;
    const whitePlayer = state.white_player || state.player_white || {};
    const blackPlayer = state.black_player || state.player_black || {};

    // Se o humano joga de pretas, vira o tabuleiro
    this.isFlipped = (blackPlayer.type === 'human');

    // Determina quem fica no topo (opp) e na base (me)
    const topPlayer = this.isFlipped ? whitePlayer : blackPlayer;
    const bottomPlayer = this.isFlipped ? blackPlayer : whitePlayer;

    // Configura oponentes no HUD
    this.oppAvatar.src = topPlayer.avatar || '/assets/avatars/default.png';
    this.oppName.textContent = topPlayer.name || 'Oponente';
    this.oppElo.textContent = topPlayer.elo || 1500;

    this.meAvatar.src = bottomPlayer.avatar || (bottomPlayer.type === 'neural' ? '/assets/avatars/neural_bot.png' : '/assets/avatars/default.png');
    this.meName.textContent = bottomPlayer.name || 'Jogador';
    this.meElo.textContent = bottomPlayer.elo || 3200;
    this.meRoleBadge.textContent = bottomPlayer.type === 'human' ? 'VOCÊ' : (bottomPlayer.type === 'neural' ? 'NEURAL AI' : 'BOT');
  }

  // ============================================================================
  // RENDERIZAÇÃO DO TABULEIRO E LANCES (100% FIDELIDADE)
  // ============================================================================
  renderBoard() {
    this.chessGrid.innerHTML = '';
    const rawFen = this.gameState ? (this.gameState.fen || this.gameState.board_fen || '') : '';
    const fen = rawFen.split(' ')[0] || 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR';
    const matrix = this.fenToMatrix(fen);

    // Obtém coordenadas de origem e destino do último lance
    let lastFrom = null;
    let lastTo = null;
    if (this.gameState && this.gameState.last_move) {
      const lm = this.gameState.last_move;
      if (typeof lm === 'string') {
        lastFrom = lm.slice(0, 2);
        lastTo = lm.slice(2, 4);
      } else if (lm.from && lm.to) {
        lastFrom = lm.from;
        lastTo = lm.to;
      }
    }

    const inCheck = this.gameState ? (this.gameState.is_check || this.gameState.in_check) : false;
    const currentTurn = this.gameState ? this.gameState.turn : 'w';

    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];

    const renderRanks = this.isFlipped ? [...ranks].reverse() : ranks;
    const renderFiles = this.isFlipped ? [...files].reverse() : files;

    renderRanks.forEach((rank, rIdx) => {
      renderFiles.forEach((file, fIdx) => {
        const squareUci = `${file}${rank}`;
        const actualRow = 8 - parseInt(rank, 10);
        const actualCol = files.indexOf(file);
        const piece = matrix[actualRow][actualCol];

        const isLight = (actualRow + actualCol) % 2 === 0;
        const squareEl = document.createElement('div');
        squareEl.className = `board-square ${isLight ? 'light-square' : 'dark-square'}`;
        squareEl.dataset.square = squareUci;

        // Destaques de último lance
        if (lastFrom === squareUci) {
          squareEl.classList.add('highlight-move-from');
        }
        if (lastTo === squareUci) {
          squareEl.classList.add('highlight-move-to');
        }

        // Destaque de Rei em Xeque
        if (inCheck && piece && piece.toLowerCase() === 'k' && ((piece === 'K' && currentTurn === 'w') || (piece === 'k' && currentTurn === 'b'))) {
          squareEl.classList.add('in-check');
        }

        // Destaque de Seleção
        if (this.selectedSquare === squareUci) {
          squareEl.classList.add('selected-piece');
        }

        // Renderiza Marcadores de Coordenadas Oficiais
        if (fIdx === 0) {
          const rankLabel = document.createElement('span');
          rankLabel.className = 'coord-rank';
          rankLabel.textContent = rank;
          squareEl.appendChild(rankLabel);
        }
        if (rIdx === 7) {
          const fileLabel = document.createElement('span');
          fileLabel.className = 'coord-file';
          fileLabel.textContent = file;
          squareEl.appendChild(fileLabel);
        }

        // Renderiza Peça
        if (piece) {
          const svgName = this.pieceSvgMap[piece];
          if (svgName) {
            const pieceImg = document.createElement('img');
            pieceImg.src = `/assets/pieces/${svgName}.svg`;
            pieceImg.className = 'chess-piece-img';
            pieceImg.alt = piece;
            squareEl.appendChild(pieceImg);
          }
        }

        // Dicas de Movimento Legal
        const isLegal = this.legalMovesForSelected.some(m => m.slice(2, 4) === squareUci);
        if (isLegal) {
          if (piece) {
            const ring = document.createElement('div');
            ring.className = 'legal-capture-ring';
            squareEl.appendChild(ring);
          } else {
            const dot = document.createElement('div');
            dot.className = 'legal-dot-indicator';
            squareEl.appendChild(dot);
          }
        }

        // Clique no Tabuleiro
        squareEl.addEventListener('click', () => this.handleSquareClick(squareUci, piece));

        this.chessGrid.appendChild(squareEl);
      });
    });
  }

  fenToMatrix(fenBoard) {
    const rows = fenBoard.split('/');
    const matrix = [];
    for (const r of rows) {
      const row = [];
      for (const char of r) {
        if (!isNaN(char)) {
          for (let i = 0; i < parseInt(char, 10); i++) row.push('');
        } else {
          row.push(char);
        }
      }
      matrix.push(row);
    }
    return matrix;
  }

  // ============================================================================
  // INTERAÇÃO DO JOGADOR HUMANO (TAP-TO-MOVE)
  // ============================================================================
  handleSquareClick(squareUci, piece) {
    if (!this.gameState || this.gameState.is_game_over || this.isProcessingMove) return;

    // Se estiver em modo Neural vs Bot, o tabuleiro é apenas assistido
    if (this.selectedMode === 'neural_vs_bot') return;

    // Identificar a cor do jogador humano
    const whitePlayer = this.gameState.white_player || this.gameState.player_white || {};
    const isHumanWhite = (whitePlayer.type === 'human');
    const humanColor = isHumanWhite ? 'w' : 'b';

    const isHumanTurn = (this.gameState.turn === humanColor);
    if (!isHumanTurn) return;

    const isOwnPiece = piece && (
      (humanColor === 'w' && piece === piece.toUpperCase()) ||
      (humanColor === 'b' && piece === piece.toLowerCase())
    );

    // Se já havia uma casa selecionada e o clique é em um movimento legal
    if (this.selectedSquare) {
      const matchingMove = this.legalMovesForSelected.find(m => m.slice(2, 4) === squareUci);
      if (matchingMove) {
        this.executeHumanMove(matchingMove);
        this.selectedSquare = null;
        this.legalMovesForSelected = [];
        this.renderBoard();
        return;
      }
    }

    // Se clicou em peça própria, seleciona
    if (isOwnPiece) {
      this.selectedSquare = squareUci;
      this.legalMovesForSelected = (this.gameState.legal_moves || []).filter(m => m.startsWith(squareUci));
      this.renderBoard();
    } else {
      this.selectedSquare = null;
      this.legalMovesForSelected = [];
      this.renderBoard();
    }
  }

  async executeHumanMove(moveUci) {
    this.isProcessingMove = true;
    try {
      const res = await fetch('/api/match/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uci: moveUci })
      });
      const data = await res.json();
      if (data.success || data.status === 'success') {
        const soundKey = data.sound || (data.state && data.state.last_move && data.state.last_move.sound) || 'move-self';
        this.audio.play(soundKey);
        this.gameState = data.state;
        this.renderBoard();
        this.updateHUD();

        if (this.gameState.is_game_over) {
          this.handleGameOver();
        } else {
          // Vez do bot responder
          setTimeout(() => this.triggerBotStep(), 400);
        }
      } else {
        this.audio.play('illegal');
      }
    } catch (err) {
      console.error("Erro ao executar lance humano:", err);
    } finally {
      this.isProcessingMove = false;
    }
  }

  async triggerBotStep() {
    const session = this.matchSessionId;
    if (!this.gameState || this.gameState.is_game_over || this.isProcessingMove) return;
    this.isProcessingMove = true;

    try {
      const res = await fetch('/api/match/step', { method: 'POST' });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      if (this.matchSessionId !== session) return;

      if (data.success || data.status === 'success') {
        const soundKey = data.sound || (data.state && data.state.last_move && data.state.last_move.sound) || 'move-opponent';
        this.audio.play(soundKey);
        this.gameState = data.state;
        this.renderBoard();
        this.updateHUD();

        if (this.gameState.current_speech && this.gameState.current_speech.text) {
          this.showBotSpeech(this.gameState.current_speech.text);
        }

        if (this.gameState.is_game_over) {
          this.handleGameOver();
        }
      }
    } catch (err) {
      console.error("Erro no lance do bot:", err);
    } finally {
      if (this.matchSessionId === session) {
        this.isProcessingMove = false;
      }
    }
  }

  // ============================================================================
  // DUELO NEURAL AO VIVO (AUTOMATIZADO E FLUIDO ATÉ O FIM)
  // ============================================================================
  startAutoPlay() {
    this.stopAutoPlay();
    if (!this.gameState || this.gameState.is_game_over) return;
    this.scheduleNextDuelStep(150);
  }

  scheduleNextDuelStep(delay = null) {
    this.stopAutoPlay();
    const session = this.matchSessionId;
    if (!this.gameState || this.gameState.is_game_over) return;
    if (this.selectedMode !== 'neural_vs_bot') return;

    const waitTime = (delay !== null) ? delay : this.duelSpeed;
    this.autoPlayTimeout = setTimeout(async () => {
      if (this.matchSessionId !== session) return;
      if (!this.gameState || this.gameState.is_game_over) return;
      await this.triggerBotStep();
      if (this.matchSessionId === session && this.selectedMode === 'neural_vs_bot' && this.gameState && !this.gameState.is_game_over) {
        this.scheduleNextDuelStep();
      }
    }, waitTime);
  }

  stopAutoPlay() {
    if (this.autoPlayTimeout) {
      clearTimeout(this.autoPlayTimeout);
      this.autoPlayTimeout = null;
    }
    if (this.autoPlayInterval) {
      clearInterval(this.autoPlayInterval);
      this.autoPlayInterval = null;
    }
  }

  restartAutoPlay() {
    if (this.selectedMode === 'neural_vs_bot' && this.gameState && !this.gameState.is_game_over) {
      this.scheduleNextDuelStep(100);
    }
  }

  // ============================================================================
  // ATUALIZAÇÃO DO HUD E TELEMETRIA
  // ============================================================================
  updateHUD() {
    if (!this.gameState) return;
    const state = this.gameState;

    // Anel de turno ativo
    if (state.turn === 'w') {
      this.meTurnRing.classList.add('active');
      this.oppTurnRing.classList.remove('active');
      this.turnStatusBadge.textContent = "Vez das Brancas";
    } else {
      this.meTurnRing.classList.remove('active');
      this.oppTurnRing.classList.add('active');
      this.turnStatusBadge.textContent = "Vez das Pretas";
    }

    if (state.is_check || state.in_check) {
      this.turnStatusBadge.textContent = "XEQUE!";
    }

    // Peças Capturadas
    this.renderCaptured(this.meCapturedTray, state.captured_by_white, 'b');
    this.renderCaptured(this.oppCapturedTray, state.captured_by_black, 'w');

    // Vantagem Material
    const materialDiff = state.material_diff !== undefined ? state.material_diff : 0.0;
    if (materialDiff > 0) {
      this.meLeadPill.textContent = `+${Math.round(materialDiff * 100)}`;
      this.oppLeadPill.textContent = '';
    } else if (materialDiff < 0) {
      this.oppLeadPill.textContent = `+${Math.round(Math.abs(materialDiff) * 100)}`;
      this.meLeadPill.textContent = '';
    } else {
      this.meLeadPill.textContent = '';
      this.oppLeadPill.textContent = '';
    }

    // Barra de Avaliação Vertical
    const evalScore = state.eval_score !== undefined ? state.eval_score : (state.eval || 0.0);
    let evalPercent = 50 + (evalScore / 6.0) * 50;
    evalPercent = Math.max(4, Math.min(96, evalPercent));
    this.mobileEvalFill.style.height = `${evalPercent}%`;
    this.mobileEvalNumber.textContent = (evalScore > 0 ? `+${evalScore.toFixed(1)}` : evalScore.toFixed(1));

    // Telemetria Mobile
    let lastMoveStr = '--';
    if (state.last_move) {
      if (typeof state.last_move === 'string') lastMoveStr = state.last_move;
      else if (state.last_move.san) lastMoveStr = state.last_move.san;
      else if (state.last_move.from && state.last_move.to) lastMoveStr = `${state.last_move.from}${state.last_move.to}`;
    }

    this.telBestMove.textContent = lastMoveStr;
    this.telEvalScore.textContent = (evalScore >= 0 ? `+${evalScore.toFixed(2)}` : evalScore.toFixed(2));
    this.telConfidence.textContent = `${Math.min(100, Math.max(65, Math.round(75 + Math.abs(evalScore) * 6)))}%`;
    this.telModeDisplay.textContent = this.mctsActive ? `MCTS ${this.selectedSims}` : 'FAST NET';
  }

  renderCaptured(container, piecesList, colorPrefix) {
    container.innerHTML = '';
    if (!piecesList || piecesList.length === 0) return;
    piecesList.forEach(p => {
      const img = document.createElement('img');
      const svgCode = (typeof p === 'string' && p.length === 2) ? p.toLowerCase() : `${colorPrefix}${String(p).slice(-1).toLowerCase()}`;
      img.src = `/assets/pieces/${svgCode}.svg`;
      img.className = 'captured-icon';
      container.appendChild(img);
    });
  }

  showBotSpeech(text) {
    if (!text) return;
    this.speechText.textContent = text;
    this.botSpeechBubble.style.display = 'block';

    if (this.speechTimeout) clearTimeout(this.speechTimeout);
    this.speechTimeout = setTimeout(() => {
      this.botSpeechBubble.style.display = 'none';
    }, 4500);
  }

  handleGameOver() {
    this.stopAutoPlay();
    const result = this.gameState.result;
    const whitePlayer = this.gameState.white_player || {};
    const blackPlayer = this.gameState.black_player || {};
    let title = "Fim de Partida";
    let desc = this.gameState.result_desc || "Empate!";
    let trophy = "🤝";

    if (result === '1-0') {
      const isMeWinner = (whitePlayer.type === 'human' || (whitePlayer.type === 'neural' && this.selectedMode === 'neural_vs_bot'));
      title = isMeWinner ? "Vitória!" : `Vitória das Brancas (${whitePlayer.name || 'Brancas'})`;
      desc = `Vitória de ${whitePlayer.name || 'Brancas'}`;
      trophy = "🏆";
      this.audio.play(isMeWinner ? 'game-win' : 'game-lose');
    } else if (result === '0-1') {
      const isMeWinner = (blackPlayer.type === 'human' || (blackPlayer.type === 'neural' && this.selectedMode === 'neural_vs_bot'));
      title = isMeWinner ? "Vitória!" : `Vitória das Pretas (${blackPlayer.name || 'Pretas'})`;
      desc = `Vitória de ${blackPlayer.name || 'Pretas'}`;
      trophy = "🏆";
      this.audio.play(isMeWinner ? 'game-win' : 'game-lose');
    } else {
      title = "Empate";
      this.audio.play('game-draw');
    }

    this.gameOverTrophy.textContent = trophy;
    this.gameOverTitle.textContent = title;
    this.gameOverDesc.textContent = desc;
    this.gameOverModal.classList.remove('hidden');
  }

  // ============================================================================
  // AÇÕES AUXILIARES DA BARRA INFERIOR
  // ============================================================================
  async requestHint() {
    try {
      const res = await fetch('/api/match/hint');
      const data = await res.json();
      if (data.hint) {
        const uci = typeof data.hint === 'string' ? data.hint : (data.hint.uci || '');
        const from = data.hint.from || uci.slice(0, 2);
        const to = data.hint.to || uci.slice(2, 4);
        const san = data.hint.san || uci;
        const fromEl = document.querySelector(`[data-square="${from}"]`);
        const toEl = document.querySelector(`[data-square="${to}"]`);
        if (fromEl) fromEl.classList.add('selected-piece');
        if (toEl) toEl.classList.add('highlight-move-to');
        this.showBotSpeech(`💡 Dica Tática: lance recomendado ${san}`);
      }
    } catch (err) {
      console.warn("Erro ao buscar dica:", err);
    }
  }

  async undoMove() {
    try {
      const res = await fetch('/api/match/undo', { method: 'POST' });
      const data = await res.json();
      if (data.success || data.status === 'success') {
        this.gameState = data.state;
        this.renderBoard();
        this.updateHUD();
      }
    } catch (err) {
      console.warn("Erro ao desfazer lance:", err);
    }
  }

  async toggleMcts() {
    this.mctsActive = !this.mctsActive;
    try {
      await fetch('/api/match/mcts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_mcts: this.mctsActive, sims: this.selectedSims })
      });
      this.btnToggleMcts.classList.toggle('active-mcts', this.mctsActive);
      this.mctsBtnLabel.textContent = this.mctsActive ? 'MCTS ON' : 'MCTS OFF';
      this.updateHUD();
    } catch (err) {
      console.warn("Erro ao alternar MCTS:", err);
    }
  }

  confirmResign() {
    if (confirm("Deseja abandonar a partida ou retornar aos Bots?")) {
      this.stopAutoPlay();
      this.showCatalogScreen();
    }
  }
}

// Inicializa a aplicação ao carregar a página
window.addEventListener('DOMContentLoaded', () => {
  window.gymArena = new GymArenaApp();
});
