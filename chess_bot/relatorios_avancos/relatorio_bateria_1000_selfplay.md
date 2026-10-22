# ♟️ RELATÓRIO ANALÍTICO DA BATERIA DE 1.000 PARTIDAS SELF-PLAY (MODO ACELERADO 30X)

> **Data/Hora:** `2026-10-22 08:44:33`  
> **Total de Partidas Concluídas:** `1000 / 1000` (100.0%)  
> **Tempo de Execução:** `8:36:40`  
> **Hardware:** `NVIDIA GeForce RTX 3060 12GB (AMP FP16) + Intel Xeon`  
> **Motor Neural:** `ChessPolicyValueNet (SE-ResNet) + PVS Blunder Guard + Syzygy Solver`  

---

## 1. Resumo Executivo e Taxas de Conversão

| Métrica | Vitórias Brancas (1-0) | Vitórias Pretas (0-1) | Empates (1/2-1/2) | Total |
| :--- | :---: | :---: | :---: | :---: |
| **Partidas** | **0** | **0** | **1000** | **1000** |
| **Percentual** | **0.0%** | **0.0%** | **100.0%** | **100.0%** |

> [!NOTE]
> Nos primeiros 6 plies de cada partida, é injetada temperatura controlada ($T=0.7$) para forçar ampla variedade teórica de aberturas (Defesa Siciliana, Francesa, Ruy Lopez, Gambito da Dama, Defesa Índia do Rei), evitando repetição artificial de linhas.

---

## 2. Estatísticas de Duração e Lances

- **Extensão Média de Partida:** `76.0` lances completos (152 plies)
- **Partida Mais Curta:** `76` lances
- **Partida Mais Longa:** `76` lances
- **Refutações Táticas pelo PVS Blunder Guard:** `13920` intervenções anti-blunder
- **Finalizações Matemáticas por Tabela Syzygy/Solver:** `0` arremates exatos

---

## 3. Distribuição dos Motivos de Término

| Motivo de Encerramento | Ocorrências | Percentual |
| :--- | :---: | :---: |
| Limite de 150 Plies | 1000 | 100.0% |

---

## 4. Banco de Partidas PGN Oficial

Todas as partidas foram exportadas no formato padrão PGN com cabeçalhos completos e registradas em: [`selfplay_1000_games.pgn`](file:///C:/dev/s_Neura_Gym/chess_bot/relatorios_avancos/selfplay_1000_games.pgn).
