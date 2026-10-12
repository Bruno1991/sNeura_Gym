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

5. **Pipeline de Destilação Ativa DAgger (Dataset Aggregation):**
   - Transfere 100% da inteligência da IA nativa do APK diretamente para os pesos da Rede Neural.
   - Elimina o problema de desvio de distribuição (*covariate shift*): a rede neural pilota, mas o bot especialista intervém a cada tick e rotula a ação ótima de correção.
   - **Semeadura Universal (Universal Warm Start):** Os pesos destilados são gravados em `best_imitation_model.pt`, `best_imitation_model_traced.pt` e `best_ppo_model.pt`, garantindo que o agente comece já jogando em alto nível em qualquer modo.

6. **Refinamento por Aprendizado por Reforço (PPO Self-Play):**
   - Inicia com os pesos do DAgger já competentes e otimiza a política no ambiente Gymnasium `SlitherEnv`.

7. **Motor de Treinamento Contínuo 24/7 para Maestria Neural:**
   - Loop unificado ininterrupto que roda infinitamente até o bot atingir a meta estipulada de maestria (ex: 95%+).
   - **Self-Play:** A rede neural joga contra versões históricas de si mesma e contra a IA especialista original.
   - **Recompensas Predatórias Avançadas:** Recompensa massiva por abates e armadilhas (*cut-offs* com +80), crescimento de massa (+4) e penalidade severa por choque em paredes (-100).
   - **Índice Oficial de Maestria (0% a 100%):** Bateria periódica de benchmark determinístico avaliando comprimento, abates, tempo de vida e taxa de sobrevivência à arena.
   - **Pesos de Ouro (`master_bot_model.pt`):** Sempre que a IA bate seu recorde histórico em maestria ou abates, salva e compila automaticamente os pesos de ouro.
   - **Interrupção Segura:** Pressione `Ctrl+C` a qualquer momento para finalizar com segurança mantendo todos os pesos e recordes intactos.

8. **Operação 100% Headless no Terminal (Máximo Rendimento de Hardware):**
   - Todo o ecossistema roda diretamente pelo terminal aproveitando o máximo da GPU CUDA (RTX 3060) e dos núcleos da CPU sem travas ou overhead de renderização visual no navegador.
   - Painel de telemetria e progresso em tempo real no próprio terminal com cálculo de FPS, abates e causas de morte.

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
│   │   └── inference.py               # Exportação TorchScript standalone e inferência
│   ├── training\
│   │   ├── dataset.py                 # Coletor de demonstrações do Expert Bot
│   │   ├── dagger_trainer.py          # Destilador Ativo DAgger (GPU Max Speed)
│   │   ├── imitation_trainer.py       # Treinador por Imitação supervisionada
│   │   ├── ppo_trainer.py             # Treinador por Reforço (PPO)
│   │   └── mastery_trainer.py         # Motor de Treinamento Contínuo 24/7 (Maestria)
│   ├── online\
│   │   ├── crypto.py                  # Handshake criptográfico challenge wtfk + CRC32
│   │   ├── protocol.py                # Parser binário e montador de pacotes v5+
│   │   └── client.py                  # SlitherOnlineClient para jogar online
│   └── utils\
│       └── math_helpers.py            # Geometria polar e conversões de bytes
├── checkpoints\                       # Modelos neurais treinados salvos
│   ├── master_bot_model.pt            # Pesos de Ouro da IA (Melhor Desempenho Histórico)
│   ├── master_bot_model_traced.pt     # Pesos de Ouro compilados para TorchScript
│   ├── best_imitation_model.pt        # Pesos destilados via DAgger da IA do APK
│   ├── best_imitation_model_traced.pt # Modelo compilado standalone TorchScript
│   └── best_ppo_model.pt              # Modelo pré-semeado / refinado por PPO
├── tests\                             # Suíte com 17 testes automatizados (pytest)
├── scripts\
│   ├── run_training_247.py            # Executa o Treinamento Contínuo 24/7 até a Maestria
│   ├── run_training_dagger.py         # Executa a destilação DAgger na GPU
│   ├── run_training_ppo.py            # Executa o auto-treinamento PPO
│   ├── run_eval_terminal.py           # Avalia partidas no terminal em tempo real
│   ├── run_benchmark.py               # Mede a taxa de FPS físico da engine
│   └── run_online_bot.py              # Inicia o bot conectado a servidores online
├── treinar-247-maestria.bat           # Atalho: Treinamento Contínuo 24/7 até Maestria (Pesos de Ouro)
├── treinar-dagger.bat                 # Atalho: Destila a IA do APK nos pesos neurais (GPU)
├── treinar-rl.bat                     # Atalho: Treina por reforço (PPO) com Warm Start
├── avaliar-bot.bat                    # Atalho: Executa partidas de teste no terminal
├── benchmark.bat                      # Atalho: Mede o throughput físico em FPS
├── jogar-bot.bat                      # Atalho: Conecta o bot em servidor online
├── requirements.txt
└── README.md
```

---

## 3. Como Utilizar

### A. Atalhos com Duplo-Clique (Windows)
- **`treinar-247-maestria.bat`**: Inicia o treinamento ininterrupto 24/7. Auto-play acelerado na GPU, ranking de recordes e salvamento contínuo dos pesos de ouro (`master_bot_model.pt`). Interrompa quando quiser com `Ctrl+C`.
- **`treinar-dagger.bat`**: Transfere toda a inteligência da IA nativa do APK para a rede neural com aceleração de GPU (CUDA) e barra de progresso no terminal.
- **`avaliar-bot.bat`**: Roda partidas completas no terminal em milhares de FPS e exibe o relatório de abates, comprimento e sobrevivência do melhor modelo existente.
- **`treinar-rl.bat`**: Refina a rede neural via PPO partindo dos pesos já inteligentes do DAgger.
- **`benchmark.bat`**: Mede a taxa de simulação física (FPS) da engine local.
- **`jogar-bot.bat`**: Conecta a IA diretamente a um servidor online do Slither.io usando os melhores pesos.

### B. Linha de Comando (Terminal)

1. **Treinamento Contínuo 24/7 até Maestria (GPU):**
   ```powershell
   python scripts/run_training_247.py --target-mastery 95.0 --eval-interval 5
   ```

2. **Destilar Inteligência do APK via DAgger (GPU):**
   ```powershell
   python scripts/run_training_dagger.py --iterations 5 --steps 15000
   ```

3. **Avaliar Desempenho no Terminal (Sem Interface Gráfica):**
   ```powershell
   python scripts/run_eval_terminal.py --episodes 20
   ```

4. **Treinar por Aprendizado por Reforço (PPO com Warm Start):**
   ```powershell
   python scripts/run_training_ppo.py
   ```

5. **Executar Benchmark de Velocidade da Física:**
   ```powershell
   python scripts/run_benchmark.py
   ```

6. **Rodar Testes Automatizados:**
   ```powershell
   pytest tests/
   ```

7. **Jogar no Servidor Online Oficial com a IA:**
   ```powershell
   python scripts/run_online_bot.py --host 127.0.0.1 --port 444 --nick NeuraBot_AI
   ```
