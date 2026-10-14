"""Módulo Executável Principal do Bot Neural (Neural_Bot).

Permite jogar contra o bot neural diretamente pelo terminal, visualizar
as probabilidades calculadas pela rede neural para cada lance e avaliar posições.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

import chess

# Adicionar caminho do pacote
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from chess_ai.agent import NeuralChessBot

# Forçar suporte UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def render_board(board: chess.Board, player_is_white: bool = True) -> str:
    """Renderiza o tabuleiro no terminal."""
    piece_symbols = {
        chess.PAWN: ("P", "p"),
        chess.KNIGHT: ("N", "n"),
        chess.BISHOP: ("B", "b"),
        chess.ROOK: ("R", "r"),
        chess.QUEEN: ("Q", "q"),
        chess.KING: ("K", "k"),
    }

    ranks = range(7, -1, -1) if player_is_white else range(0, 8)
    files = range(0, 8) if player_is_white else range(7, -1, -1)

    lines = ["    +---+---+---+---+---+---+---+---+"]
    for r in ranks:
        row_str = f"  {r + 1} |"
        for f in files:
            sq = chess.square(f, r)
            piece = board.piece_at(sq)
            symbol = piece_symbols[piece.piece_type][0 if piece.color == chess.WHITE else 1] if piece else "."
            row_str += f" {symbol} |"
        lines.append(row_str)
        lines.append("    +---+---+---+---+---+---+---+---+")

    file_header = "      " + "   ".join([chess.FILE_NAMES[f] for f in files])
    lines.append(file_header)
    return "\n".join(lines)


import random



def simulate_human_delay(
    info: dict,
    min_delay: float = 1.0,
    max_delay: float = 3.2,
    enabled: bool = True,
) -> float:
    """Simula o tempo de reflexão de um jogador humano com base na certeza da rede."""
    if not enabled:
        return 0.0

    prob = info.get("probability", 0.5)
    # Quanto menor a certeza (probabilidade baixa), mais tempo o humano pondera
    uncertainty = 1.0 - min(1.0, max(0.0, prob))
    base_delay = min_delay + uncertainty * (max_delay - min_delay)

    # Jitter natural aleatório (+/- 25%)
    jitter = random.uniform(-0.25, 0.35)
    target_time = max(min_delay * 0.75, base_delay + jitter)

    start = time.time()
    print("\n[*] Neural_Bot está pensando", end="", flush=True)
    while (time.time() - start) < target_time:
        time.sleep(0.3)
        print(".", end="", flush=True)

    # Limpar a linha de 'pensando...' para exibição limpa
    print("\r" + " " * 55 + "\r", end="", flush=True)
    return time.time() - start


def play_interactive_game(
    agent: NeuralChessBot,
    player_color: chess.Color = chess.WHITE,
    temperature: float = 0.0,
    human_delay: bool = True,
    delay_min: float = 1.0,
    delay_max: float = 3.2,
    use_mcts: bool = False,
    mcts_sims: int = 50,
):
    """Executa partida interativa no terminal contra o bot neural."""
    board = chess.Board()
    player_is_white = player_color == chess.WHITE

    mode_str = f"MCTS ({mcts_sims} sims)" if use_mcts else "Política Neural Direta"
    print("\n" + "=" * 65)
    print("  PARTIDA CONTRA O AGENTE NEURAL (CHESS POLICY-VALUE RESNET)")
    print("=" * 65)
    print(" Pesos treinados a partir do livro de Grandes Mestres (3200 Elo)")
    print(f" Modo de Busca: {mode_str}")
    tempo_modo = f"Ativado ({delay_min:.1f}s a {delay_max:.1f}s)" if human_delay else "Desativado (Instantâneo)"
    print(f" Delay de Pensamento Humano: {tempo_modo}")
    print("=" * 65 + "\n")

    move_count = 1

    while not board.is_game_over():
        print(render_board(board, player_is_white))
        turn_str = "Brancas" if board.turn == chess.WHITE else "Pretas"
        print(f"\nTurno: {turn_str} (Lance {move_count})")

        if board.turn == player_color:
            # Jogador humano
            while True:
                user_input = input("\nSeu lance (ex: e4, Nf3, e2e4 ou 'sair'): ").strip()
                if user_input.lower() in ["sair", "exit", "quit", "desistir"]:
                    print("\nPartida encerrada pelo jogador.")
                    return

                try:
                    try:
                        move = board.parse_san(user_input)
                    except ValueError:
                        move = board.parse_uci(user_input)

                    if move in board.legal_moves:
                        board.push(move)
                        break
                    else:
                        print("[!] Lance ilegal! Tente novamente.")
                except Exception:
                    print("[!] Formato não reconhecido. Exemplos: 'e4', 'Nf3', 'd2d4'.")

        else:
            # Bot Neural
            t0 = time.time()
            best_move, info = agent.get_best_move(
                board,
                temperature=temperature,
                use_mcts=use_mcts,
                num_simulations=mcts_sims,
            )
            infer_ms = (time.time() - t0) * 1000.0

            if not best_move:
                print("[!] Sem lances legais.")
                break

            # Simulação do tempo de reflexão humano
            delay_spent = simulate_human_delay(
                info,
                min_delay=delay_min,
                max_delay=delay_max,
                enabled=human_delay,
            )

            san_move = board.san(best_move)
            prob_percent = info.get("probability", 0.0) * 100.0
            val_eval = info.get("value", 0.0)

            tempo_str = f"{delay_spent:.2f}s" if human_delay else f"{infer_ms:.1f}ms"
            source_tag = f"MCTS ({info.get('simulations', mcts_sims)} sims | Prof: {info.get('depth_reached', 1)})" if use_mcts else "Rede Direta"
            print(f"[*] Neural_Bot [{source_tag}] jogou: {san_move} (Confiança: {prob_percent:.1f}% | Eval: {val_eval:+.2f} | Pensou: {tempo_str})")

            # Exibir Linha Principal (PV)
            pv = info.get("principal_variation", [])
            if pv:
                print(f"    Variante calculada (PV): {' -> '.join(pv)}")

            top_candidates = info.get("top_candidates", [])
            if top_candidates:
                cands_str = ", ".join([f"{c['san']} ({c['prob']*100:.1f}%)" for c in top_candidates])
                print(f"    Top variantes consideradas: [{cands_str}]")

            board.push(best_move)

        if board.turn == chess.WHITE:
            move_count += 1

    print("\n" + "=" * 65)
    print(" FIM DA PARTIDA!")
    print("=" * 65)
    print(render_board(board, player_is_white))
    print(f"\nResultado Final: {board.result()}")


def main():
    parser = argparse.ArgumentParser(description="Neural Chess Bot (ResNet Policy-Value + MCTS)")
    parser.add_argument("--play", action="store_true", help="Inicia partida interativa contra o modelo neural")
    parser.add_argument("--color", choices=["white", "black"], default="white", help="Cor do jogador humano")
    parser.add_argument("--temp", type=float, default=0.0, help="Temperatura de amostragem (0.0 = argmax estrito)")
    parser.add_argument("--weights", type=str, default=None, help="Caminho personalizado para os pesos .pt")
    parser.add_argument("--instant", action="store_true", help="Desativa o delay humano (resposta em milissegundos)")
    parser.add_argument("--delay-min", type=float, default=1.0, help="Tempo mínimo de pensamento em segundos (padrão: 1.0)")
    parser.add_argument("--delay-max", type=float, default=3.2, help="Tempo máximo de pensamento em segundos (padrão: 3.2)")
    parser.add_argument("--mcts", action="store_true", help="Ativa o Motor de Busca Neural (Neural MCTS / Tree Search)")
    parser.add_argument("--mcts-sims", type=int, default=50, help="Número de simulações MCTS por lance (padrão: 50)")

    args = parser.parse_args()

    default_weights = current_dir / "checkpoints" / "chess_policy_weights.pt"
    weights_path = Path(args.weights) if args.weights else default_weights

    agent = NeuralChessBot(
        weights_path=weights_path,
        use_mcts=args.mcts,
        mcts_sims=args.mcts_sims,
    )
    if not agent.is_ready():
        print(f"[!] Aviso: Pesos não encontrados em {weights_path}.")
        print("    Execute o treinamento primeiro via:")
        print("    python scripts/train_distillation.py")
        sys.exit(1)

    color = chess.WHITE if args.color == "white" else chess.BLACK
    play_interactive_game(
        agent,
        player_color=color,
        temperature=args.temp,
        human_delay=not args.instant,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        use_mcts=args.mcts,
        mcts_sims=args.mcts_sims,
    )


if __name__ == "__main__":
    main()

