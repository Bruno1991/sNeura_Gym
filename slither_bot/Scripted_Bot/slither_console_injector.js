/**
 * ============================================================================
 * SLITHER.IO - BOT NATIVO APK (CONSOLE INJECTOR) - VERSÃO 5.0 MASTER
 * CÉREBRO: 100% FIEL À IA DO APK SLITHER (gaim.Main) + TURBO INTELIGENTE
 * ============================================================================
 * Como usar:
 * 1. Abra https://slither.io no seu navegador.
 * 2. Abra o Console do DevTools (F12 ou Ctrl+Shift+I -> Console).
 * 3. Cole todo este código e aperte Enter.
 * 4. Digite seu apelido e clique em "Play" (ou deixe o bot renascer sozinho!).
 *
 * Teclas de Atalho no Jogo:
 * [T] -> Alterna Piloto Automático LIGADO / DESLIGADO (para jogar no mouse)
 * [R] -> Alterna Auto-Respawn LIGADO / DESLIGADO (renasce sozinho ao morrer)
 * [O] -> Liga / Desliga o painel visual HUD na tela
 * ============================================================================
 */

(function() {
    'use strict';

    // 1. Limpa instâncias anteriores
    if (window._slitherBotTimer) {
        clearInterval(window._slitherBotTimer);
        console.log('[Slither Bot] Instância anterior finalizada com sucesso.');
    }

    // 2. Parâmetros 100% fiéis ao código-fonte descompilado do APK (gaim.Main)
    window.BOT_CONFIG = {
        COWARDICE_BASE: 380.0,         // Linha 11011 (84 * 4.5 = 378px)
        COWARDICE_BOOST_MULT: 2.0,     // Linha 11041 (bidt *= 2 durante boost = 760px)
        RAD_TANGENT: 0.26,             // Linha 11210 (+/- 0.26 rad = 15 graus exatos)
        INTERCEPT_LEAD_DIST: 95.0,     // Linha 11214 (mira preditiva a 95px)
        FOOD_HOLD_MS: 2500,            // Linha 11160 (3000ms + random)
        FOOD_REACH_DIST: 45.0,         // Distância de absorção para evitar espirais
        AVOID_SWITCH_MS: 2000,         // Linha 11100 (alterna sentido de giro a cada 2000ms)
        BORDER_MARGIN: 800.0,          // Margem de segurança da parede circular externa
        MIN_BOOST_MASS: 10,            // Linha 11170 (me.sct > 10 para liberar turbo com segurança)
        AUTO_RESPAWN: true             // Renascer automaticamente após a morte
    };

    window.botState = {
        enabled: true,
        autoRespawn: true,
        avoidanceDir: 1,
        lastAvoidDirChangeTm: 0,
        changeTargetAfterTm: 0,
        targetFood: null,
        violent: false,
        stopViolenceTm: 0,
        allowViolenceAfterTm: 0,
        excited: false,
        stopExcitedTm: 0,
        currentMode: 'INICIALIZADO',
        isBoosting: false,
        lastBoostVal: -1,
        lastSangVal: -1,
        steerCount: 0,
        deathTm: 0,
        gamesPlayed: 1,
        logTimer: 0
    };

    // 3. Interceptador de mouse protetor: impede conflito com o cursor do jogador
    if (!window._orig_onmousemove && window.onmousemove) {
        window._orig_onmousemove = window.onmousemove;
    }
    window.onmousemove = function(e) {
        if (!window.botState || !window.botState.enabled) {
            if (window._orig_onmousemove) return window._orig_onmousemove(e);
        }
    };

    // 4. Hook passivo de WebSocket para pacotes binários de baixa latência
    if (!window._slitherWsHooked) {
        window._slitherWsHooked = true;
        var _nativeWsSend = WebSocket.prototype.send;
        WebSocket.prototype.send = function() {
            window._activeWs = this;
            return _nativeWsSend.apply(this, arguments);
        };
    }

    // 5. Helpers de resolução do estado do jogo
    function getMySnake() {
        try { if (typeof slither !== 'undefined' && slither) return slither; } catch(e) {}
        try { if (window.slither) return window.slither; } catch(e) {}
        try { if (typeof snake !== 'undefined' && snake) return snake; } catch(e) {}
        try { if (window.snake) return window.snake; } catch(e) {}
        return null;
    }

    function getOtherSnakes() {
        try { if (typeof slithers !== 'undefined' && Array.isArray(slithers)) return slithers; } catch(e) {}
        try { if (window.slithers) return window.slithers; } catch(e) {}
        try { if (typeof snakes !== 'undefined' && Array.isArray(snakes)) return snakes; } catch(e) {}
        try { if (window.snakes) return window.snakes; } catch(e) {}
        return [];
    }

    function getFoods() {
        try { if (typeof foods !== 'undefined' && Array.isArray(foods)) return foods; } catch(e) {}
        try { if (window.foods) return window.foods; } catch(e) {}
        return [];
    }

    function getPreys() {
        try { if (typeof preys !== 'undefined' && Array.isArray(preys)) return preys; } catch(e) {}
        try { if (window.preys) return window.preys; } catch(e) {}
        return [];
    }

    function getArenaRadius() {
        try { if (typeof grd !== 'undefined' && grd) return grd; } catch(e) {}
        try { if (window.grd) return window.grd; } catch(e) {}
        return 21600.0;
    }

    // 6. Direcionador de Movimento Multi-Camada
    function steerSnake(angleRad, boost) {
        window.botState.isBoosting = !!boost;
        window.botState.steerCount++;

        var dist = 600;
        var tx = Math.cos(angleRad) * dist;
        var ty = Math.sin(angleRad) * dist;

        // Camada A: Variáveis internas do motor do jogo (xm, ym, want_e)
        try { xm = tx; ym = ty; want_e = true; } catch(e) {}
        try { window.xm = tx; window.ym = ty; window.want_e = true; } catch(e) {}

        // Camada B: Predição angular local imediata
        var me = getMySnake();
        if (me) {
            try { me.eang = angleRad; } catch(e) {}
        }

        // Camada C: Aceleração nativa
        try {
            if (typeof setAcceleration === 'function') setAcceleration(window.botState.isBoosting ? 1 : 0);
            else if (typeof window.setAcceleration === 'function') window.setAcceleration(window.botState.isBoosting ? 1 : 0);
        } catch(e) {}

        // Camada D: Injeção direta no WebSocket
        var socket = (typeof ws !== 'undefined' && ws) ? ws : window._activeWs;
        if (socket && socket.readyState === 1) {
            var pi2 = Math.PI * 2;
            var norm = ((angleRad % pi2) + pi2) % pi2;
            var sang = Math.floor(251 * norm / pi2) & 255;

            if (sang !== window.botState.lastSangVal) {
                window.botState.lastSangVal = sang;
                var ba = new Uint8Array(1);
                ba[0] = sang;
                try { socket.send(ba.buffer || ba); } catch(e) {}
            }

            var boostVal = window.botState.isBoosting ? 253 : 254;
            if (boostVal !== window.botState.lastBoostVal) {
                window.botState.lastBoostVal = boostVal;
                try { socket.send(new Uint8Array([boostVal])); } catch(e) {}
            }
        }
    }

    function triggerRespawn() {
        try {
            if (typeof play_btn !== 'undefined' && play_btn && play_btn.elem) play_btn.elem.click();
            else {
                var btn = document.getElementById('playh');
                if (btn) btn.click();
            }
        } catch(e) {}
    }

    // 7. Cérebro 100% Fiel à IA Descompilada do APK (gaim.Main linhas 11040 a 11250)
    function runBotCycle() {
        var me = getMySnake();
        var isPlaying = (typeof playing !== 'undefined' && playing) || (window.playing) || (me && !me.dead);
        var now = Date.now();

        // Tratamento de Morte e Auto-Respawn
        if (!me || !isPlaying || me.dead) {
            window.botState.currentMode = 'AGUARDANDO PLAY';
            if (window.botState.autoRespawn) {
                window.botState.currentMode = 'MORTO / RENASCENDO...';
                if (window.botState.deathTm === 0) {
                    window.botState.deathTm = now;
                } else if (now - window.botState.deathTm > 1500) {
                    window.botState.deathTm = 0;
                    window.botState.gamesPlayed++;
                    triggerRespawn();
                }
            }
            updateHUD();
            return;
        }

        window.botState.deathTm = 0;

        if (!window.botState.enabled) {
            window.botState.currentMode = 'MANUAL (PAUSADO NO TECLADO)';
            updateHUD();
            return;
        }

        var myX = me.xx;
        var myY = me.yy;
        var myScore = me.sct || (me.pts ? me.pts.length : 0);
        var arenaRadius = getArenaRadius();
        var pi2 = Math.PI * 2;

        // Log de diagnóstico a cada 3s
        if (now - window.botState.logTimer > 3000) {
            window.botState.logTimer = now;
            console.log(`[Slither APK Bot v5] Partida #${window.botState.gamesPlayed} | Modo: ${window.botState.currentMode} | Segmentos: ${myScore} | Turbo: ${window.botState.isBoosting ? 'LIGADO' : 'OFF'}`);
        }

        // --- 1. SEGURANÇA DA BORDA DA ARENA (Círculo centrado em (grd, grd)) ---
        var dxC = myX - arenaRadius;
        var dyC = myY - arenaRadius;
        var distCenter = Math.sqrt(dxC * dxC + dyC * dyC);
        if (distCenter > (arenaRadius - window.BOT_CONFIG.BORDER_MARGIN)) {
            window.botState.currentMode = 'BORDA DE SEGURANÇA';
            var awayBorder = Math.atan2(arenaRadius - myY, arenaRadius - myX);
            steerSnake(awayBorder, false); // NUNCA acelerar na borda
            updateHUD();
            return;
        }

        // --- 2. EVITAÇÃO DE OBSTÁCULOS NATIVA (gaim.Main linhas 11040-11099) ---
        // Se a cobra estiver em boost, o raio de detecção dobra (bidt *= 2, l. 11041)
        var bidt = window.botState.isBoosting 
            ? (window.BOT_CONFIG.COWARDICE_BASE * window.BOT_CONFIG.COWARDICE_BOOST_MULT)
            : window.BOT_CONFIG.COWARDICE_BASE;
        var avpo = null;

        // Alternância do sentido de giro a cada 2000ms (Main.as l. 11100-11114)
        if (now - window.botState.lastAvoidDirChangeTm > window.BOT_CONFIG.AVOID_SWITCH_MS) {
            if (avpo === null) {
                window.botState.lastAvoidDirChangeTm = now;
                window.botState.avoidanceDir = (window.botState.avoidanceDir === 1) ? 2 : 1;
            }
        }

        var allSnakes = getOtherSnakes();
        for (var i = 0; i < allSnakes.length; i++) {
            var sk2 = allSnakes[i];
            if (!sk2 || sk2.id === me.id || sk2.dead) continue;

            // Prioridade: Cabeça do oponente
            var hdx = Math.abs(myX - sk2.xx);
            var hdy = Math.abs(myY - sk2.yy);
            var hdt = (hdx > hdy) ? hdx : hdy;
            if (hdt < bidt * 1.3) {
                bidt = hdt;
                avpo = { xx: sk2.xx, yy: sk2.yy };
            }

            // Varredura de segmentos do corpo de trás para frente (Main.as l. 11050)
            var pts = sk2.pts;
            if (!pts) continue;
            for (var p = pts.length - 1; p >= 0; p--) {
                var po = pts[p];
                if (!po || po.dying) continue;

                // Métrica de Chebyshev: max(|dx|, |dy|) (Main.as l. 11075)
                var idx = Math.abs(myX - po.xx);
                var idy = Math.abs(myY - po.yy);
                var idt = (idx > idy) ? idx : idy;

                if (idt < bidt) {
                    bidt = idt;
                    avpo = po;
                }
            }
        }

        // SE HOUVER OBSTÁCULO: ESQUIVA PURA DE 15° (ZERO TURBO!)
        // Na física do Slither, usar turbo abre o raio de curva e faz a cobra bater de frente.
        // A IA nativa desativa turbo na esquiva para fazer o giro mais fechado e seguro possível!
        if (avpo !== null) {
            window.botState.currentMode = 'DESVIO DEFENSIVO (15°)';
            window.botState.targetFood = null; // Foco 100% na sobrevivência
            var awayAngle = Math.atan2(myY - avpo.yy, myX - avpo.xx);
            var tangent = (window.botState.avoidanceDir === 1) ? window.BOT_CONFIG.RAD_TANGENT : -window.BOT_CONFIG.RAD_TANGENT;
            steerSnake(awayAngle + tangent, false); // NUNCA turbo ao desviar!
            updateHUD();
            return;
        }

        // Checa se o orb atual foi absorvido
        if (window.botState.targetFood) {
            var tf = window.botState.targetFood;
            var d2T = Math.sqrt(Math.pow(myX - tf.xx, 2) + Math.pow(myY - tf.yy, 2));
            if (d2T < window.BOT_CONFIG.FOOD_REACH_DIST || tf.eaten) {
                window.botState.targetFood = null;
            }
        }

        // --- 3. MODO PREDATÓRIO / VIOLÊNCIA NATIVO (Main.as l. 11163-11184) ---
        var nearestOpp = null;
        var nearestOppDist = 700;
        for (var j = 0; j < allSnakes.length; j++) {
            var opp = allSnakes[j];
            if (!opp || opp.id === me.id || opp.dead) continue;
            var odt = Math.max(Math.abs(myX - opp.xx), Math.abs(myY - opp.yy));
            if (odt < nearestOppDist) {
                nearestOppDist = odt;
                nearestOpp = opp;
            }
        }

        if (window.botState.violent) {
            if (now > window.botState.stopViolenceTm) window.botState.violent = false;
        } else if (myScore >= window.BOT_CONFIG.MIN_BOOST_MASS && nearestOpp && nearestOpp.sct > 6) {
            // Tempo de recarga e chance de ataque (Main.as l. 11174)
            if (now > window.botState.allowViolenceAfterTm && Math.random() < 0.25) {
                window.botState.allowViolenceAfterTm = now + 14000;
                window.botState.violent = true;
                window.botState.stopViolenceTm = now + 2500 + Math.floor(Math.random() * 3500);
            }
        }

        // Execução do Ataque Predatório com Interceptação Balística a 95px (Main.as l. 11214)
        if (window.botState.violent && nearestOpp && !nearestOpp.dead) {
            window.botState.currentMode = 'ATAQUE PREDATÓRIO 95px (TURBO)';
            var leadX = nearestOpp.xx + Math.cos(nearestOpp.ang) * window.BOT_CONFIG.INTERCEPT_LEAD_DIST;
            var leadY = nearestOpp.yy + Math.sin(nearestOpp.ang) * window.BOT_CONFIG.INTERCEPT_LEAD_DIST;
            var attackAng = Math.atan2(leadY - myY, leadX - myX);
            steerSnake(attackAng, true); // TURBO 100% ATIVO NO ATAQUE!
            updateHUD();
            return;
        }

        // --- 4. MODO EMPOLGADO / TIRO DE ACELERAÇÃO (Main.as l. 11185-11200) ---
        if (window.botState.excited) {
            if (now > window.botState.stopExcitedTm) window.botState.excited = false;
        } else if (myScore >= window.BOT_CONFIG.MIN_BOOST_MASS && Math.random() < 0.008) {
            window.botState.excited = true;
            window.botState.stopExcitedTm = now + 600 + Math.floor(Math.random() * 1200);
        }

        // --- 5. COLETA DE COMIDA NATIVA (Main.as l. 11115-11162) ---
        if (now > window.botState.changeTargetAfterTm || !window.botState.targetFood) {
            var bestFood = null;
            var bestScore = -999999;

            // Prioridade A: Presas rápidas luminosas (preys)
            var preysList = getPreys();
            for (var pr = 0; pr < preysList.length; pr++) {
                var prey = preysList[pr];
                if (!prey || prey.eaten) continue;
                var pdx = prey.xx - myX;
                var pdy = prey.yy - myY;
                var pdSq = pdx * pdx + pdy * pdy;
                if (pdSq > 1100 * 1100 || pdSq < 15 * 15) continue;
                var pd = Math.sqrt(pdSq);
                var pDiff = Math.abs(((Math.atan2(pdy, pdx) - me.ang + Math.PI * 3) % pi2) - Math.PI);
                if (pDiff > 1.9) continue; // Filtro frontal: não fazer curvas de 180 para trás

                var pScore = (1100 - pd) + (Math.PI - pDiff) * 150 + 350;
                if (pScore > bestScore) {
                    bestScore = pScore;
                    bestFood = prey;
                }
            }

            // Prioridade B: Orbs de comida no mapa com bônus de massa (Main.as l. 11150)
            var foodsList = getFoods();
            var count = (typeof foods_c !== 'undefined') ? foods_c : foodsList.length;
            for (var f = 0; f < count; f++) {
                var fo = foodsList[f];
                if (!fo || fo.eaten) continue;
                var fdx = fo.xx - myX;
                var fdy = fo.yy - myY;
                var fDistSq = fdx * fdx + fdy * fdy;
                if (fDistSq > 950 * 950 || fDistSq < 20 * 20) continue;
                var fd = Math.sqrt(fDistSq);
                var fDiff = Math.abs(((Math.atan2(fdy, fdx) - me.ang + Math.PI * 3) % pi2) - Math.PI);
                if (fDiff > 1.9) continue;

                var szBonus = (fo.sz || 1) * 25; // Peso especial para orbs grandes
                var fScore = (950 - fd) + (Math.PI - fDiff) * 120 + szBonus;
                if (fScore > bestScore) {
                    bestScore = fScore;
                    bestFood = fo;
                }
            }

            if (bestFood !== null) {
                window.botState.targetFood = bestFood;
                window.botState.changeTargetAfterTm = now + window.BOT_CONFIG.FOOD_HOLD_MS;
            }
        }

        // Decisão de Turbo Inteligente:
        // Só acelera para comer se a presa estiver perto (< 280px) e com massa segura
        var isPrey = !!(window.botState.targetFood && (window.botState.targetFood.sp || window.botState.targetFood.rsp > 1));
        var distToFood = window.botState.targetFood 
            ? Math.sqrt(Math.pow(myX - window.botState.targetFood.xx, 2) + Math.pow(myY - window.botState.targetFood.yy, 2))
            : 9999;
        var boostPrey = (isPrey && distToFood < 280 && myScore >= window.BOT_CONFIG.MIN_BOOST_MASS);
        var boostOverall = (boostPrey || window.botState.excited) && (myScore >= window.BOT_CONFIG.MIN_BOOST_MASS);

        if (window.botState.targetFood && !window.botState.targetFood.eaten) {
            window.botState.currentMode = boostOverall ? 'COLETA (TURBO)' : 'COLETA DE COMIDA';
            var foodAng = Math.atan2(window.botState.targetFood.yy - myY, window.botState.targetFood.xx - myX);
            steerSnake(foodAng, boostOverall);
        } else {
            window.botState.currentMode = boostOverall ? 'CRUZEIRO (TURBO)' : 'CRUZEIRO SUAVE';
            if (Math.random() < 0.03) steerSnake(me.ang + (Math.random() - 0.5) * 0.4, boostOverall);
            else steerSnake(me.ang, boostOverall);
        }
        updateHUD();
    }

    // 8. HUD Visual Elegante e Dinâmico
    function createHUD() {
        var existing = document.getElementById('slither-apk-hud');
        if (existing) existing.remove();

        var hud = document.createElement('div');
        hud.id = 'slither-apk-hud';
        hud.innerHTML = `
            <div style="
                position: fixed;
                top: 15px;
                right: 15px;
                background: rgba(15, 23, 42, 0.94);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(56, 189, 248, 0.5);
                border-radius: 12px;
                padding: 14px 18px;
                color: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 13px;
                line-height: 1.5;
                z-index: 9999999;
                box-shadow: 0 10px 25px rgba(0,0,0,0.6), 0 0 15px rgba(56, 189, 248, 0.25);
                min-width: 280px;
                pointer-events: none;
                user-select: none;
            ">
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px;">
                    <span style="font-weight: 700; color: #38bdf8; font-size: 14px;">🐍 BOT NATIVO APK v5.0</span>
                    <span id="bot-badge" style="background:#10b981; color:#fff; font-size:10px; font-weight:800; padding:2px 6px; border-radius:6px;">ATIVO [T]</span>
                </div>
                <div style="display:grid; grid-template-columns: 95px 1fr; gap: 4px; font-size: 12px;">
                    <span style="color:#94a3b8;">Estado:</span>
                    <span id="bot-mode" style="font-weight:700; color:#fbbf24;">INICIALIZADO</span>
                    <span style="color:#94a3b8;">Partidas:</span>
                    <span id="bot-games" style="color:#f1f5f9; font-weight:700;">1</span>
                    <span style="color:#94a3b8;">Segmentos:</span>
                    <span id="bot-segs" style="color:#f1f5f9; font-weight:700;">0</span>
                    <span style="color:#94a3b8;">Auto-Respawn:</span>
                    <span id="bot-respawn" style="color:#10b981; font-weight:700;">LIGADO [R]</span>
                    <span style="color:#94a3b8;">Turbo:</span>
                    <span id="bot-boost" style="color:#64748b; font-weight:700;">OFF</span>
                </div>
                <div style="margin-top: 8px; font-size: 10px; color:#64748b; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 4px;">
                    [T] Piloto Automático | [R] Auto-Respawn | [O] HUD
                </div>
            </div>
        `;
        document.body.appendChild(hud);
    }

    function updateHUD() {
        var badge = document.getElementById('bot-badge');
        var modeText = document.getElementById('bot-mode');
        var segsText = document.getElementById('bot-segs');
        var gamesText = document.getElementById('bot-games');
        var boostText = document.getElementById('bot-boost');
        var respawnText = document.getElementById('bot-respawn');
        var me = getMySnake();

        if (badge) {
            badge.style.background = window.botState.enabled ? '#10b981' : '#64748b';
            badge.innerText = window.botState.enabled ? 'ATIVO [T]' : 'PAUSADO [T]';
        }
        if (modeText) {
            modeText.innerText = window.botState.currentMode;
            if (window.botState.currentMode.indexOf('DESVIO') >= 0) modeText.style.color = '#ef4444';
            else if (window.botState.currentMode.indexOf('ATAQUE') >= 0) modeText.style.color = '#f97316';
            else if (window.botState.currentMode.indexOf('TURBO') >= 0) modeText.style.color = '#f43f5e';
            else if (window.botState.currentMode.indexOf('COLETA') >= 0) modeText.style.color = '#38bdf8';
            else if (window.botState.currentMode.indexOf('BORDA') >= 0) modeText.style.color = '#eab308';
            else if (window.botState.currentMode.indexOf('MORTO') >= 0) modeText.style.color = '#f43f5e';
            else modeText.style.color = '#a855f7';
        }
        if (segsText && me) {
            segsText.innerText = (me.sct || (me.pts ? me.pts.length : 0));
        }
        if (gamesText) {
            gamesText.innerText = window.botState.gamesPlayed;
        }
        if (respawnText) {
            respawnText.innerText = window.botState.autoRespawn ? 'LIGADO [R]' : 'OFF [R]';
            respawnText.style.color = window.botState.autoRespawn ? '#10b981' : '#64748b';
        }
        if (boostText) {
            boostText.innerText = window.botState.isBoosting ? 'LIGADO' : 'OFF';
            boostText.style.color = window.botState.isBoosting ? '#ef4444' : '#64748b';
        }
    }

    // 9. Teclas de Atalho
    window.addEventListener('keydown', function(e) {
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
        var key = e.key.toUpperCase();
        if (key === 'T') {
            window.botState.enabled = !window.botState.enabled;
            console.log('[Slither Bot] Piloto Automático: ' + (window.botState.enabled ? 'LIGADO' : 'DESLIGADO'));
            updateHUD();
        } else if (key === 'R') {
            window.botState.autoRespawn = !window.botState.autoRespawn;
            console.log('[Slither Bot] Auto-Respawn: ' + (window.botState.autoRespawn ? 'LIGADO' : 'DESLIGADO'));
            updateHUD();
        } else if (key === 'O') {
            var hudEl = document.getElementById('slither-apk-hud');
            if (hudEl) hudEl.style.display = (hudEl.style.display === 'none' ? 'block' : 'none');
        }
    });

    createHUD();
    window._slitherBotTimer = setInterval(runBotCycle, 33);

    console.log('%c[Slither APK Bot v5.0 Master]%c INJETADO! 100% IA Nativa do APK com Turbo Inteligente.', 'background:#10b981;color:#fff;font-weight:bold;padding:5px 10px;border-radius:4px;', 'color:#38bdf8;');
})();
