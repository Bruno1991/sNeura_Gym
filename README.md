# SlitherAI — Estúdio de Neuroevolução & Tensor Core CUDA

Plataforma integrada de simulação, treinamento em saturação de GPU (NVIDIA GeForce RTX 3060 12GB) e injeção autônoma no Slither.io via Console DevTools (F12).

---

## 🌟 Visão Geral

O módulo **SlitherAI** une duas tecnologias de ponta para o jogo Slither.io:

1. **Tensor Core Engine na GPU (`train_slither_cuda.py`)**:
   - População paralela massiva de **1.024 a 2.048 serpentes** simuladas simultaneamente na VRAM.
   - Inferência em lote ultrarrápida via `torch.bmm` (Batch Matrix Multiplication) nos SMs Ampere e Tensor Cores da RTX 3060 (>100.000 a 250.000 inferências/segundo).
   - Percepção sensorial de **28 entradas** (12 raios de comida, 12 raios de perigo/fronteira da arena, velocidade, razão de massa, ângulo ao centro e proximidade da borda).
   - Classificação e elitismo 100% em tensores na GPU com mutação Gaussiana paralela.
   - Servidor HTTP de telemetria em tempo real (`http://127.0.0.1:8765`) com gráficos SVG dinâmicos e endpoints REST com CORS.
   - Geração automática do script `slither_console_inject.js` e pesos serializados em `slither_champion.json`.

2. **Web Studio Interativo (React 19 + Vite 8 + Canvas 2D + Tailwind CSS)**:
   - Arena interativa em HTML5 Canvas com 60 FPS e física de colisão.
   - Visualizador de ativações neurais em tempo real (`NeuralVisualizer`).
   - Modos de jogo: **Treinamento** (evolução genética no navegador), **Player vs AI** e **Inspector**.
   - Botão **Carregar Campeão CUDA (RTX 3060)** para transferir os pesos da GPU diretamente para o simulador web em 1 clique.
   - Guia e gerador de injeção direta no Console F12 do Slither.io sem necessidade de instalar nenhuma extensão de navegador.

---

## 🚀 Como Executar

### 1. Treinamento Massivo em GPU (NVIDIA RTX 3060)

No terminal, dentro da pasta `slither`:

```powershell
python train_slither_cuda.py
```

Opções disponíveis:
- `--generations 100`: Número de gerações para treinar (padrão: 100).
- `--pop-size 1024`: Tamanho da população paralela tensorial na VRAM.
- `--port 8765`: Porta do servidor de telemetria web.
- `--open-browser`: Abre automaticamente o painel de telemetria no navegador.
- `--headless`: Executa e encerra imediatamente após o término do treino.

### 2. Painel & Simulador Web Interativo

```powershell
npm run dev
```

Abra o navegador em `http://localhost:3000/`.

---

## 🎮 Injeção Direta no Slither.io (F12 Console — Sem Extensões!)

Você **não precisa** de Tampermonkey ou de nenhuma extensão de terceiro:

1. Acesse [slither.io](https://slither.io) no Chrome, Edge ou Brave.
2. Pressione **F12** (ou `Ctrl + Shift + I`) e vá para a aba **Console**.
3. Copie o conteúdo de `slither_console_inject.js` (ou clique no botão "Copiar Script para F12" no dashboard) e dê **Enter**.
4. O bot assume o controle da cobra instantaneamente! Para pausar, execute no console:
   ```javascript
   clearInterval(window.__slitherAiInterval);
   ```

---

## 🧠 Arquitetura da Rede Neural (28 Entradas)

- **Camada de Entrada (28)**:
  - `0..11`: Proximidade de comida por feixe radial (12 raios ao redor da cabeça).
  - `12..23`: Proximidade de perigo/fronteira da arena por feixe radial.
  - `24`: Razão de velocidade (normal = 0.0, turbo/boost = 1.0).
  - `25`: Razão de massa atual ($m / 300$).
  - `26`: Ângulo relativo em direção ao centro da arena ($[-1.0, 1.0]$).
  - `27`: Proximidade da borda circular da arena ($[0.0, 1.0]$).
- **Camada Oculta 1**: 24 neurônios com ativação $\tanh$.
- **Camada Oculta 2**: 16 neurônios com ativação $\tanh$.
- **Camada de Saída (2)**:
  - `0`: Ângulo de giro (Steer) em $[-1.0, 1.0]$ com ativação $\tanh$.
  - `1`: Ativação do turbo (Boost) em $[0.0, 1.0]$ com ativação $\text{Sigmoid} > 0.55$.

