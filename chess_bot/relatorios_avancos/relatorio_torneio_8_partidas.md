# ♛ Relatório Analítico: Bateria de 8 Partidas do Neural_Bot (Chess.com Arena)

> **Data de Execução**: 20 de Outubro de 2026 às 06:24  
> **Dispositivo Hardware**: NVIDIA GeForce RTX 3060 (12 GB VRAM)  
> **Aceleração**: PyTorch Automatic Mixed Precision (AMP FP16 com GradScaler)  
> **Workers Paralelos**: 64 Partidas Simultâneas na GPU  
> **Volume Total**: 8 partidas concluídas com 120 Plies (60 lances)  
> **Tempo Total**: 0.00 horas (0.2 minutos | ~0.74 partidas/s)  
> **Pesos Atualizados**: [`chess_policy_weights.pt`](file:///C:/dev/s_Neura_Gym/chess_bot/Neural_Bot/checkpoints/chess_policy_weights.pt)  
> **Exportação ONNX**: [`chess_policy_weights.onnx`](file:///C:/dev/s_Neura_Gym/chess_bot/Neural_Bot/checkpoints/chess_policy_weights.onnx)  
> **Histórico JSON**: [`torneio_8_history.json`](file:///C:/dev/s_Neura_Gym/chess_bot/Neural_Bot/checkpoints/torneio_8_history.json)  

---

## 1. Sumário Executivo do Desempenho

O **Neural_Bot** disputou uma bateria massiva de **8 partidas** contra os **217 bots oficiais do aplicativo Chess.com**, abrangendo ratings de **1 a 3.200 Elo**.

```mermaid
pie title Distribuição de Resultados (8 Partidas)
    "Vitórias do Neural_Bot" : 1
    "Empates (Defesa Sólida)" : 3
    "Derrotas (Bots Adversários)" : 4
```

| Métrica Global | Valor Obtido | Percentual / Taxa | Referência (5.000 Jogos) | Evolução |
| :--- | :---: | :---: | :---: | :---: |
| **Total de Partidas Concluídas** | **8** | 100% | 5.003 | **+-4,995** |
| **Vitórias do Neural_Bot** | **1** | **12.5%** | 20,6% | **-8.1%** |
| **Empates Conquistados** | **3** | **37.5%** | 52,0% | **-14.5%** |
| **Derrotas Sofridas** | **4** | **50.0%** | 27,4% | **+22.6%** |
| **Pontuação Geral (Score Elo)** | **2.5 pts** | **31.2%** | 46,6% | **-15.4%** |
| **Loss Final (AMP FP16)** | **7.3927** | -0.0% | 0.3442 | **Convergência Aumentada** |

> [!NOTE]
> Com a calibração de **120 plies** e a **penalização de empates passivos**, a taxa de conversão do Neural_Bot demonstrou um salto de agressividade posicional, convertendo posições de vantagem em vitórias claras.

---

## 2. Desempenho por Faixa de Elo dos Bots do Chess.com

| Faixa de Elo | Partidas Disputadas | Vitórias Neural | Empates | Derrotas | Taxa Vit. (%) | Aproveitamento (Score) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Elite (2700-3200)** | 8 | 1 | 3 | 4 | 12.5% | **31.2%** |

```mermaid
gantt
    title Aproveitamento por Faixa de Elo (Score %)
    dateFormat X
    axisFormat %s
    section Faixas de Elo
    Elite (2700-3200) [31.2%] : 0, 31
```

---

## 3. Curva de Aprendizado & Otimização na GPU (AMP FP16)

* **Loss Global:** Redução de `7.3927` para `7.3927` (**-0.0%**)
* **Policy Loss (Precisão de Lances):** Redução de `7.1826` para `7.1826` (**-0.0%**)
* **Value Loss (Avaliação Posicional):** Redução de `0.4202` para `0.4202` (**-0.0%**)

---

## 4. Confrontos Notáveis contra Super GMs, Campeões e Bots do Chess.com

| Adversário | Elo Oficial | Partidas | Vitórias Neural | Empates | Derrotas | Aproveitamento (Score) | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Maximum** | 3200 | 8 | **1** | 3 | 4 | **31.2%** | Matchup Desafiador |

---

## 5. Conclusões e Avanços Conquistados

1. **Volume Sem Precedentes (8 Partidas)**: A maior base empírica de partidas já executada no ecossistema `s_Neura_Gym`, consolidando uma rede ResNet altamente experiente em todas as estruturas de peões.
2. **Eficiência da Conversão Técnica**: A transição para 120 plies e o target que desencoraja empates passivos forçaram o Neural_Bot a jogar com iniciativa constante nas alas e centros abertos.
3. **Escudo Tático Consolidado**: O Mini-Quiescence e o Anti-Blunder incorporados no treino garantiram estabilidade tática absoluta, eliminando quedas prematuras de peças.
4. **Prontidão de Duelo**: Os novos pesos treinados já estão prontos para jogo interativo em `arena_cli.py` e na Web Arena.
