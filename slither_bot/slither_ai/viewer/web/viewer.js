/**
 * Slither AI - Visualizador Web do Espectador em HTML5 Canvas (60 FPS)
 */

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// Elementos da UI / HUD
const elSnakeName = document.getElementById('snakeName');
const elLength = document.getElementById('statLength');
const elKills = document.getElementById('statKills');
const elSpeed = document.getElementById('statSpeed');
const elBoost = document.getElementById('statBoost');
const elFps = document.getElementById('fpsCounter');
const elSnakesCount = document.getElementById('snakesCount');
const elFoodsCount = document.getElementById('foodsCount');
const elWsStatus = document.getElementById('wsStatus');
const elModelLabel = document.getElementById('modelLabel');

const btnToggleLidar = document.getElementById('btnToggleLidar');
const elLidarStatus = document.getElementById('lidarStatus');
const btnToggleCam = document.getElementById('btnToggleCam');
const elCamStatus = document.getElementById('camStatus');
const btnResetGame = document.getElementById('btnResetGame');

// Configurações da Câmera
let camera = {
    x: 0,
    y: 0,
    zoom: 1.0,
    followBot: true,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0
};

// Estados
let showLidar = true;
let gameState = null;
let lastFrameTime = performance.now();
let frameCount = 0;
let fpsTimer = performance.now();

// Redimensionamento do Canvas
function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// Controles de Câmera (Zoom e Drag)
window.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    camera.zoom = Math.max(0.2, Math.min(2.5, camera.zoom * zoomFactor));
}, { passive: false });

canvas.addEventListener('mousedown', (e) => {
    camera.isDragging = true;
    camera.dragStartX = e.clientX;
    camera.dragStartY = e.clientY;
});

window.addEventListener('mousemove', (e) => {
    if (camera.isDragging) {
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
});

// Eventos dos Botões da HUD
btnToggleLidar.addEventListener('click', () => {
    showLidar = !showLidar;
    elLidarStatus.textContent = showLidar ? "LIGADA" : "DESLIGADA";
    btnToggleLidar.classList.toggle('btn-active', showLidar);
});

btnToggleCam.addEventListener('click', () => {
    camera.followBot = !camera.followBot;
    elCamStatus.textContent = camera.followBot ? "SEGUIR BOT" : "LIVRE";
    btnToggleCam.classList.toggle('btn-active', camera.followBot);
});

btnResetGame.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ cmd: "reset" }));
    }
});

// Conexão WebSocket com o Servidor Python
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
            console.error("Erro ao decodificar dados do jogo:", err);
        }
    };

    ws.onclose = () => {
        elWsStatus.textContent = "Desconectado";
        elWsStatus.className = "";
        setTimeout(connectWebSocket, 1500); // Reconexão automática
    };

    ws.onerror = () => {
        ws.close();
    };
}

// Atualização dos Indicadores de Telemetria
function updateUI(state) {
    if (!state) return;

    if (state.model_name) {
        elModelLabel.textContent = `Modelo: ${state.model_name}`;
    }

    if (state.snakes_count !== undefined) {
        elSnakesCount.textContent = state.snakes_count;
    }
    if (state.foods_count !== undefined) {
        elFoodsCount.textContent = state.foods_count;
    }

    const player = state.player_snake;
    if (player) {
        elSnakeName.textContent = player.name || "NeuraBot_AI";
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
}

// Renderização Gráfica em Canvas (60 FPS)
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

    // Limpa tela
    ctx.fillStyle = '#0a0d14';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!gameState) {
        ctx.fillStyle = '#9ca3af';
        ctx.font = '16px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText("Aguardando transmissão da Arena...", canvas.width / 2, canvas.height / 2);
        return;
    }

    const player = gameState.player_snake;

    // Atualiza posição da câmera suavemente
    if (camera.followBot && player && player.is_alive) {
        camera.x += (player.x - camera.x) * 0.1;
        camera.y += (player.y - camera.y) * 0.1;
    }

    ctx.save();
    // Aplica matriz de transformação da câmera
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.scale(camera.zoom, camera.zoom);
    ctx.translate(-camera.x, -camera.y);

    // 1. Desenha Grade da Arena e Borda Circular
    drawArenaBoundary(gameState.arena_radius || 2500);

    // 2. Desenha Comidas (Orbs Brilhantes)
    if (gameState.foods) {
        drawFoods(gameState.foods);
    }

    // 3. Desenha Cobras Bots Inimigas
    if (gameState.other_snakes) {
        for (const snake of gameState.other_snakes) {
            drawSnake(snake, false);
        }
    }

    // 4. Desenha Cobra Principal do Bot Neural
    if (player && player.is_alive) {
        drawSnake(player, true);

        // 5. Desenha Feixes de Laser LIDAR (Visão Neural)
        if (showLidar && gameState.lidar_readings) {
            drawLidarRays(player, gameState.lidar_readings);
        }
    }

    ctx.restore();
}

// Desenha a Borda Circular da Arena
function drawArenaBoundary(radius) {
    // Grade de fundo suave
    const gridSize = 100;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
    ctx.lineWidth = 1;

    const minX = -radius;
    const maxX = radius;
    const minY = -radius;
    const maxY = radius;

    ctx.beginPath();
    for (let x = minX; x <= maxX; x += gridSize) {
        ctx.moveTo(x, minY);
        ctx.lineTo(x, maxY);
    }
    for (let y = minY; y <= maxY; y += gridSize) {
        ctx.moveTo(minX, y);
        ctx.lineTo(maxX, y);
    }
    ctx.stroke();

    // Borda circular com brilho neon
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.6)';
    ctx.lineWidth = 12;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 4;
    ctx.stroke();
}

// Desenha Comidas (Orbs)
function drawFoods(foods) {
    for (const fo of foods) {
        const r = fo.radius || 3.5;
        ctx.beginPath();
        ctx.arc(fo.x, fo.y, r, 0, Math.PI * 2);

        // Cores vibrantes com glow
        if (fo.is_poop) {
            ctx.fillStyle = '#fbbf24'; // Orbs de turbo
            ctx.shadowColor = '#fbbf24';
            ctx.shadowBlur = 6;
        } else {
            ctx.fillStyle = '#10b981'; // Orbs naturais
            ctx.shadowColor = '#10b981';
            ctx.shadowBlur = 4;
        }
        ctx.fill();
        ctx.shadowBlur = 0; // Reseta shadow para performance
    }
}

// Desenha Cobra (Corpo, Cabeça e Olhos)
function drawSnake(snake, isMainPlayer) {
    if (!snake.segments || snake.segments.length === 0) return;

    const baseColor = isMainPlayer ? '#00f0ff' : (snake.color || '#a855f7');
    const headRadius = snake.radius || 14;

    // 1. Desenha Segmentos do Corpo da Cauda para o Pescoço
    for (let i = snake.segments.length - 1; i >= 0; i--) {
        const seg = snake.segments[i];
        ctx.beginPath();
        ctx.arc(seg.x, seg.y, seg.radius || 12, 0, Math.PI * 2);
        
        if (isMainPlayer) {
            // Efeito gradiente/listrado elegante
            ctx.fillStyle = (i % 2 === 0) ? '#00c4d4' : '#0284c7';
        } else {
            ctx.fillStyle = (i % 2 === 0) ? baseColor : '#7e22ce';
        }
        ctx.fill();

        ctx.strokeStyle = 'rgba(0, 0, 0, 0.3)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    }

    // 2. Desenha a Cabeça
    ctx.beginPath();
    ctx.arc(snake.x, snake.y, headRadius, 0, Math.PI * 2);
    ctx.fillStyle = isMainPlayer ? '#38bdf8' : baseColor;
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 3. Olhos Orientados pelo Ângulo
    const ang = snake.angle || 0;
    const eyeDist = headRadius * 0.55;
    const eyeOffset = headRadius * 0.45;

    const eyeLeftX = snake.x + Math.cos(ang) * eyeDist - Math.sin(ang) * eyeOffset;
    const eyeLeftY = snake.y + Math.sin(ang) * eyeDist + Math.cos(ang) * eyeOffset;

    const eyeRightX = snake.x + Math.cos(ang) * eyeDist + Math.sin(ang) * eyeOffset;
    const eyeRightY = snake.y + Math.sin(ang) * eyeDist - Math.cos(ang) * eyeOffset;

    // Esclera branca
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(eyeLeftX, eyeLeftY, headRadius * 0.32, 0, Math.PI * 2);
    ctx.arc(eyeRightX, eyeRightY, headRadius * 0.32, 0, Math.PI * 2);
    ctx.fill();

    // Pupila preta apontando na direção da marcha
    const pupilX1 = eyeLeftX + Math.cos(ang) * 2;
    const pupilY1 = eyeLeftY + Math.sin(ang) * 2;
    const pupilX2 = eyeRightX + Math.cos(ang) * 2;
    const pupilY2 = eyeRightY + Math.sin(ang) * 2;

    ctx.fillStyle = '#000000';
    ctx.beginPath();
    ctx.arc(pupilX1, pupilY1, headRadius * 0.16, 0, Math.PI * 2);
    ctx.arc(pupilX2, pupilY2, headRadius * 0.16, 0, Math.PI * 2);
    ctx.fill();

    // Nome flutuante
    ctx.fillStyle = '#f3f4f6';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(snake.name || "Snake", snake.x, snake.y - headRadius - 8);
}

// Desenha Feixes de Laser LIDAR da Visão Neural
function drawLidarRays(player, lidarReadings) {
    const numRays = lidarReadings.length || 16;
    const headX = player.x;
    const headY = player.y;
    const headAng = player.angle;
    const maxDist = 350;
    const step = (Math.PI * 2) / numRays;

    for (let i = 0; i < numRays; i++) {
        const proximity = lidarReadings[i] || 0; // 0.0 = livre, 1.0 = colisão
        const rayRelAngle = -Math.PI + i * step;
        const rayAbsAngle = headAng + rayRelAngle;

        // Comprimento do feixe
        const rayDist = maxDist * (1.0 - proximity * 0.7);
        const endX = headX + Math.cos(rayAbsAngle) * rayDist;
        const endY = headY + Math.sin(rayAbsAngle) * rayDist;

        // Cor dinâmica baseada no risco
        let strokeColor = 'rgba(0, 240, 255, 0.25)'; // Verde/Ciano seguro
        if (proximity > 0.4 && proximity <= 0.7) {
            strokeColor = 'rgba(245, 158, 11, 0.7)'; // Amarelo cautela
        } else if (proximity > 0.7) {
            strokeColor = 'rgba(239, 68, 68, 0.95)'; // Vermelho perigo
        }

        ctx.beginPath();
        ctx.moveTo(headX, headY);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = proximity > 0.7 ? 2.5 : 1.2;
        ctx.stroke();

        // Ponto de impacto no final do raio se houver proximidade
        if (proximity > 0.2) {
            ctx.beginPath();
            ctx.arc(endX, endY, 3.5, 0, Math.PI * 2);
            ctx.fillStyle = strokeColor;
            ctx.fill();
        }
    }
}

// Inicia conexão e render loop
connectWebSocket();
render();
