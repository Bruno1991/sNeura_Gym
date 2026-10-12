# Slither AI - Academia de Treinamento Neural (s_Neura_Gym)

Academia completa de treinamento por **Aprendizado por Máquina (Imitation Learning e PPO / Reinforcement Learning)** com simulação física **100% fiel ao código-fonte original do Slither.io** (descompilado de `air.com.hypah.io.slither` / ActionScript 3).

---

## 1. Destaques da Arquitetura

1. **Física e Dinâmica 100% Fiel:**
   - Equações de velocidade de cruzeiro (`nsp1 = 4.25`) e turbo (`fsp = 12.0`).
   - Taxa de rotação angular dependente da massa (`mang = mamu * vfr * scang * spang`), garantindo que cobras maiores tenham curvas mais lentas e realistas.
   - Perda contínua de massa durante turbo gerando esferas de alimento (`poop`).
   - Detecção geométrica exata de colisão circular cabeça-segmento e borda da arena.

2. **IA Especialista Nativa do Slither (`SlitherNativeBot`):**
   - Reprodução idêntica das 150 linhas de lógica da IA original de `gaim.Main`:
     - **Avoidance Steering:** Desvio tangencial a $\pm 15^\circ$ ($\pm 0.26\text{ rad}$) ao detectar corpos de outras cobras.
     - **Violent Mode (Ataque Predatório):** Interceptação preditiva a **95 pixels à frente da cabeça** da vítima com turbo contínuo.
     - **Foraging:** Busca de comida ótima por distância aproximada Manhattan/Chebyshev.

3. **Percepção Sensorial Egocêntrica (32 Dimensões Normalizadas):**
   - **Raios LIDAR 360° (16 valores):** Distância normalizada até corpos de cobras e bordas da arena.
   - **Cones de Alimento (8 valores):** Densidade de orbs de comida por quadrante angular de $45^\circ$.
   - **Radar de Inimigos (4 valores):** Distância, ângulo relativo e vantagem de tamanho em relação à cobra mais próxima.
   - **Estado Físico Interno (4 valores):** Velocidade atual, tamanho corporal, status de turbo e distância do centro da arena.

4. **Rede Neural Actor-Critic (`SlitherPolicyNet`):**
   - Arquitetura PyTorch com LayerNorm e cabeças independentes para ângulo ($[-1.0, 1.0] \to [-\pi, \pi]$), gatilho de turbo (BCE) e estimativa de valor (Critic).
   - Exportação automática para **TorchScript standalone (`.pt`)** e **ONNX**.

5. **Pipeline Híbrido de Treinamento:**
   - **Fase 1 (Behavior Cloning):** Treina a rede neural imitando as decisões do bot nativo especialista (loss $< 0.02$).
   - **Fase 2 (PPO Reinforcement Learning):** Refinamento no ambiente Gymnasium `SlitherEnv` com recompensas por crescimento, abates e sobrevivência.

7. **Arena do Espectador em Tempo Real (Zero Impacto no Treinamento):**
   - **Arquitetura 100% Desacoplada:** O treinamento por reforço roda em modo Headless a velocidade pura de CPU/GPU (>135 a 10.000+ FPS), sem travas de interface ou renderização.
   - **Live Web Spectator independente:** Servidor FastAPI + WebSocket que carrega qualquer checkpoint treinado (`.pt`) e renderiza uma partida a 60 FPS no navegador (`http://localhost:8080`) com:
     - Visão dos 16 raios LIDAR em tempo real (laser verde/vermelho).
     - HUD com abates, comprimento, velocidade e acionamento de turbo.
     - Câmera suave seguindo o bot e controle de zoom pelo scroll do mouse.

---

## 2. Estrutura do Diretório

```
c:\dev\s_Neura_Gym\slither_bot\
├── docs\
│   └── SLITHER_CODE_ARCHITECTURE.md   # Mapeamento canônico da engenharia reversa
├── slither_ai\
│   ├── config.py                      # Constantes físicas extraídas de Main.as
│   ├── core\
│   │   ├── entities.py                # Snake, Segment, SnakePoint, Food
│   │   ├── physics.py                 # Dinâmica de movimento, inércia e boost
│   │   ├── collision.py               # Colisão circular exata cabeça-segmento
│   │   ├── engine.py                  # SlitherEngine (simulador em alta performance)
│   │   └── expert_bot.py              # SlitherNativeBot (IA especialista nativa)
│   ├── env\
│   │   ├── sensors.py                 # Extrator sensorial LIDAR 360° (32 floats)
│   │   └── slither_env.py             # Ambiente padrão Gymnasium (reset/step)
│   ├── models\
│   │   ├── policy_net.py              # Rede Neural Actor-Critic PyTorch
│   │   └── inference.py               # Exportação TorchScript/ONNX e inferência rápida
│   ├── viewer\                        # Live Web Spectator (Desacoplado)
│   │   ├── server.py                  # Servidor FastAPI e streaming WebSocket
│   │   └── web\                       # Frontend HTML5 Canvas, CSS e JS 60 FPS
│   ├── training\
│   │   ├── dataset.py                 # Coletor de demonstrações do Expert Bot
│   │   ├── imitation_trainer.py       # Treinador por Imitação (Behavior Cloning)
│   │   └── ppo_trainer.py             # Treinador por Reforço (PPO)
│   ├── online\
│   │   ├── crypto.py                  # Handshake criptográfico challenge wtfk + CRC32
│   │   ├── protocol.py                # Parser binário e montador de pacotes v5+
│   │   └── client.py                  # SlitherOnlineClient para jogar online
│   └── utils\
│       └── math_helpers.py            # Geometria polar e conversões de bytes
├── checkpoints\                       # Modelos neurais treinados salvos
│   ├── best_imitation_model.pt        # Modelo treinado por imitação do bot nativo
│   ├── best_imitation_model_traced.pt # Modelo TorchScript standalone compilado
│   └── best_ppo_model.pt              # Modelo refinado por PPO
├── tests\                             # Suíte com 16 testes automatizados (pytest)
├── scripts\
│   ├── run_benchmark.py               # Benchmark de velocidade da física
│   ├── run_spectator.py               # Inicia o servidor da arena do espectador
│   ├── run_training_imitation.py      # Executa o treino por imitação
│   ├── run_training_ppo.py            # Executa o treino PPO
│   └── run_online_bot.py              # Inicia o bot em servidor online
├── assistir-bot.bat                   # Atalho: Inicia o Live Spectator Web (localhost:8080)
├── benchmark.bat                      # Atalho: Executa o benchmark de performance
├── treinar-imitacao.bat               # Atalho: Treina por imitação
├── treinar-rl.bat                     # Atalho: Treina por reforço (PPO)
├── jogar-bot.bat                      # Atalho: Conecta o bot em servidor
├── requirements.txt
└── README.md
```

---

## 3. Como Utilizar

### A. Atalhos com Duplo-Clique (Windows)
- **`assistir-bot.bat`**: Inicia o servidor espectador em `http://localhost:8080`. Basta abrir o link no navegador para assistir a IA jogando a 60 FPS com os raios LIDAR ativos!
- **`treinar-imitacao.bat`**: Treina a rede neural por imitação em segundos (velocidade máxima headless).
- **`treinar-rl.bat`**: Roda o auto-treinamento por Aprendizado por Reforço (PPO) em velocidade máxima headless.
- **`benchmark.bat`**: Mede a performance de simulação (FPS) da física local.
- **`jogar-bot.bat`**: Conecta o bot diretamente em um servidor online oficial ou local.

### B. Linha de Comando (Terminal)

1. **Assistir ao Bot Jogando (Spectator):**
   ```powershell
   python scripts/run_spectator.py --port 8080
   ```
   *Abra `http://localhost:8080` no navegador para assistir em tempo real.*

2. **Rodar Testes Automatizados:**
   ```powershell
   pytest tests/
   ```

3. **Benchmark de FPS:**
   ```powershell
   python scripts/run_benchmark.py
   ```

4. **Treinar Rede Neural por Imitação:**
   ```powershell
   python scripts/run_training_imitation.py
   ```

5. **Treinar por Aprendizado por Reforço (PPO):**
   ```powershell
   python scripts/run_training_ppo.py
   ```

6. **Jogar no Servidor Online com a IA:**
   ```powershell
   python scripts/run_online_bot.py --host 127.0.0.1 --port 444 --nick NeuraBot_AI
   ```
