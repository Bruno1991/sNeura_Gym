/**
 * Slither AI - Visualizador Web do Espectador em HTML5 Canvas (60 FPS)
 * Renderização gráfica 100% fiel à engine descompilada do Slither.io APK.
 */

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const minimapCanvas = document.getElementById('minimapCanvas');
const minimapCtx = minimapCanvas.getContext('2d');

// Elementos da UI / HUD
const elSnakeName = document.getElementById('snakeName');
const elBrainBadge = document.getElementById('brainBadge');
const elLength = document.getElementById('statLength');
const elKills = document.getElementById('statKills');
const elSpeed = document.getElementById('statSpeed');
const elBoost = document.getElementById('statBoost');
const elFps = document.getElementById('fpsCounter');
const elSnakesCount = document.getElementById('snakesCount');
const elFoodsCount = document.getElementById('foodsCount');
const elWsStatus = document.getElementById('wsStatus');
const elModelLabel = document.getElementById('modelLabel');
const elLeaderboardList = document.getElementById('leaderboardList');

const btnToggleLidar = document.getElementById('btnToggleLidar');
const elLidarStatus = document.getElementById('lidarStatus');
const btnToggleCam = document.getElementById('btnToggleCam');
const elCamStatus = document.getElementById('camStatus');
const btnToggleTheme = document.getElementById('btnToggleTheme');
const elThemeStatus = document.getElementById('themeStatus');
const btnResetGame = document.getElementById('btnResetGame');

const brainButtons = {
    native: document.getElementById('btnBrainNative'),
    imitation: document.getElementById('btnBrainImitation'),
    ppo: document.getElementById('btnBrainPpo'),
    manual: document.getElementById('btnBrainManual'),
};

// Texturas de fundo descompiladas do Slither.io APK
const THEMES = [
    { name: "Hex Clássico", src: "/static/assets/34_bgee_classic.png" },
    { name: "Hex Gelo", src: "/static/assets/46_bg_hexice.png" },
    { name: "Grade Cinza", src: "/static/assets/49_bg_graygrid.png" },
    { name: "Vácuo Escuro", src: null },
];
let currentThemeIdx = 0;
let bgPattern = null;
let bgImage = new Image();

function loadTheme(idx) {
    currentThemeIdx = idx;
    const theme = THEMES[currentThemeIdx];
    elThemeStatus.textContent = theme.name;
    if (theme.src) {
        bgImage = new Image();
        bgImage.src = theme.src;
        bgImage.onload = () => {
            bgPattern = ctx.createPattern(bgImage, 'repeat');
        };
    } else {
        bgPattern = null;
    }
}
loadTheme(0);

// Paleta de cores vibrantes para orbs de comida
const FOOD_COLORS = [
    { core: "#ffffff", edge: "#10b981", glow: "rgba(16, 185, 129, 0.4)" }, // Verde Esmeralda
    { core: "#ffffff", edge: "#06b6d4", glow: "rgba(6, 182, 212, 0.4)" },  // Ciano
    { core: "#ffffff", edge: "#a855f7", glow: "rgba(168, 85, 247, 0.4)" }, // Roxo
    { core: "#ffffff", edge: "#f59e0b", glow: "rgba(245, 158, 11, 0.4)" },  // Âmbar
    { core: "#ffffff", edge: "#ec4899", glow: "rgba(236, 72, 153, 0.4)" }, // Rosa
    { core: "#ffffff", edge: "#ef4444", glow: "rgba(239, 68, 68, 0.4)" },  // Vermelho
];

// Configurações da Câmera
let camera = {
    x: 0,
    y: 0,
    zoom: 0.9,
    followBot: true,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0
};

// Estados do Jogo
let showLidar = true;
let gameState = null;
let currentBrain = "native";
let lastMouseAngle = 0;
let isMouseDown = false;
let frameCount = 0;
let fpsTimer = performance.now();

// Redimensionamento Dinâmico do Canvas
function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// Controles de Câmera (Zoom e Arrastar)
window.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
    camera.zoom = Math.max(0.15, Math.min(2.5, camera.zoom * zoomFactor));
}, { passive: false });

canvas.addEventListener('mousedown', (e) => {
    if (currentBrain === "manual") {
        isMouseDown = true;
        sendManualControl(e);
    } else {
        camera.isDragging = true;
        camera.dragStartX = e.clientX;
        camera.dragStartY = e.clientY;
    }
});

window.addEventListener('mousemove', (e) => {
    if (currentBrain === "manual") {
        sendManualControl(e);
    } else if (camera.isDragging) {
        camera.followBot = false;
        elCamStatus.textContent = "LIVRE";
        btnToggleCam.classList.remove('btn-active');
        const dx = (e.clientX - camera.dragStartX) / camera.zoom;
        const dy = (e.clientY - camera.dragStartY) / camera.zoom;
        camera.x -= dx;
        camera.y -= dy;
        camera.dragStartX = e.clientX;
        camera.dragStartY = e.clientY;
    }
});

window.addEventListener('mouseup', () => {
    camera.isDragging = false;
    isMouseDown = false;
});

function sendManualControl(e) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const dx = e.clientX - centerX;
    const dy = e.clientY - centerY;
    const angle = Math.atan2(dy, dx);
    lastMouseAngle = angle;
    ws.send(JSON.stringify({
        cmd: "mouse_control",
        angle: angle,
        boost: isMouseDown
    }));
}

// Botões da Toolbar Inferior
btnToggleLidar.addEventListener('click', () => {
    showLidar = !showLidar;
    elLidarStatus.textContent = showLidar ? "LIGADO" : "DESLIGADO";
    btnToggleLidar.classList.toggle('btn-active', showLidar);
});

btnToggleCam.addEventListener('click', () => {
    camera.followBot = !camera.followBot;
    elCamStatus.textContent = camera.followBot ? "SEGUIR BOT" : "LIVRE";
    btnToggleCam.classList.toggle('btn-active', camera.followBot);
});

btnToggleTheme.addEventListener('click', () => {
    const nextIdx = (currentThemeIdx + 1) % THEMES.length;
    loadTheme(nextIdx);
});

btnResetGame.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ cmd: "reset" }));
    }
});

// Seletor de Cérebro ao Vivo
Object.keys(brainButtons).forEach(brainKey => {
    const btn = brainButtons[brainKey];
    if (btn) {
        btn.addEventListener('click', () => {
            selectBrain(brainKey);
        });
    }
});

function selectBrain(brainKey) {
    currentBrain = brainKey;
    Object.keys(brainButtons).forEach(k => {
        brainButtons[k].classList.toggle('active', k === brainKey);
    });
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ cmd: "set_brain", brain: brainKey }));
    }
}

// Conexão WebSocket com o Backend Python
let ws = null;

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    elWsStatus.textContent = "Conectando...";
    elWsStatus.className = "";

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        elWsStatus.textContent = "Ao Vivo (60 FPS)";
        elWsStatus.className = "status-online";
    };

    ws.onmessage = (event) => {
        try {
            gameState = JSON.parse(event.data);
            updateUI(gameState);
        } catch (err) {
            console.error("Erro ao decodificar telemetria:", err);
        }
    };

    ws.onclose = () => {
        elWsStatus.textContent = "Desconectado";
        elWsStatus.className = "";
        setTimeout(connectWebSocket, 1500);
    };

    ws.onerror = () => {
        ws.close();
    };
}

// Atualização dos Indicadores de Telemetria
function updateUI(state) {
    if (!state) return;

    if (state.brain_label) {
        elModelLabel.textContent = `Cérebro: ${state.brain_label}`;
    }

    if (state.active_brain && state.active_brain !== currentBrain) {
        currentBrain = state.active_brain;
        Object.keys(brainButtons).forEach(k => {
            brainButtons[k].classList.toggle('active', k === currentBrain);
        });
    }

    // Badge de status
    if (currentBrain === "native") {
        elBrainBadge.textContent = "IA NATIVA DO APK";
        elBrainBadge.className = "badge badge-neural";
    } else if (currentBrain === "imitation") {
        elBrainBadge.textContent = "NEURAL IMITAÇÃO";
        elBrainBadge.className = "badge badge-neural";
    } else if (currentBrain === "ppo") {
        elBrainBadge.textContent = "NEURAL PPO RL";
        elBrainBadge.className = "badge badge-neural";
    } else {
        elBrainBadge.textContent = "CONTROLE MANUAL";
        elBrainBadge.className = "badge";
    }

    if (state.snakes_count !== undefined) {
        elSnakesCount.textContent = state.snakes_count;
    }
    if (state.foods_count !== undefined) {
        elFoodsCount.textContent = state.foods_count;
    }

    const player = state.player_snake;
    if (player) {
        elSnakeName.textContent = player.name || "NeuraBot (IA)";
        elLength.textContent = Math.round(player.score);
        elKills.textContent = player.kills || 0;
        elSpeed.textContent = player.speed ? player.speed.toFixed(1) : "4.3";

        if (player.is_boosting) {
            elBoost.textContent = "TURBO ATIVO";
            elBoost.classList.add('active');
        } else {
            elBoost.textContent = "CRUZEIRO";
            elBoost.classList.remove('active');
        }
    }

    // Atualiza Placar de Líderes
    if (state.leaderboard) {
        updateLeaderboard(state.leaderboard);
    }

    // Atualiza Minimapa
    if (state.minimap_dots && state.arena_radius) {
        drawMinimap(state.minimap_dots, state.arena_radius);
    }
}

function updateLeaderboard(list) {
    elLeaderboardList.innerHTML = "";
    list.forEach(item => {
        const li = document.createElement('li');
        li.className = `leaderboard-item ${item.is_player ? 'player-rank' : ''}`;
        li.innerHTML = `
            <span class="leaderboard-rank">#${item.rank}</span>
            <span class="leaderboard-name">${escapeHtml(item.name)}</span>
            <span class="leaderboard-score">${item.score}</span>
        `;
        elLeaderboardList.appendChild(li);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Renderização Gráfica do Minimapa
function drawMinimap(dots, arenaRadius) {
    const w = minimapCanvas.width;
    const h = minimapCanvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const scale = (cx - 8) / arenaRadius;

    minimapCtx.clearRect(0, 0, w, h);

    // Fundo circular do radar
    minimapCtx.beginPath();
    minimapCtx.arc(cx, cy, cx - 2, 0, Math.PI * 2);
    minimapCtx.fillStyle = 'rgba(6, 10, 18, 0.9)';
    minimapCtx.fill();
    minimapCtx.strokeStyle = 'rgba(239, 68, 68, 0.6)';
    minimapCtx.lineWidth = 1.5;
    minimapCtx.stroke();

    // Grade do radar
    minimapCtx.beginPath();
    minimapCtx.arc(cx, cy, (cx - 8) * 0.5, 0, Math.PI * 2);
    minimapCtx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    minimapCtx.lineWidth = 1;
    minimapCtx.stroke();

    // Pontos dos inimigos
    for (const dot of dots) {
        if (!dot.is_player) {
            const px = cx + dot.x * scale;
            const py = cy + dot.y * scale;
            minimapCtx.beginPath();
            minimapCtx.arc(px, py, 2.0, 0, Math.PI * 2);
            minimapCtx.fillStyle = 'rgba(168, 85, 247, 0.7)';
            minimapCtx.fill();
        }
    }

    // Ponto piscante do jogador
    for (const dot of dots) {
        if (dot.is_player) {
            const px = cx + dot.x * scale;
            const py = cy + dot.y * scale;
            const pulse = 3.5 + Math.sin(performance.now() * 0.008) * 1.0;

            minimapCtx.beginPath();
            minimapCtx.arc(px, py, pulse, 0, Math.PI * 2);
            minimapCtx.fillStyle = '#00f0ff';
            minimapCtx.fill();
            minimapCtx.strokeStyle = '#ffffff';
            minimapCtx.lineWidth = 1;
            minimapCtx.stroke();
            break;
        }
    }
}

// Loop Principal de Renderização em HTML5 Canvas (60 FPS)
function render() {
    requestAnimationFrame(render);

    // Mede FPS
    frameCount++;
    const now = performance.now();
    if (now - fpsTimer >= 1000) {
        elFps.textContent = frameCount;
        frameCount = 0;
        fpsTimer = now;
    }

    // Limpa tela com o fundo espacial escuro oficial
    ctx.fillStyle = '#06080d';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!gameState) {
        ctx.fillStyle = '#9ca3af';
        ctx.font = '16px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText("Conectando à Arena do Slither...", canvas.width / 2, canvas.height / 2);
        return;
    }

    const player = gameState.player_snake;

    // Atualização suave da câmera
    if (camera.followBot && player && player.is_alive) {
        camera.x += (player.x - camera.x) * 0.12;
        camera.y += (player.y - camera.y) * 0.12;
    }

    ctx.save();
    // Aplica matriz de transformação da câmera
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.scale(camera.zoom, camera.zoom);
    ctx.translate(-camera.x, -camera.y);

    const arenaRadius = gameState.arena_radius || 2500;

    // 1. Desenha a Textura Hexagonal Descompilada da Arena e Borda Neon
    drawArenaOfficial(arenaRadius);

    // 2. Desenha Orbs de Comida com Glow Pulsante
    if (gameState.foods) {
        drawFoods(gameState.foods, now);
    }

    // 3. Desenha Cobras Bots Inimigas (Skins e Olhos do APK)
    if (gameState.other_snakes) {
        for (const snake of gameState.other_snakes) {
            drawSnake(snake, false, now);
        }
    }

    // 4. Desenha a Cobra Principal da IA
    if (player && player.is_alive) {
        drawSnake(player, true, now);

        // 5. Desenha Feixes de Laser LIDAR Sensorial
        if (showLidar && gameState.lidar_readings) {
            drawLidarRays(player, gameState.lidar_readings, arenaRadius);
        }
    }

    ctx.restore();
}

// 1. Renderiza a Arena com a Textura Hexagonal do Slither.io APK
function drawArenaOfficial(radius) {
    ctx.save();

    // Recorta exatamente o círculo da arena (fora dele fica o vácuo escuro infinito)
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.clip();

    if (bgPattern) {
        ctx.fillStyle = bgPattern;
        ctx.fillRect(-radius, -radius, radius * 2, radius * 2);
    } else {
        // Fallback para grade geométrica suave
        ctx.fillStyle = '#0f141f';
        ctx.fillRect(-radius, -radius, radius * 2, radius * 2);
        const gridSize = 80;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let x = -radius; x <= radius; x += gridSize) {
            ctx.moveTo(x, -radius);
            ctx.lineTo(x, radius);
        }
        for (let y = -radius; y <= radius; y += gridSize) {
            ctx.moveTo(-radius, y);
            ctx.lineTo(radius, y);
        }
        ctx.stroke();
    }

    ctx.restore();

    // Borda Neon de Perigo Circular do Slither.io
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.lineWidth = 16;
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.35)';
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.lineWidth = 4;
    ctx.strokeStyle = '#ef4444';
    ctx.stroke();
}

// 2. Renderiza Orbs de Comida com Glow Pulsante e Núcleo Iluminado
function drawFoods(foods, timeMs) {
    for (const fo of foods) {
        const baseRadius = fo.radius || 3.5;
        // Pulso suave
        const pulse = 1.0 + 0.12 * Math.sin(timeMs * 0.006 + fo.id * 1.3);
        const r = baseRadius * pulse;

        const colorScheme = fo.is_poop
            ? { core: "#ffffff", edge: "#fbbf24", glow: "rgba(251, 191, 36, 0.6)" } // Orbs de turbo
            : FOOD_COLORS[fo.id % FOOD_COLORS.length];

        ctx.beginPath();
        ctx.arc(fo.x, fo.y, r, 0, Math.PI * 2);

        // Gradiente radial com centro brilhante
        const grad = ctx.createRadialGradient(fo.x, fo.y, r * 0.2, fo.x, fo.y, r);
        grad.addColorStop(0, colorScheme.core);
        grad.addColorStop(0.6, colorScheme.edge);
        grad.addColorStop(1, colorScheme.glow);

        ctx.fillStyle = grad;
        ctx.fill();
    }
}

// 3. Renderiza a Cobra (Segmentos, Cabeça, Olhos Cartoon e Pupilas)
function drawSnake(snake, isMainPlayer, timeMs) {
    if (!snake.segments || snake.segments.length === 0) return;

    const skin = snake.skin || {
        head: isMainPlayer ? "#00f0ff" : "#a855f7",
        body: isMainPlayer ? ["#0ea5e9", "#00f0ff"] : ["#9333ea", "#c084fc"],
        border: "#000000"
    };

    const isBoosting = snake.is_boosting;
    const boostSwell = isBoosting ? 1.1 : 1.0;

    // A) Desenha os Segmentos do Corpo da Cauda para a Cabeça
    const segs = snake.segments;
    const bodyColors = skin.body;

    for (let i = segs.length - 1; i >= 0; i--) {
        const seg = segs[i];
        const segRadius = (seg.radius || 8.0) * boostSwell;
        const color = bodyColors[i % bodyColors.length];

        ctx.beginPath();
        ctx.arc(seg.x, seg.y, segRadius, 0, Math.PI * 2);

        // Preenchimento com borda para dar aspecto volumétrico 3D
        ctx.fillStyle = color;
        ctx.fill();

        ctx.lineWidth = 1.5;
        ctx.strokeStyle = skin.border || 'rgba(0, 0, 0, 0.35)';
        ctx.stroke();
    }

    // B) Desenha a Cabeça com Aura e Olhos Grandes
    const headRadius = (snake.radius || 9.0) * boostSwell;
    const headAngle = snake.angle || 0.0;
    const targetAngle = snake.target_angle !== undefined ? snake.target_angle : headAngle;

    // Efeito de Glow quando a cobra está em Turbo (Boost)
    if (isBoosting) {
        ctx.beginPath();
        ctx.arc(snake.x, snake.y, headRadius * 1.5, 0, Math.PI * 2);
        ctx.fillStyle = isMainPlayer ? 'rgba(0, 240, 255, 0.25)' : 'rgba(251, 191, 36, 0.25)';
        ctx.fill();
    }

    // Círculo principal da cabeça
    ctx.beginPath();
    ctx.arc(snake.x, snake.y, headRadius, 0, Math.PI * 2);
    ctx.fillStyle = skin.head;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = skin.border || '#000000';
    ctx.stroke();

    // C) Olhos Cartoon do Slither.io (Dois Olhos Brancos com Pupilas Pretas Móveis)
    const eyeOffsetDist = headRadius * 0.65;
    const eyeSpreadAngle = 0.65; // ~37 graus de cada lado
    const eyeRadius = headRadius * 0.36;
    const pupilRadius = eyeRadius * 0.55;

    // Olho Esquerdo e Direito
    const eyes = [
        { angle: headAngle - eyeSpreadAngle },
        { angle: headAngle + eyeSpreadAngle },
    ];

    for (const eye of eyes) {
        const eyeX = snake.x + Math.cos(eye.angle) * eyeOffsetDist;
        const eyeY = snake.y + Math.sin(eye.angle) * eyeOffsetDist;

        // Globo ocular branco com contorno fino
        ctx.beginPath();
        ctx.arc(eyeX, eyeY, eyeRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.lineWidth = 1;
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.6)';
        ctx.stroke();

        // Pupila preta olhando na direção para onde a cobra quer virar
        const pupilShift = eyeRadius * 0.42;
        const pupilX = eyeX + Math.cos(targetAngle) * pupilShift;
        const pupilY = eyeY + Math.sin(targetAngle) * pupilShift;

        ctx.beginPath();
        ctx.arc(pupilX, pupilY, pupilRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#111827';
        ctx.fill();

        // Ponto de brilho/reflexo na pupila
        ctx.beginPath();
        ctx.arc(pupilX - pupilRadius * 0.3, pupilY - pupilRadius * 0.3, pupilRadius * 0.32, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
    }

    // Nome da Cobra sobre a Cabeça
    if (snake.name) {
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = isMainPlayer ? '#00f0ff' : 'rgba(255, 255, 255, 0.85)';
        ctx.shadowColor = '#000000';
        ctx.shadowBlur = 4;
        ctx.fillText(snake.name, snake.x, snake.y - headRadius - 8);
        ctx.shadowBlur = 0;
    }
}

// 4. Desenha Feixes de Laser LIDAR da Visão Sensorial (360 Graus)
function drawLidarRays(player, readings, arenaRadius) {
    const numRays = readings.length;
    const maxDist = 380.0;
    const step = (Math.PI * 2) / numRays;

    for (let i = 0; i < numRays; i++) {
        const val = readings[i]; // 0.0 = colisão imediata, 1.0 = caminho totalmente limpo
        const relAngle = -Math.PI + i * step;
        const absAngle = player.angle + relAngle;
        const rayLen = val * maxDist;

        const targetX = player.x + Math.cos(absAngle) * rayLen;
        const targetY = player.y + Math.sin(absAngle) * rayLen;

        ctx.beginPath();
        ctx.moveTo(player.x, player.y);
        ctx.lineTo(targetX, targetY);

        if (val < 0.98) {
            // Obstáculo detectado: Raio vermelho/laranja com faísca de impacto
            ctx.strokeStyle = val < 0.4 ? 'rgba(239, 68, 68, 0.85)' : 'rgba(245, 158, 11, 0.65)';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Ponto de impacto brilhante
            ctx.beginPath();
            ctx.arc(targetX, targetY, 3.0, 0, Math.PI * 2);
            ctx.fillStyle = val < 0.4 ? '#ef4444' : '#f59e0b';
            ctx.fill();
        } else {
            // Espaço livre: Feixe verde suave
            ctx.strokeStyle = 'rgba(16, 185, 129, 0.22)';
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }
}

// Inicia conexão e loop de renderização
connectWebSocket();
requestAnimationFrame(render);
