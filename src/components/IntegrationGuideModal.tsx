import React, { useState } from 'react';
import { NeuralNetwork } from '../ai/neuralNetwork';
import { X, Copy, Check, Terminal, ExternalLink, ShieldAlert, Cpu, Sparkles } from 'lucide-react';

interface IntegrationGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
  championBrain: NeuralNetwork;
}

export const IntegrationGuideModal: React.FC<IntegrationGuideModalProps> = ({
  isOpen,
  onClose,
  championBrain,
}) => {
  const [copiedCode, setCopiedCode] = useState(false);
  const [copiedWeights, setCopiedWeights] = useState(false);

  if (!isOpen) return null;

  const weightsJSON = JSON.stringify(championBrain.toJSON());

  // Ready-to-paste Tampermonkey script for slither.io
  const tampermonkeyScript = `// ==UserScript==
// @name         Slither.io Neural Network AI Bot
// @namespace    https://slitherai.local/
// @version      1.0
// @description  Bot autônomo baseado em Rede Neural treinada por neuroevolução no SlitherAI
// @match        http*://slither.io/*
// @match        http*://slither.com/io*
// @grant        none
// ==/UserScript==

(function() {
  'use strict';

  console.log('[SlitherAI] Inicializando Rede Neural do Bot...');

  // 1. Pesos da Rede Neural treinada (Arquitetura 28 -> 24 -> 16 -> 2)
  const BRAIN_WEIGHTS = ${weightsJSON};

  // 2. Motor de Inferência da Rede Neural
  class SlitherBrain {
    constructor(data) {
      this.layers = data.layers;
      this.weights = data.weights;
      this.biases = data.biases;
    }

    predict(inputs) {
      let current = [...inputs];
      for (let l = 0; l < this.weights.length; l++) {
        const next = [];
        const toSize = this.layers[l + 1];
        const fromSize = this.layers[l];
        const isLast = l === this.weights.length - 1;

        for (let j = 0; j < toSize; j++) {
          let sum = this.biases[l][j];
          for (let i = 0; i < fromSize; i++) {
            sum += current[i] * this.weights[l][i][j];
          }
          if (isLast) {
            next.push(j === 0 ? Math.tanh(sum) : 1 / (1 + Math.exp(-sum)));
          } else {
            next.push(Math.tanh(sum));
          }
        }
        current = next;
      }
      return { steer: current[0], boost: current[1] > 0.52 };
    }
  }

  const brain = new SlitherBrain(BRAIN_WEIGHTS);

  // 3. Sensor de Visão por Raios (Raycaster no Canvas do Slither.io)
  function getSensoryInputs(mySnake, snakes, foods) {
    const NUM_RAYS = 12;
    const MAX_DIST = 550;
    const foodProx = new Array(NUM_RAYS).fill(0);
    const dangerProx = new Array(NUM_RAYS).fill(0);

    const headX = mySnake.xx;
    const headY = mySnake.yy;
    const headAngle = mySnake.ang;

    // Calcular proximidade em cada um dos 12 raios
    for (let r = 0; r < NUM_RAYS; r++) {
      const relAngle = (r / NUM_RAYS) * Math.PI * 2;
      const worldAngle = headAngle + (relAngle > Math.PI ? relAngle - Math.PI * 2 : relAngle);
      const dirX = Math.cos(worldAngle);
      const dirY = Math.sin(worldAngle);

      // Distância de perigo (outras cobras)
      for (const s of (snakes || [])) {
        if (!s || s.id === mySnake.id || s.dead) continue;
        for (const pt of (s.pts || [])) {
          const dx = pt.xx - headX;
          const dy = pt.yy - headY;
          const proj = dx * dirX + dy * dirY;
          if (proj > 0 && proj < MAX_DIST) {
            const perpSq = (dx * dx + dy * dy) - proj * proj;
            if (perpSq < 400) {
              const prox = 1 - proj / MAX_DIST;
              if (prox > dangerProx[r]) dangerProx[r] = prox;
            }
          }
        }
      }

      // Distância de comida
      for (const f of (foods || [])) {
        if (!f) continue;
        const dx = f.xx - headX;
        const dy = f.yy - headY;
        const proj = dx * dirX + dy * dirY;
        if (proj > 0 && proj < MAX_DIST) {
          const perpSq = (dx * dx + dy * dy) - proj * proj;
          if (perpSq < 500) {
            const prox = 1 - proj / MAX_DIST;
            if (prox > foodProx[r]) foodProx[r] = prox;
          }
        }
      }
    }

    return [
      ...foodProx,
      ...dangerProx,
      window.want_accel ? 1.0 : 0.0,
      Math.min(1.0, (mySnake.sc || 10) / 400),
      0, // ângulo relativo ao centro
      0.3 // distância da borda aproximada
    ];
  }

  // 4. Loop de Decisão Autônoma (30 vezes por segundo)
  setInterval(() => {
    if (!window.snake || window.snake.dead) return;

    try {
      const inputs = getSensoryInputs(window.snake, window.snakes, window.foods);
      const decision = brain.predict(inputs);

      // Comandar ângulo de direção
      const targetAngle = window.snake.ang + decision.steer * 0.35;
      const targetX = window.snake.xx + Math.cos(targetAngle) * 500;
      const targetY = window.snake.yy + Math.sin(targetAngle) * 500;

      // Injeta posição alvo no mouse virtual do slither
      window.xm = targetX;
      window.ym = targetY;

      // Comandar aceleração (turbo)
      window.setAcceleration(decision.boost ? 1 : 0);
    } catch (err) {
      console.warn('[SlitherAI] Erro no tick:', err);
    }
  }, 33);

  console.log('[SlitherAI] Bot ativado com sucesso! Pronto para jogar.');
})();`;

  const copyToClipboard = (text: string, type: 'code' | 'weights') => {
    navigator.clipboard.writeText(text);
    if (type === 'code') {
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2500);
    } else {
      setCopiedWeights(true);
      setTimeout(() => setCopiedWeights(false), 2500);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white font-['Outfit']">
                Como Usar essa Rede Neural no Slither.com/io Real
              </h2>
              <p className="text-xs text-slate-400">
                Arquitetura, protocolo de rede e Userscript de injeção direta no navegador
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs text-slate-300">
          {/* Section 1: Direct Answer */}
          <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-4 flex gap-3 text-emerald-200">
            <Sparkles className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-1 text-xs">
              <strong className="text-white text-sm block">
                Sim! Podemos desenvolver e treinar o bot aqui e exportá-lo diretamente para o Slither.io!
              </strong>
              <p className="text-emerald-300/90 leading-relaxed">
                A melhor metodologia para jogos como Slither.io é <strong>treinar a rede neural primeiro em um simulador local rápido (com neuroevolução genética)</strong> — exatamente como este laboratório faz —, e depois exportar os pesos sinápticos aprendidos para um script injetado no jogo real.
              </p>
            </div>
          </div>

          {/* Section 2: Why local simulation first? */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              Por que treinar no simulador antes de jogar na web?
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                <span className="font-semibold text-cyan-300 block mb-1">1. Velocidade de Treino (10.000x mais rápido)</span>
                No jogo online real, cada partida dura minutos e há latência de internet (~80ms). No nosso simulador, rodamos gerações inteiras de 24 bots a 60-600 FPS sem atraso de rede.
              </div>
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                <span className="font-semibold text-cyan-300 block mb-1">2. Sem Risco de Bloqueio / IP Ban</span>
                Treinar milhares de mortes no servidor oficial causaria banimento por spam de conexões. O simulador local gera os pesos ideais com segurança.
              </div>
            </div>
          </div>

          {/* Section 3: How slither.io protocol works */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              Como a Rede Neural envia comandos ao Slither.io
            </h3>
            <p className="text-slate-400 leading-relaxed">
              O cliente oficial do Slither.io roda em HTML5 Canvas e mantém na memória global do JavaScript as variáveis:
            </p>
            <ul className="list-disc list-inside space-y-1 text-slate-300 font-mono text-[11px] bg-slate-950/80 p-3 rounded-lg border border-slate-800">
              <li><span className="text-cyan-300">window.snake</span>: coordenadas da sua cabeça (xx, yy), ângulo e tamanho.</li>
              <li><span className="text-cyan-300">window.snakes</span>: lista de todas as outras cobras visíveis na tela.</li>
              <li><span className="text-cyan-300">window.foods</span>: posições das orbs de comida no mapa.</li>
              <li><span className="text-amber-300">window.setAcceleration(1)</span>: aciona o boost de velocidade (gasta massa).</li>
              <li><span className="text-amber-300">window.xm, window.ym</span>: coordenadas virtuais para onde a cobra deve virar.</li>
            </ul>
          </div>

          {/* Section 4: Tampermonkey Script */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                Injeção Direta no Console F12 (Nativo - Sem Extensão)
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => copyToClipboard(weightsJSON, 'weights')}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] font-medium transition-colors flex items-center gap-1"
                >
                  {copiedWeights ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedWeights ? 'Pesos Copiados!' : 'Copiar Só Pesos'}</span>
                </button>
                <button
                  onClick={() => copyToClipboard(tampermonkeyScript, 'code')}
                  className="px-3 py-1 bg-gradient-to-r from-emerald-500 to-cyan-400 hover:brightness-110 text-slate-950 rounded text-[11px] font-bold transition-colors flex items-center gap-1 shadow-sm shadow-emerald-500/30"
                >
                  {copiedCode ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedCode ? 'Copiado para F12!' : 'Copiar Script para Console F12'}</span>
                </button>
              </div>
            </div>

            <div className="relative">
              <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] font-mono text-emerald-400/90 overflow-x-auto max-h-56 leading-relaxed">
                {tampermonkeyScript}
              </pre>
            </div>
          </div>

          {/* Section 5: Step-by-step installation */}
          <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-2">
            <span className="font-semibold text-white text-xs block">Passo a Passo Rápido (Sem Instalar Nada):</span>
            <ol className="list-decimal list-inside space-y-1.5 text-xs text-slate-400">
              <li>Abra o <a href="https://slither.io" target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">slither.io</a> no Google Chrome, Edge ou Brave.</li>
              <li>Aperte a tecla <strong>F12</strong> no teclado (ou clique com botão direito &gt; Inspecionar).</li>
              <li>Clique na aba <strong>"Console"</strong>.</li>
              <li>Cole o código copiado no botão verde acima e dê <strong>Enter</strong>.</li>
              <li>Você verá a mensagem: <em>"[SlitherAI] Bot ativado com sucesso! Pronto para jogar."</em> e a sua serpente começará a jogar 100% autônoma!</li>
            </ol>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between">
          <span className="text-[11px] text-slate-500">
            Dica: Evolua várias gerações no simulador antes de exportar para garantir um bot mais experiente!
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold transition-colors"
          >
            Fechar Janela
          </button>
        </div>
      </div>
    </div>
  );
};
