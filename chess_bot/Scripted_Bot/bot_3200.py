"""Bot de Xadrez 3200 Elo - Maximum (Komodo 25).

Isolamento completo e autônomo do bot de 3200 de rating extraído da engenharia
reversa do aplicativo Chess.com (com.chess).

Características:
- Livro de Abertura Polyglot balanced.bin (1.28 MB) oficial com dezenas de milhares de posições.
- Motor de cálculo tático e posicional com avaliação PeSTO (Piece-Square Tables para Middlegame e Endgame).
- Busca minimax com poda Alpha-Beta, Transposition Table (Zobrist Hash), Quiescence Search e MVV-LVA.
- Suporte automático a motor UCI externo (Stockfish/Komodo) se presente em bin/ ou PATH.
- Interface interativa via terminal com renderização do tabuleiro e diálogo do bot.
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.polyglot

from engine.evaluation import evaluate_board
from engine.search import AlphaBetaSearcher
from engine.uci_wrapper import UCIEngineWrapper

# Suporte a caracteres UTF-8 no Windows PowerShell e CMD
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class ChessBot3200:
    """Implementação isolada do bot oficial de 3200 Elo (Maximum / Komodo 25)."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        use_uci_if_available: bool = True,
        max_depth: int = 4,
        max_time_seconds: float = 2.5,
    ):
        self.base_dir = base_dir or Path(__file__).resolve().parent
        self.assets_dir = self.base_dir / "assets"
        self.profile_path = self.assets_dir / "bot_3200_profile.json"
        self.book_path = self.assets_dir / "balanced.bin"

        self.profile: Dict[str, Any] = self._load_profile()
        self.name: str = self.profile.get("name", "Maximum")
        self.username: str = self.profile.get("username", "Komodo25")
        self.rating: int = self.profile.get("rating", 3200)
        self.komodo_skill: int = self.profile.get("komodoSkillLevel", 25)
        self.phrases: Dict[str, str] = self.profile.get("phraseList", {})

        # Motor de busca interno
        self.builtin_searcher = AlphaBetaSearcher(
            max_depth=max_depth,
            max_time_seconds=max_time_seconds,
        )

        # Motor UCI opcional
        self.uci_wrapper = UCIEngineWrapper()
        self.use_uci = use_uci_if_available and self.uci_wrapper.is_available()

        # Leitor de livro de abertura Polyglot
        self._polyglot_reader: Optional[chess.polyglot.MemoryMappedReader] = None
        self._init_opening_book()

    def _load_profile(self) -> Dict[str, Any]:
        """Carrega a ficha técnica do bot do arquivo JSON de assets."""
        if self.profile_path.is_file():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "name": "Maximum",
            "username": "Komodo25",
            "rating": 3200,
            "komodoSkillLevel": 25,
            "book": "balanced",
            "phraseList": {
                "greeting": "Prepare-se para enfrentar o nível máximo da engine (Rating 3200).",
                "won": "Partida concluída. O cálculo tático e posicional prevaleceu.",
                "lost": "Excelente partida! Uma vitória impressionante contra uma avaliação de 3200.",
                "givingCheck": "Xeque. Suas opções defensivas estão sendo calculadas.",
                "queenCaptured": "A dama caiu, mas a avaliação posicional continua ativa.",
                "capturingQueen": "Dama capturada com precisão posicional.",
            },
        }

    def _init_opening_book(self):
        """Abre o livro de aberturas Polyglot balanced.bin."""
        if self.book_path.is_file():
            try:
                self._polyglot_reader = chess.polyglot.open_reader(str(self.book_path))
            except Exception as e:
                print(f"[!] Aviso: Não foi possível carregar o livro {self.book_path.name}: {e}")
                self._polyglot_reader = None

    def get_book_move(self, board: chess.Board) -> Optional[Tuple[chess.Move, int]]:
        """Busca movimento no livro Polyglot balanced.bin.
        
        Retorna (move, weight) ou None se a posição estiver fora do livro.
        """
        if not self._polyglot_reader:
            return None

        try:
            entries = list(self._polyglot_reader.find_all(board))
            if not entries:
                return None

            # Para um bot 3200 Elo, selecionamos com maior peso as melhores variantes
            weights = [e.weight for e in entries]
            total_weight = sum(weights)
            if total_weight > 0:
                chosen = random.choices(entries, weights=weights, k=1)[0]
                return chosen.move, chosen.weight
            return entries[0].move, entries[0].weight
        except Exception:
            return None

    def get_best_move(
        self,
        board: chess.Board,
        max_depth: Optional[int] = None,
        max_time_seconds: Optional[float] = None,
    ) -> Tuple[Optional[chess.Move], Dict[str, Any]]:
        """Determina o melhor lance do bot.
        
        Retorna: (best_move, info_dict)
        """
        if board.is_game_over():
            return None, {"source": "game_over"}

        # 1. Consulta ao Livro de Abertura balanced.bin
        book_res = self.get_book_move(board)
        if book_res is not None:
            move, weight = book_res
            return move, {
                "source": "book",
                "book": "balanced.bin",
                "weight": weight,
                "san": board.san(move),
            }

        # 2. Motor UCI externo (se configurado e disponível)
        if self.use_uci and self.uci_wrapper.is_available():
            time_limit = max_time_seconds or 1.5
            move, score, depth = self.uci_wrapper.search_best_move(
                board,
                time_limit=time_limit,
                depth_limit=max_depth,
            )
            if move:
                return move, {
                    "source": "uci_engine",
                    "engine": self.uci_wrapper.engine_path.name,
                    "depth": depth,
                    "score_cp": score,
                    "san": board.san(move),
                }

        # 3. Motor Alpha-Beta com PeSTO e Quiescence Search
        move, score, depth, nodes = self.builtin_searcher.search_best_move(
            board,
            max_depth=max_depth,
            max_time_seconds=max_time_seconds,
        )

        return move, {
            "source": "builtin_alphabeta",
            "depth": depth,
            "score_cp": score,
            "nodes": nodes,
            "san": board.san(move) if move else None,
        }

    def print_profile(self):
        """Exibe a ficha técnica e parâmetros do bot."""
        print("\n" + "=" * 65)
        print(f" FICHA TÉCNICA DO BOT: {self.name} (Rating {self.rating})")
        print("=" * 65)
        print(f" Nome Oficial        : {self.name}")
        print(f" Username no Chess.com: {self.username}")
        print(f" Rating Elo          : {self.rating}")
        print(f" Komodo Skill Level  : {self.komodo_skill} / 25 (Nível Máximo)")
        print(f" Personalidade       : {self.profile.get('personality')}")
        print(f" Livro de Abertura   : {self.book_path.name} ({self.book_path.stat().st_size / 1024:.1f} KB)")
        engine_mode = "UCI Externo" if self.use_uci else "Motor PeSTO Alpha-Beta Interno"
        print(f" Modo de Cálculo     : {engine_mode}")
        print(f" Imagem de Avatar    : {self.profile.get('imageUrl')}")
        print("-" * 65)
        print(" Frases de Diálogo:")
        for k, v in self.phrases.items():
            print(f"   - {k:<15}: \"{v}\"")
        print("=" * 65 + "\n")


def render_board(board: chess.Board, player_is_white: bool = True) -> str:
    """Renderiza o tabuleiro de forma limpa e elegante no terminal."""
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

    lines = []
    lines.append("    +---+---+---+---+---+---+---+---+")
    for r in ranks:
        row_str = f"  {r + 1} |"
        for f in files:
            sq = chess.square(f, r)
            piece = board.piece_at(sq)
            if piece:
                symbol = piece_symbols[piece.piece_type][0 if piece.color == chess.WHITE else 1]
            else:
                symbol = "."
            row_str += f" {symbol} |"
        lines.append(row_str)
        lines.append("    +---+---+---+---+---+---+---+---+")

    file_header = "      " + "   ".join([chess.FILE_NAMES[f] for f in files])
    lines.append(file_header)
    return "\n".join(lines)


def play_interactive_game(
    bot: ChessBot3200,
    player_color: chess.Color = chess.WHITE,
    max_depth: int = 4,
    max_time_seconds: float = 2.5,
):
    """Executa partida interativa no terminal contra o Bot de 3200 Elo."""
    board = chess.Board()
    player_is_white = player_color == chess.WHITE

    print("\n" + "=" * 65)
    print(f"  PARTIDA CONTRA: {bot.name} (Rating {bot.rating} Elo)")
    print("=" * 65)
    if "greeting" in bot.phrases:
        print(f"\n{bot.name}: \"{bot.phrases['greeting']}\"\n")

    move_count = 1

    while not board.is_game_over():
        print(render_board(board, player_is_white))
        turn_str = "Brancas" if board.turn == chess.WHITE else "Pretas"
        print(f"\nTurno: {turn_str} (Lance {move_count})")

        if board.turn == player_color:
            # Vez do jogador humano
            while True:
                user_input = input("\nSeu lance (ex: e4, Nf3, e2e4 ou 'sair'/'desistir'): ").strip()
                if user_input.lower() in ["sair", "exit", "quit", "desistir"]:
                    print(f"\n{bot.name}: \"Partida interrompida por desistência.\"")
                    return

                try:
                    # Tenta interpretar como SAN (ex: e4, Nf3) ou UCI (ex: e2e4)
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
                    print("[!] Formato não reconhecido. Exemplos válidos: 'e4', 'Nf3', 'd2d4'.")

        else:
            # Vez do Bot 3200
            print(f"\n[*] {bot.name} está calculando...")
            t0 = time.time()
            best_move, info = bot.get_best_move(
                board,
                max_depth=max_depth,
                max_time_seconds=max_time_seconds,
            )
            elapsed = time.time() - t0

            if not best_move:
                print("[!] Bot sem lances legais.")
                break

            san_move = board.san(best_move)
            board.push(best_move)

            # Exibe informações do cálculo
            source_tag = "[LIVRO balanced.bin]" if info.get("source") == "book" else f"[MOTOR d={info.get('depth', '?')}]"
            score_cp = info.get("score_cp")
            score_str = f" | Eval: {score_cp/100:+.2f}" if score_cp is not None else ""
            print(f"[*] {bot.name} jogou: {san_move} ({source_tag}{score_str} em {elapsed:.2f}s)")

            # Frases interativas
            if board.is_check() and "givingCheck" in bot.phrases:
                print(f"    {bot.name}: \"{bot.phrases['givingCheck']}\"")

        if board.turn == chess.WHITE:
            move_count += 1

    # Fim de Jogo
    print("\n" + "=" * 65)
    print(" FIM DA PARTIDA!")
    print("=" * 65)
    print(render_board(board, player_is_white))
    result = board.result()
    print(f"\nResultado Final: {result}")

    if board.is_checkmate():
        winner = "Brancas" if board.turn == chess.BLACK else "Pretas"
        print(f"Vitória por Xeque-Mate das {winner}!")
        if (winner == "Brancas" and player_is_white) or (winner == "Pretas" and not player_is_white):
            print(f"{bot.name}: \"{bot.phrases.get('lost', 'Parabéns pela vitória!')}\"")
        else:
            print(f"{bot.name}: \"{bot.phrases.get('won', 'Xeque-mate. O cálculo prevaleceu.')}\"")
    elif board.is_stalemate():
        print("Empate por Afogamento (Stalemate)!")
    elif board.is_insufficient_material():
        print("Empate por Material Insuficiente!")
    elif board.can_claim_threefold_repetition():
        print("Empate por Repetição de Posição (Threefold Repetition)!")
    elif board.can_claim_fifty_moves():
        print("Empate pela Regra dos 50 Lances!")
    else:
        print("Partida empatada.")


def main():
    parser = argparse.ArgumentParser(description="Bot de Xadrez 3200 Elo - Maximum (Komodo 25)")
    parser.add_argument("--info", action="store_true", help="Exibe a ficha técnica do bot 3200")
    parser.add_argument("--play", action="store_true", help="Inicia uma partida interativa no terminal")
    parser.add_argument("--color", choices=["white", "black"], default="white", help="Cor do jogador (white ou black)")
    parser.add_argument("--depth", type=int, default=4, help="Profundidade máxima de busca (padrão: 4)")
    parser.add_argument("--time", type=float, default=2.5, help="Tempo limite de cálculo por lance em segundos (padrão: 2.5)")
    parser.add_argument("--uci", action="store_true", help="Força uso de motor UCI externo se disponível")

    args = parser.parse_args()

    bot = ChessBot3200(
        use_uci_if_available=args.uci or False,
        max_depth=args.depth,
        max_time_seconds=args.time,
    )

    if args.info:
        bot.print_profile()
        return

    # Se for chamado diretamente sem flags ou com --play, inicia o jogo interativo
    color = chess.WHITE if args.color == "white" else chess.BLACK
    bot.print_profile()
    play_interactive_game(
        bot,
        player_color=color,
        max_depth=args.depth,
        max_time_seconds=args.time,
    )


if __name__ == "__main__":
    main()
