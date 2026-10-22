# ♟️ Guia Rápido de Subcomandos do Canivete Suíço (`cli.py`)

Este documento serve como referência rápida para todos os utilitários e rotinas do ecossistema **s_Neura_Gym (chess_bot)**.

---

## 1. Modo Interativo (Menu Visual Rich)
Para abrir o menu interativo com botões e validação em terminal:
```bash
# Via executável batch
.\tools.bat

# Ou diretamente pelo Python
python cli.py
```

---

## 2. Linha de Comando (Subcomandos Diretos)

### 🌐 GymArena Mobile Server (Interface Web)
Inicia o servidor FastAPI + WebSocket com tabuleiro SVG cburnett oficial e efeitos sonoros:
```bash
# Iniciar na porta padrão 8000
python cli.py arena --port 8000

# Permitir acesso de outros dispositivos na rede local
python cli.py arena --host 0.0.0.0 --port 8000
```

### 📊 Dashboard e Telemetria em Tempo Real
Exibe status dos checkpoints, pesos treinados, placar de torneio e relatórios:
```bash
python cli.py status
```

### 📖 Catálogo dos 217 Bots Oficiais
Pesquisa bots do Chess.com descompilados por nome, Elo, livro ou categoria:
```bash
# Buscar um bot específico
python cli.py bots --query Nelson

# Filtrar por categoria (Master, Beginner, Intermediate, etc.)
python cli.py bots --category Master

# Listar todos os 217 bots
python cli.py bots
```

### ⚔️ Duelo Interativo no Terminal
Joga uma partida no terminal contra qualquer bot oficial utilizando livros Polyglot (.bin) reais:
```bash
# Jogar de Brancas contra o bot Nelson
python cli.py duelo --bot Nelson --color white

# Jogar de Pretas contra o bot Hikaru
python cli.py duelo --bot Hikaru --color black
```

### 🏆 Torneio MD3 Oficial (217 Bots)
Executa o torneio em modo acelerado 30x (in-memory multi-threaded na GPU RTX 3060):
```bash
# Continuar a partir do último checkpoint (Recomendado)
python cli.py torneio --workers 4 --resume

# Reiniciar torneio do zero descartando checkpoint
python cli.py torneio --workers 4 --fresh
```

### ♟️ Bateria de Self-Play (Auto-Jogo com PGN)
Simula partidas autônomas entre instâncias do Neura Bot e grava as jogadas em PGN:
```bash
# Executar bateria padrão de 1.000 partidas
python cli.py selfplay --games 1000 --workers 4

# Continuar bateria interrompida
python cli.py selfplay --games 1000 --workers 4 --resume
```

### 🧠 Treinamento e Ajuste Fino Neural (AMP FP16)
Realiza o fine-tuning da arquitetura SE-ResNet na GPU NVIDIA RTX 3060 a partir do PGN e livros GM:
```bash
# Treino padrão (15 épocas, batch size 512, com duelos de validação)
python cli.py treinar --epochs 15 --batch-size 512

# Forçar reconstrução completa dos tensores
python cli.py treinar --epochs 15 --batch-size 512 --rebuild
```

### 🚀 Pipeline Master Completo Automatizado
Encadeia sequencialmente Torneio MD3 -> Self-Play 1.000 -> Treinamento Neural -> Relatório Master -> Git Sync:
```bash
python cli.py pipeline
```

### 🎯 Avaliação Neural de Posição FEN
Avalia qualquer posição com política, valor e simulação MCTS profunda:
```bash
# Avaliar posição inicial
python cli.py avaliar "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" --sims 50

# Avaliar posição tática complexa
python cli.py avaliar "r1bqkb1r/pppp1ppp/2n5/4p3/2B1n3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 5" --sims 100
```

### 🧪 Suíte de Testes Automatizados (pytest)
Executa a validação de integridade dos 50 testes automatizados da arquitetura:
```bash
python cli.py test
```
