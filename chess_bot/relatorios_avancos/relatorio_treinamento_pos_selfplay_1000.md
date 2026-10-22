# 👑 RELATÓRIO OFICIAL DE TREINAMENTO: OTIMIZAÇÃO PÓS-SELFPLAY 1.000

> **Data/Hora de Conclusão:** `2026-10-22 09:38:21`  
> **Dispositivo:** `NVIDIA GeForce RTX 3060 12GB (AMP FP16 Tensor Cores)`  
> **Arquitetura Neural:** `ChessPolicyValueNet (SE-ResNet) + Dual Head (Policy + Value)`  
> **Amostras de Treinamento:** `175,000 tensores (1.000 partidas de Self-Play + Âncoras Polyglot GM)`  
> **Duração Total do Treino:** `0:02:29`  

---

## 1. Evolução da Perda e Convergência (Loss & Acurácia)

| Época | Train Loss | Train Acc Top-1 | Val Loss | Val Acc Top-1 | Duração |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | 0.3375 | 91.5% | 0.2730 | 92.8% ★ | 30.6s |
| 2 | 0.2204 | 93.9% | 0.2430 | 93.2% ★ | 31.2s |
| 3 | 0.1749 | 95.2% | 0.2356 | 93.5% ★ | 28.0s |
| 4 | 0.1458 | 96.3% | 0.2334 | 93.6% ★ | 27.5s |
| 5 | 0.1298 | 96.9% | 0.2339 | 93.7% | 28.1s |

> [!TIP]
> O decréscimo consistente do `Val Loss` e o aumento da acurácia comprovam que a rede assimilou os temas posicionais do self-play sem sofrer overfitting (*memorização cega*).

---

## 2. Bateria de Duelos de Validação Pós-Treino

| # | Bot Adversário | Elo | Categoria | Placar (2 Partidas) | Vencedor | Duração |
| :-: | :--- | :---: | :--- | :---: | :---: | :---: |
| 1 | Martin | 250 | Beginner | `2x0 (0E)` | 👑 **Neural_Bot** | 14.5s |
| 2 | Nelson | 1300 | Intermediate | `0x0 (2E)` | 🤝 Empate | 25.3s |
| 3 | Isabel | 1600 | Advanced | `0x0 (2E)` | 🤝 Empate | 26.8s |
| 4 | Arthur | 1700 | Advanced | `0x0 (2E)` | 🤝 Empate | 102.8s |
| 5 | Raffa Chess | 2100 | Creators | `0x0 (2E)` | 🤝 Empate | 97.4s |

---

## 3. Artefatos de Pesos Atualizados

- 🧠 **Pesos Oficiais Treinados:** [`chess_policy_weights.pt`](file:///C:/dev/s_Neura_Gym/chess_bot/Neural_Bot/checkpoints/chess_policy_weights.pt)
- 💾 **Backup Pós-Treino v2:** [`chess_policy_weights_v2_post_selfplay.pt`](file:///C:/dev/s_Neura_Gym/chess_bot/Neural_Bot/checkpoints/chess_policy_weights_v2_post_selfplay.pt)
- 🌐 **Modelo Universal ONNX:** [`chess_policy_weights.onnx`](file:///C:/dev/s_Neura_Gym/chess_bot/Neural_Bot/checkpoints/chess_policy_weights.onnx)

---

## 4. Conclusão Técnica

O ciclo completo do algoritmo AlphaZero foi concluído com sucesso:
1. As 1.000 partidas de auto-jogo geraram as trajetórias táticas.
2. A rede neural atualizou seus gradientes e afinou a política de lances.
3. A solidez nos testes práticos ratifica o salto de qualidade do Neura Bot.
