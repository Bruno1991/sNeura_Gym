"""Confronto Direto entre Bots: Neural_Bot (ResNet + MCTS) vs Maximum 3200 (Scripted_Bot).

Executa uma partida local completa entre o agente neural e o bot de 3200 Elo,
exibindo o tabuleiro, probabilidades, variantes de cálculo (PV) e gerando o PGN da partida.
100% autônomo, não requer dependências externas além do ambiente local.
"""

import argparse
import sys
import time
from pathlib import Path

import chess
import chess.pgn

# Configurar caminhos do projeto
current_dir = Path(__file__).resolve().parent
scripted_bot_dir = current_dir.parent / "Scripted_Bot"

sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(scripted_bot_dir))

from chess_ai.agent import NeuralChessBot
from bot_3200 import ChessBot3200, render_board

# Forçar suporte UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_bot_battle(
    neural_is_white: bool = True,
    delay_between_moves: float = 1.0,
    max_fullmoves: int = 60,
    temperature: float = 0.0,
    use_mcts: bool = False,
    mcts_sims: int = 50,
):
    """Executa a partida completa entre o Neural_Bot e o Bot de 3200 Elo."""
    weights_path = current_dir / "checkpoints" / "chess_policy_weights.pt"
    neural_agent = NeuralChessBot(
        weights_path=weights_path,
        use_mcts=use_mcts,
        mcts_sims=mcts_sims,
    )

    if not neural_agent.is_ready():
        print(f"[!] Erro: Pesos neurais não encontrados em {weights_path}.")
        return

    bot_3200 = ChessBot3200()

    board = chess.Board()
    pgn_game = chess.pgn.Game()
    pgn_node = pgn_game

    neural_tag = f"Neural_Bot (ResNet + MCTS {mcts_sims})" if use_mcts else "Neural_Bot (ResNet)"
    white_name = neural_tag if neural_is_white else "Maximum (3200 Elo)"
    black_name = "Maximum (3200 Elo)" if neural_is_white else neural_tag

    pgn_game.headers["Event"] = "Duelo Local s_Neura_Gym"
    pgn_game.headers["White"] = white_name
    pgn_game.headers["Black"] = black_name
    pgn_game.headers["Date"] = time.strftime("%Y.%m.%d")

    print("\n" + "=" * 70)
    print("   CONFRONTO DIRETO: NEURAL_BOT vs MAXIMUM 3200 ELO")
    print("=" * 70)
    print(f" Brancas: {white_name}")
    print(f" Pretas : {black_name}")
    print(f" Modo Neural: {'MCTS Tree Search (' + str(mcts_sims) + ' sims)' if use_mcts else 'Política Neural Direta'}")
    print(f" Delay entre lances: {delay_between_moves:.1f}s")
    print("=" * 70 + "\n")

    while not board.is_game_over(claim_draw=True) and board.fullmove_number <= max_fullmoves:
        is_neural_turn = (board.turn == chess.WHITE and neural_is_white) or (board.turn == chess.BLACK and not neural_is_white)
        player_title = "NEURAL_BOT" if is_neural_turn else "MAXIMUM 3200"

        print(render_board(board, player_is_white=True))
        turn_str = "Brancas" if board.turn == chess.WHITE else "Pretas"
        print(f"\nLance {board.fullmove_number} - Turno: {turn_str} [{player_title}]")

        t0 = time.time()
        if is_neural_turn:
            print(f"[*] {player_title} calculando com {'MCTS Tree Search' if use_mcts else 'Rede Neural'}...")
            move, info = neural_agent.get_best_move(
                board,
                temperature=temperature,
                use_mcts=use_mcts,
                num_simulations=mcts_sims,
            )
            elapsed = time.time() - t0
            prob_percent = info.get("probability", 0.0) * 100.0
            val = info.get("value", 0.0)
            if use_mcts:
                tag = f"[MCTS {info.get('simulations', mcts_sims)} sims | Prof: {info.get('depth_reached', 1)} | Eval: {val:+.2f}]"
            else:
                tag = f"[REDE Confiança: {prob_percent:.1f}% | Eval: {val:+.2f}]"
        else:
            print(f"[*] {player_title} consultando livro e motor...")
            move, info = bot_3200.get_best_move(board, max_depth=3)
            elapsed = time.time() - t0
            source = info.get("source")
            if source == "book":
                tag = f"[LIVRO balanced.bin (Peso: {info.get('weight', 0)})]"
            else:
                score_cp = info.get("score_cp", 0)
                tag = f"[MOTOR PeSTO d={info.get('depth', '?')} | Eval: {score_cp/100:+.2f}]"

        if not move or move not in board.legal_moves:
            print(f"[!] Lance ilegal ou nulo gerado por {player_title}: {move}")
            break

        san_move = board.san(move)
        print(f"[*] {player_title} jogou: {san_move:<7} {tag} ({elapsed:.2f}s)")
        if is_neural_turn and use_mcts and "principal_variation" in info:
            print(f"    Variante calculada (PV): {' -> '.join(info['principal_variation'])}")

        pgn_node = pgn_node.add_variation(move)
        board.push(move)

        if delay_between_moves > 0:
            time.sleep(delay_between_moves)

    # Fim da Partida
    print("\n" + "=" * 70)
    print(" FIM DO CONFRONTO!")
    print("=" * 70)
    print(render_board(board, player_is_white=True))

    res = board.result(claim_draw=True)
    pgn_game.headers["Result"] = res

    print(f"\nResultado Final: {res}")
    if board.is_checkmate():
        vencedor = black_name if board.turn == chess.WHITE else white_name
        print(f"Vitória por Xeque-Mate de: {vencedor}!")
    elif board.is_stalemate():
        print("Empate por Afogamento (Stalemate)!")
    elif board.is_insufficient_material():
        print("Empate por Material Insuficiente!")
    elif board.can_claim_threefold_repetition():
        print("Empate por Repetição de Posição!")
    elif board.can_claim_fifty_moves():
        print("Empate pela Regra dos 50 Lances!")
    else:
        print("Partida concluída.")

    # Salvar PGN
    partidas_dir = current_dir / "partidas"
    partidas_dir.mkdir(parents=True, exist_ok=True)
    pgn_file = partidas_dir / "duelo_neural_vs_3200.pgn"
    with open(pgn_file, "w", encoding="utf-8") as f:
        print(pgn_game, file=f)

    print(f"\n[+] PGN da partida salvo em: {pgn_file}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Duelo: Neural_Bot vs Maximum 3200")
    parser.add_argument("--neural-white", action="store_true", default=True, help="Neural_Bot joga de Brancas (padrão: True)")
    parser.add_argument("--neural-black", action="store_true", help="Neural_Bot joga de Pretas")
    parser.add_argument("--delay", type=float, default=1.0, help="Pausa em segundos entre cada lance para acompanhamento (padrão: 1.0)")
    parser.add_argument("--max-moves", type=int, default=60, help="Limite máximo de lances completos (padrão: 60)")
    parser.add_argument("--temp", type=float, default=0.0, help="Temperatura do bot neural (0.0 = mais preciso)")
    parser.add_argument("--mcts", action="store_true", help="Ativa o Motor de Busca Neural (Neural MCTS / Tree Search)")
    parser.add_argument("--mcts-sims", type=int, default=50, help="Número de simulações MCTS por lance (padrão: 50)")

    args = parser.parse_args()

    neural_is_white = not args.neural_black
    run_bot_battle(
        neural_is_white=neural_is_white,
        delay_between_moves=args.delay,
        max_fullmoves=args.max_moves,
        temperature=args.temp,
        use_mcts=args.mcts,
        mcts_sims=args.mcts_sims,
    )


if __name__ == "__main__":
    main()
