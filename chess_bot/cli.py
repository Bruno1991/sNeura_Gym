"""Canivete Suíço Universal do Xadrez (s_Neura_Gym - chess_bot).

Interface unificada e centralizada de controle para:
- Ligar / reiniciar a GymArena Mobile Web (FastAPI + WebSocket)
- Executar baterias paralelas de partidas (Neural_Bot vs Bots do Chess.com com 64 workers e AMP FP16)
- Acompanhar status, telemetria e checkpoints em tempo real
- Consultar e inspecionar o catálogo dos 217 bots oficiais do Chess.com
- Jogar duelos interativos no terminal com livros Polyglot reais
- Avaliação neural de FEN com MCTS profundo
- Executar testes automatizados (pytest)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Suporte UTF-8 no terminal Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
NEURAL_DIR = CURRENT_DIR / "Neural_Bot"
SCRIPTED_DIR = CURRENT_DIR / "Scripted_Bot"
CHECKPOINTS_DIR = NEURAL_DIR / "checkpoints"
REPORTS_DIR = CURRENT_DIR / "relatorios_avancos"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(NEURAL_DIR))
sys.path.insert(0, str(SCRIPTED_DIR))

WEIGHTS_PATH = CHECKPOINTS_DIR / "chess_policy_weights.pt"
ONNX_PATH = CHECKPOINTS_DIR / "chess_policy_weights.onnx"
BOTS_DATA_FILE = CURRENT_DIR / "bots_data.json"


# ==============================================================================
# 1. GYMARENA WEB SERVER
# ==============================================================================
def start_arena(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Inicia o servidor web da GymArena Mobile."""
    print("\n" + "=" * 70)
    print("      ♛ GYMARENA MOBILE: INICIANDO SERVIDOR WEB LOCAL ♛")
    print("=" * 70)
    print(f" [*] Endereço Local    : http://localhost:{port}")
    print(f" [*] Interface de Rede : http://{host}:{port}")
    print(" [*] Peças Vetoriais   : cburnett SVG (Oficiais do Lichess)")
    print(" [*] Bots Integrados   : 217 Bots Oficiais + Neural_Bot 3200")
    print(" [*] Pressione CTRL+C para encerrar o servidor.\n")
    import uvicorn
    if reload:
        uvicorn.run("arena.server:app", host=host, port=port, reload=True, reload_dirs=[str(CURRENT_DIR / "arena")], app_dir=str(CURRENT_DIR))
    else:
        uvicorn.run("arena.server:app", host=host, port=port, reload=False, app_dir=str(CURRENT_DIR))


# ==============================================================================
# 2. BATERIA DE PARTIDAS COM WORKERS PARALELOS
# ==============================================================================
def run_battery(
    total_games: int = 10000,
    workers: int = 64,
    cycle_games: int = 250,
    max_plies: int = 80,
    engine_workers: int = 8,
):
    """Executa simulação paralela acelerada por GPU de Neural vs Bots."""
    import torch
    from chess_ai.batched_rl_trainer import BatchedRLTrainer
    from chess_ai.model import ChessPolicyValueNet
    from chess_ai.report_generator import generate_tournament_markdown_report
    from chess_bot import ChessBot

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 75)
    print(f"      ♛ BATERIA DE {total_games:,} PARTIDAS: NEURAL_BOT VS CHESS.COM BOTS ♛")
    print("=" * 75)
    print(f" [*] Hardware GPU/CPU    : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    print(f" [*] Workers Simultâneos : {workers} workers")
    print(f" [*] Processos Oponentes : {engine_workers} engine workers")
    print(f" [*] Meta de Partidas    : {total_games:,} partidas")
    print(f" [*] Limite de Plies     : {max_plies} plies ({max_plies//2} lances)")
    print(f" [*] Aceleração Tensor   : PyTorch AMP FP16 ativa")
    print("=" * 75)

    if WEIGHTS_PATH.is_file():
        print(f"[*] Carregando pesos neurais: {WEIGHTS_PATH.name}")
        model = ChessPolicyValueNet.load_weights(WEIGHTS_PATH, device=str(device))
    else:
        print("[*] Inicializando arquitetura ResNet (128 canais x 4 blocos)")
        model = ChessPolicyValueNet(in_channels=18, num_channels=128, num_blocks=4).to(device)

    # Carregar bot pool
    bot_pool = []
    if BOTS_DATA_FILE.is_file():
        try:
            with open(BOTS_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for g in data.get("botGroups", []):
                for b in g.get("botPersonalities", []):
                    bot_pool.append(ChessBot(rate=int(b.get("rating", 1500)), bot_name=b.get("name")))
            print(f"[*] Pool completo de oponentes: {len(bot_pool)} bots oficiais carregados")
        except Exception as e:
            print(f"[!] Erro ao ler bots_data.json: {e}")

    if not bot_pool:
        sample_ratings = [250, 400, 700, 1000, 1300, 1500, 1800, 2000, 2500, 2820, 3200]
        bot_pool = [ChessBot(rate=r) for r in sample_ratings]

    trainer = BatchedRLTrainer(
        model=model,
        num_workers=workers,
        device=str(device),
        use_amp=True,
        bot_pool=bot_pool,
        max_plies=max_plies,
        engine_pool_workers=engine_workers,
    )

    history_path = CHECKPOINTS_DIR / f"bateria_{total_games}_history.json"
    report_path = REPORTS_DIR / f"relatorio_bateria_{total_games}_partidas_{workers}_workers.md"

    start_time = time.time()
    try:
        trainer.run_batched_training(
            total_games=total_games,
            games_per_cycle=cycle_games,
            epochs_per_cycle=2,
            batch_size=256,
            save_weights_path=WEIGHTS_PATH,
            save_onnx_path=ONNX_PATH,
            history_path=history_path,
        )
    except KeyboardInterrupt:
        print("\n[!] Bateria interrompida pelo operador. Salvando checkpoint...")

    total_elapsed = time.time() - start_time
    total_played = trainer.env.total_completed_games

    # Salvar pesos e exportar ONNX
    try:
        model.save_weights(WEIGHTS_PATH)
        model.export_onnx(ONNX_PATH)
        print(f"[+] Pesos e modelo ONNX atualizados com sucesso em checkpoints/")
    except Exception as e:
        print(f"[!] Erro ao salvar pesos: {e}")

    # Gerar relatório Markdown
    try:
        if history_path.is_file():
            with open(history_path, "r", encoding="utf-8") as f:
                history_data = json.load(f)
            generate_tournament_markdown_report(history_data, report_path)
            print(f"[+] Relatório analítico gerado com sucesso em: {report_path}")
    except Exception as e:
        print(f"[!] Erro ao gerar relatório markdown: {e}")

    win_rate = (trainer.env.neural_wins / max(1, total_played)) * 100
    print("=" * 75)
    print(f" [✔] BATERIA CONCLUÍDA: {total_played:,} partidas jogadas em {total_elapsed/60:.2f} min")
    print(f" [✔] Vitórias: {trainer.env.neural_wins} | Empates: {trainer.env.draws} | Derrotas: {trainer.env.engine_wins}")
    print(f" [✔] Taxa de Vitória Global: {win_rate:.2f}%")
    print("=" * 75 + "\n")


# ==============================================================================
# 3. STATUS DAS BATERIAS E TELEMETRIA
# ==============================================================================
def show_battery_status():
    """Lê e exibe o progresso das baterias gravadas em checkpoints."""
    history_files = list(CHECKPOINTS_DIR.glob("*history*.json"))
    if not history_files:
        print("\n[!] Nenhum histórico de bateria encontrado em checkpoints/.")
        return

    print("\n" + "=" * 70)
    print("           ♛ STATUS E HISTÓRICO DE BATERIAS NEURAIS ♛")
    print("=" * 70)
    for hf in history_files:
        try:
            with open(hf, "r", encoding="utf-8") as f:
                data = json.load(f)
            cycles = data.get("cycles", [])
            if cycles:
                c = cycles[-1]
                t = c.get("total_completed_games", 0)
                w = c.get("global_neural_wins", 0)
                dr = c.get("global_draws", 0)
                l = c.get("global_engine_wins", 0)
                wr = c.get("neural_win_rate", 0.0)
                loss = c.get("loss", 0.0)
                elapsed_min = c.get("total_elapsed_seconds", 0) / 60.0
                print(f"\nArquivo: {hf.name}")
                print(f"  • Total de Partidas : {t:,} partidas (Ciclo {c.get('cycle', '?')})")
                print(f"  • Placar Geral      : {w:,} Vitórias | {dr:,} Empates | {l:,} Derrotas")
                print(f"  • Taxa de Vitória   : {wr:.2f}% (Score: {((w + 0.5*dr)/max(1,t))*100:.2f}%)")
                print(f"  • Loss Neural       : {loss:.4f} (AMP FP16)")
                print(f"  • Tempo Decorrido   : {elapsed_min:.1f} minutos ({elapsed_min/60:.2f}h)")
        except Exception as e:
            print(f"[!] Erro ao ler {hf.name}: {e}")
    print("=" * 70 + "\n")


# ==============================================================================
# 4. CATÁLOGO DOS 217 BOTS OFICIAIS DO CHESS.COM
# ==============================================================================
def list_bots(query: Optional[str] = None, category_filter: Optional[str] = None):
    """Consulta os 217 bots do com.chess com filtragem flexível."""
    from chess_bots import ChessBotsManager
    mgr = ChessBotsManager(CURRENT_DIR)
    groups = mgr.get_all_groups()

    print("\n" + "=" * 70)
    print(f"      ♛ CATÁLOGO OFICIAL DE BOTS DO CHESS.COM ({len(groups)} Categorias) ♛")
    print("=" * 70)

    total_found = 0
    for g in groups:
        g_name = g.get("name", "Geral")
        if category_filter and category_filter.lower() not in g_name.lower():
            continue
        bots = g.get("botPersonalities", [])
        matching = []
        for b in bots:
            name = b.get("name", "Bot")
            rating = str(b.get("rating", "?"))
            if query:
                q = query.lower()
                if q not in name.lower() and q not in rating:
                    continue
            matching.append(b)

        if matching:
            print(f"\n--- {g_name} ({len(matching)} bots) ---")
            for b in matching:
                total_found += 1
                b_name = b.get("name", "Bot")
                b_elo = b.get("rating", "?")
                b_book = b.get("book", "balanced")
                print(f"  • {b_name:<18} | Elo: {b_elo:<5} | Livro: {b_book}")

    print(f"\n[*] Total de bots listados: {total_found}")
    print("=" * 70 + "\n")


# ==============================================================================
# 5. DUELO NO TERMINAL
# ==============================================================================
def play_terminal(bot_name: str = "Nelson", player_color: str = "white"):
    """Inicia duelo interativo no terminal."""
    from chess_bots import ChessBotsManager
    mgr = ChessBotsManager(CURRENT_DIR)
    mgr.play_game(bot_name=bot_name, player_is_white=(player_color.lower() != "black"))


# ==============================================================================
# 6. AVALIAÇÃO DE FEN COM REDE NEURAL & MCTS
# ==============================================================================
def evaluate_fen(fen: str, sims: int = 50):
    """Avalia posição de xadrez com política neural e MCTS."""
    import chess
    import torch
    from chess_ai.agent import NeuralChessBot
    from chess_ai.model import ChessPolicyValueNet

    board = chess.Board(fen)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if WEIGHTS_PATH.is_file():
        model = ChessPolicyValueNet.load_weights(WEIGHTS_PATH, device=str(device))
    else:
        model = ChessPolicyValueNet().to(device)

    agent = NeuralChessBot(model=model, device=device, use_mcts=True, mcts_sims=sims)
    move, info = agent.get_best_move(board, use_mcts=True, num_simulations=sims)
    print("\n" + "=" * 60)
    print("        ♛ AVALIAÇÃO NEURAL DE POSIÇÃO (MCTS) ♛")
    print("=" * 60)
    print(f" [*] FEN             : {fen}")
    print(f" [*] Melhor Lance    : {move} ({board.san(move) if move else 'Nenhum'})")
    print(f" [*] Fonte           : {info.get('source')}")
    print(f" [*] Avaliação Valor : {info.get('value', 0.0):.3f}")
    print(f" [*] Confiança       : {info.get('probability', 0.0)*100:.1f}%")
    print("=" * 60 + "\n")


# ==============================================================================
# 7. EXECUÇÃO DE TESTES
# ==============================================================================
def run_tests():
    """Roda a suíte de testes com pytest."""
    cmd = [sys.executable, "-m", "pytest", "-v"]
    subprocess.run(cmd, cwd=str(CURRENT_DIR))


# ==============================================================================
# MENU INTERATIVO (CANIVETE SUÍÇO)
# ==============================================================================
def interactive_menu():
    while True:
        print("\n" + "=" * 70)
        print("          ♛ S_NEURA_GYM: CANIVETE SUÍÇO DO CHESS_BOT ♛")
        print("=" * 70)
        print(" [1] Ligar GymArena Mobile Server (Interface Web na porta 8000)")
        print(" [2] Rodar Bateria de Partidas (Neural_Bot vs Bots do Chess.com)")
        print(" [3] Ver Status e Telemetria das Baterias / Checkpoints")
        print(" [4] Consultar Catálogo Completo dos 217 Bots Oficiais")
        print(" [5] Jogar Duelo Interativo no Terminal contra um Bot")
        print(" [6] Avaliar Posição FEN com Neural Policy + MCTS")
        print(" [7] Executar Suíte de Testes Automatizados (pytest)")
        print(" [0] Sair")
        print("=" * 70)
        choice = input("Escolha uma opção (0-7): ").strip()

        if choice == "1":
            port_str = input("Porta do servidor (pressione Enter para 8000): ").strip()
            port = int(port_str) if port_str.isdigit() else 8000
            start_arena(port=port)
        elif choice == "2":
            games_str = input("Quantas partidas deseja simular? (padrão: 10000): ").strip()
            games = int(games_str) if games_str.isdigit() else 10000
            workers_str = input("Quantos workers paralelos? (padrão: 64): ").strip()
            workers = int(workers_str) if workers_str.isdigit() else 64
            cycle_str = input("Partidas por ciclo de aprendizado? (padrão: 250): ").strip()
            cycle = int(cycle_str) if cycle_str.isdigit() else 250
            run_battery(total_games=games, workers=workers, cycle_games=cycle)
        elif choice == "3":
            show_battery_status()
        elif choice == "4":
            q = input("Filtrar por nome ou Elo (Enter para todos): ").strip()
            list_bots(query=q if q else None)
        elif choice == "5":
            bot = input("Nome do bot (ex: Nelson, Martin, Hikaru, Maximum): ").strip() or "Nelson"
            col = input("Sua cor (white/black, padrão white): ").strip() or "white"
            play_terminal(bot_name=bot, player_color=col)
        elif choice == "6":
            fen = input("Cole a string FEN: ").strip()
            if fen:
                evaluate_fen(fen)
            else:
                print("[!] FEN vazia.")
        elif choice == "7":
            run_tests()
        elif choice == "0":
            print("\nAté logo!")
            break
        else:
            print("\n[!] Opção inválida.")


def main():
    parser = argparse.ArgumentParser(description="Canivete Suíço Universal do Chess_Bot (s_Neura_Gym)")
    parser.add_argument("--arena", action="store_true", help="Inicia o servidor web da GymArena")
    parser.add_argument("--port", type=int, default=8000, help="Porta do servidor da arena (padrão: 8000)")
    parser.add_argument("--battery", action="store_true", help="Executa bateria de partidas")
    parser.add_argument("--games", type=int, default=10000, help="Quantidade de partidas da bateria (padrão: 10000)")
    parser.add_argument("--workers", type=int, default=64, help="Número de workers simultâneos (padrão: 64)")
    parser.add_argument("--cycle-games", type=int, default=250, help="Partidas por ciclo de treinamento")
    parser.add_argument("--status", action="store_true", help="Exibe status e telemetria de baterias anteriores")
    parser.add_argument("--bots", action="store_true", help="Lista catálogo de bots oficiais")
    parser.add_argument("--query", type=str, default=None, help="Filtro para busca de bots")
    parser.add_argument("--play", action="store_true", help="Joga no terminal")
    parser.add_argument("--bot-name", type=str, default="Nelson", help="Nome do bot para duelo no terminal")
    parser.add_argument("--eval-fen", type=str, default=None, help="Avalia posição FEN com MCTS")
    parser.add_argument("--test", action="store_true", help="Roda a suíte de testes com pytest")
    args = parser.parse_args()

    if args.arena:
        start_arena(port=args.port)
    elif args.battery:
        run_battery(total_games=args.games, workers=args.workers, cycle_games=args.cycle_games)
    elif args.status:
        show_battery_status()
    elif args.bots:
        list_bots(query=args.query)
    elif args.play:
        play_terminal(bot_name=args.bot_name)
    elif args.eval_fen:
        evaluate_fen(args.eval_fen)
    elif args.test:
        run_tests()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
