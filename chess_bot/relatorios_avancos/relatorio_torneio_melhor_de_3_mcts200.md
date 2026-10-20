# ♛ Relatório Oficial de Torneio: GymArena Chromium Headless ♛

> **Data de Execução:** 20/10/2026 05:15:20 | **Tempo Decorrido:** 1:07:47
> **Ambiente:** Chromium Headless (Google Chrome Oficial) via Playwright
> **Motor Neural:** `Neural_Bot 3200 Elo` (ResNet 128ch + 4 Blocks, MCTS=200 nós, Escudo Tático & Endgame Finisher)
> **Regras da Partida:** Melhor de 3 partidas (MD3), Cor Aleatória, Duelo ao Vivo 100ms, MCTS=ON

---

## 1. Resumo Executivo da Performance

| Métrica Geral | Valor |
| :--- | :--- |
| **Total de Bots Enfrentados** | `10` de `10` |
| **Total de Partidas Jogadas** | `24` partidas individuais |
| **Séries Vencidas pelo Neural_Bot** | `10` (100.0%) |
| **Séries Perdidas pelo Neural_Bot** | `0` |
| **Séries Empatadas** | `0` |
| **Placar Global de Partidas** | `19 Vitórias` / `0 Derrotas` / `5 Empates` (79.2% Win Rate) |
| **Erros de Página (JavaScript)** | `0` |
| **Erros de Console (DevTools)** | `0` |
| **Falhas de Rede (HTTP >= 400)** | `0` |

---

## 2. Tabela Detalhada das Séries Melhor de 3

| # | Bot Oponente | Elo | Categoria | Placar MD3 | Vencedor da Série | Lances Totais | Duração Total | Detalhes das Partidas |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 01 | **The Mechanical Turk** | 1 | Personalities | `2 - 0` | **Neural_Bot** | 117 | 290.6s | G1: 0-1 (B, 54l) | G2: 1-0 (W, 63l) |
| 02 | **June** | 50 | New to Chess | `2 - 0` | **Neural_Bot** | 97 | 246.8s | G1: 0-1 (B, 64l) | G2: 1-0 (W, 33l) |
| 03 | **Pepe** | 100 | New to Chess | `2 - 0 (1E)` | **Neural_Bot** | 123 | 327.9s | G1: 1/2-1/2 (B, 115l) | G2: 1-0 (W, 63l) | G3: 0-1 (B, 60l) |
| 04 | **Elsa** | 150 | New to Chess | `2 - 0` | **Neural_Bot** | 183 | 405.5s | G1: 0-1 (B, 72l) | G2: 1-0 (W, 111l) |
| 05 | **Beginner** | 250 | Engine | `2 - 0` | **Neural_Bot** | 151 | 375.1s | G1: 0-1 (B, 74l) | G2: 1-0 (W, 77l) |
| 06 | **Elani** | 400 | Beginner | `2 - 0` | **Neural_Bot** | 181 | 370.2s | G1: 1-0 (W, 109l) | G2: 0-1 (B, 72l) |
| 07 | **Milica** | 550 | Beginner | `2 - 0 (1E)` | **Neural_Bot** | 164 | 525.2s | G1: 1/2-1/2 (W, 110l) | G2: 0-1 (B, 60l) | G3: 0-1 (B, 104l) |
| 08 | **Loch Chess Monster** | 575 | The Cryptids | `2 - 0 (1E)` | **Neural_Bot** | 148 | 354.5s | G1: 0-1 (B, 86l) | G2: 1/2-1/2 (W, 95l) | G3: 0-1 (B, 62l) |
| 09 | **HarryMack** | 600 | Creators | `2 - 0` | **Neural_Bot** | 177 | 461.1s | G1: 0-1 (B, 122l) | G2: 1-0 (W, 55l) |
| 10 | **Aron** | 700 | Beginner | `1 - 0 (2E)` | **Neural_Bot** | 43 | 127.0s | G1: 1-0 (W, 43l) | G2: 1/2-1/2 (B, 145l) | G3: 1/2-1/2 (B, 115l) |

---

## 3. Auditoria de Confiabilidade & Integridade do Frontend / Backend

- **Exceções de Página não Tratadas:** 0
- **Erros no Console do Chromium:** 0
- **Erros de Rede / WebSocket / HTTP:** 0
