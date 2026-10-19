"""Bot de Xadrez Inteligente com Rate/Elo Dinâmico (Chess.com & Engine).

Unifica todos os perfis e níveis de inteligência de xadrez:
- Flag --rate ou --elo determina o nível tático, profundidade e blunder rate.
- Integração direta aos 217 bots oficiais de s_ADB_Tools/bots_data.json com
  personalidades, frases de diálogo e livros de abertura Polyglot (.bin).
- Motor de cálculo tático PeSTO (Piece-Square Tables) e busca Alpha-Beta com Quiescence.
- Suporte a jogo interativo no terminal via --play.
"""

from __future__ import annotations

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

# Suporte a caracteres UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


_BOTS_DATA_CACHE: Optional[List[Dict[str, Any]]] = None


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


def simulate_human_delay(
    info: dict,
    min_delay: float = 0.5,
    max_delay: float = 2.0,
    enabled: bool = True,
    bot_name: str = "Bot",
) -> float:
    """Simula o tempo de reflexão do bot proporcional à complexidade."""
    if not enabled:
        return 0.0

    is_book = info.get("source") == "book"
    if is_book:
        base = random.uniform(0.3, 0.8)
    else:
        base = random.uniform(min_delay, max_delay)

    start = time.time()
    print(f"\n[*] {bot_name} está pensando", end="", flush=True)
    while (time.time() - start) < base:
        time.sleep(0.25)
        print(".", end="", flush=True)

    print("\r" + " " * 55 + "\r", end="", flush=True)
    return time.time() - start


class ChessBot:
    """Bot de xadrez dinâmico cuja inteligência é governada pelo rate/Elo."""

    def __init__(
        self,
        rate: Optional[int] = None,
        target_elo: Optional[int] = None,
        bot_name: Optional[str] = None,
        base_dir: Optional[Path] = None,
        use_uci_if_available: bool = True,
        max_depth: Optional[int] = None,
        max_time_seconds: Optional[float] = None,
    ):
        self.target_elo = rate if rate is not None else target_elo
        self.bot_name = bot_name

        self.base_dir = base_dir or Path(__file__).resolve().parent
        self.assets_dir = self.base_dir / "assets"
        self.s_adb_tools_dir = Path("C:/dev/s_ADB_Tools")

        # Busca bots_data.json localmente em s_Neura_Gym ou em s_ADB_Tools
        candidate_bots_data = [
            self.base_dir.parent / "bots_data.json",
            self.base_dir / "bots_data.json",
            self.s_adb_tools_dir / "bots_data.json",
        ]
        self.bots_data_file = next((p for p in candidate_bots_data if p.is_file()), candidate_bots_data[0])

        # Busca livros polyglot localmente em books/, assets/ ou decompiled_sources
        candidate_book_dirs = [
            self.base_dir.parent / "books",
            self.assets_dir,
            self.s_adb_tools_dir / "decompiled_sources" / "com.chess" / "app" / "src" / "main" / "assets",
        ]
        self.decompiled_assets = next((d for d in candidate_book_dirs if d.is_dir()), candidate_book_dirs[0])

        # Resolver perfil
        self.profile = self._resolve_bot_profile(self.target_elo, self.bot_name)
        self.name: str = self.profile.get("name", "Maximum")
        self.username: str = self.profile.get("username", "Komodo25")
        self.rating: int = int(self.profile.get("rating", 3200))
        self.group_name: str = self.profile.get("groupName", "Engine")
        self.description: str = self.profile.get("description", "")
        self.phrases: Dict[str, str] = self.profile.get("phraseList", {})
        if not self.phrases:
            fallback_json = self.assets_dir / "bot_3200_profile.json"
            if fallback_json.is_file():
                try:
                    with open(fallback_json, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        if d.get("phraseList"):
                            self.phrases = d["phraseList"]
                except Exception:
                    pass
        self.komodo_skill: int = int(self.profile.get("komodoSkillLevel", 25))

        # Calibrar inteligência baseada no rating
        self.calibrated_depth, self.blunder_rate = self._calibrate_engine_for_rate(self.rating)
        self.search_depth = max_depth or self.calibrated_depth
        self.search_time = max_time_seconds or 2.0

        # Motor de busca interno
        self.builtin_searcher = AlphaBetaSearcher(
            max_depth=self.search_depth,
            max_time_seconds=self.search_time,
        )

        # Motor UCI opcional (apenas para ratings de topo >= 2800 se disponível)
        self.uci_wrapper = UCIEngineWrapper()
        self.use_uci = (
            use_uci_if_available
            and self.rating >= 2800
            and self.uci_wrapper.is_available()
        )

        # Livro de abertura Polyglot
        self.polyglot_reader: Optional[chess.polyglot.MemoryMappedReader] = None
        self.active_book_path: Optional[Path] = None
        self.book_name = self.profile.get("book", "balanced")
        self._init_polyglot_book()

        # Propriedades de compatibilidade
        self.book_path = self.active_book_path or (self.assets_dir / "balanced.bin")
        self.profile_path = self.assets_dir / "bot_3200_profile.json"

    def _resolve_bot_profile(self, target_elo: Optional[int], bot_name: Optional[str]) -> Dict[str, Any]:
        """Localiza o perfil correspondente ao rate ou nome solicitado."""
        global _BOTS_DATA_CACHE
        if _BOTS_DATA_CACHE is None:
            _BOTS_DATA_CACHE = []
            if self.bots_data_file.is_file():
                try:
                    with open(self.bots_data_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for g in data.get("botGroups", []):
                            g_name = g.get("name", "Geral")
                            for b in g.get("botPersonalities", []):
                                b_copy = dict(b)
                                b_copy["groupName"] = g_name
                                _BOTS_DATA_CACHE.append(b_copy)
                except Exception:
                    pass
        all_bots = _BOTS_DATA_CACHE

        if not all_bots:
            return {
                "name": "Maximum",
                "username": "Komodo25",
                "rating": 3200,
                "komodoSkillLevel": 25,
                "book": "balanced",
                "phraseList": {
                    "greeting": "Prepare-se para enfrentar a inteligência máxima (Rating 3200).",
                    "won": "Partida concluída. O cálculo prevaleceu.",
                    "lost": "Excelente partida! Uma vitória impressionante.",
                    "givingCheck": "Xeque.",
                },
            }

        # 1. Busca por nome
        if bot_name:
            query = bot_name.strip().lower()
            for b in all_bots:
                if b.get("name", "").lower() == query or b.get("username", "").lower() == query:
                    return b
            for b in all_bots:
                if query in b.get("name", "").lower() or query in b.get("username", "").lower():
                    return b

        # 2. Busca pelo rating mais próximo
        if target_elo is not None:
            return min(all_bots, key=lambda b: abs(int(b.get("rating", 1500)) - target_elo))

        # Padrão: 3200
        for b in all_bots:
            if int(b.get("rating", 0)) == 3200:
                return b
        return all_bots[-1]

    def _calibrate_engine_for_rate(self, rate: int) -> Tuple[int, float]:
        """Define a inteligência (profundidade de cálculo e blunder rate) conforme o rate."""
        if rate <= 400:
            return 1, 0.55   # Iniciante total (Martin = 250)
        elif rate <= 800:
            return 1, 0.35   # Principiante (Aron = 700)
        elif rate <= 1200:
            return 2, 0.18   # Intermediário básico (Nelson = 1300)
        elif rate <= 1600:
            return 2, 0.08   # Intermediário / Clube (Wendy = 1500, Pablo = 1600)
        elif rate <= 2100:
            return 3, 0.02   # Mestre / Avançado (Li = 2000)
        elif rate <= 2600:
            return 3, 0.00   # Grande Mestre (Luk.AI = 2500)
        else:
            return 4, 0.00   # Super GM / Força Máxima (Hikaru = 2820, Maximum = 3200)

    def _init_polyglot_book(self):
        """Carrega o livro Polyglot apropriado para o perfil do bot."""
        book_candidates = []
        if self.book_name:
            clean_name = self.book_name.lower().replace(".bin", "")
            book_candidates.append(self.decompiled_assets / f"{clean_name}.bin")
            book_candidates.append(self.assets_dir / f"{clean_name}.bin")

        book_candidates.append(self.assets_dir / "balanced.bin")
        book_candidates.append(self.decompiled_assets / "balanced.bin")

        for cand in book_candidates:
            if cand.is_file():
                try:
                    self.polyglot_reader = chess.polyglot.open_reader(str(cand))
                    self.active_book_path = cand
                    return
                except Exception:
                    pass

        self.polyglot_reader = None
        self.active_book_path = None

    def get_book_move(self, board: chess.Board) -> Optional[Tuple[chess.Move, int]]:
        """Busca movimento no livro Polyglot do bot."""
        if not self.polyglot_reader:
            return None

        try:
            entries = list(self.polyglot_reader.find_all(board))
            if not entries:
                return None

            weights = [e.weight for e in entries]
            total_w = sum(weights)
            if total_w > 0:
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
        """Determina o melhor lance do bot de acordo com o nível configurado."""
        if board.is_game_over():
            return None, {"source": "game_over"}

        # 1. Livro Polyglot
        book_res = self.get_book_move(board)
        if book_res is not None:
            move, weight = book_res
            return move, {
                "source": "book",
                "book": self.active_book_path.name if self.active_book_path else "polyglot",
                "weight": weight,
                "san": board.san(move),
            }

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None, {"source": "no_legal_moves"}

        # 2. Simulação de Blunder Humano se configurado
        if self.blunder_rate > 0.0 and random.random() < self.blunder_rate:
            blunder_move = self._select_human_blunder(board, legal_moves)
            return blunder_move, {
                "source": "blunder_emulation",
                "rate": self.rating,
                "san": board.san(blunder_move),
            }

        # 3. UCI se habilitado e aplicável
        if self.use_uci:
            t0 = time.time()
            limit_time = max_time_seconds or self.search_time
            uci_move = self.uci_wrapper.best_move(board, time_limit=limit_time)
            if uci_move and uci_move in board.legal_moves:
                return uci_move, {
                    "source": "uci_engine",
                    "time_spent": time.time() - t0,
                    "san": board.san(uci_move),
                }

        # 4. Motor de Busca PeSTO Alpha-Beta
        depth = max_depth or self.search_depth
        calc_time = max_time_seconds or self.search_time
        move, score, d, nodes = self.builtin_searcher.search_best_move(
            board,
            max_depth=depth,
            max_time_seconds=calc_time,
        )

        return move, {
            "source": "builtin_alphabeta",
            "depth": d,
            "score_cp": score,
            "nodes": nodes,
            "san": board.san(move) if move else None,
        }

    def _select_human_blunder(self, board: chess.Board, legal_moves: List[chess.Move]) -> chess.Move:
        """Seleciona um lance imperfeito natural humano condizente com o rating do bot."""
        scored_moves: List[Tuple[chess.Move, int]] = []
        for m in legal_moves:
            board.push(m)
            # Avaliação estática PeSTO sob a perspectiva de quem acabou de jogar
            eval_after = -evaluate_board(board)
            board.pop()
            scored_moves.append((m, eval_after))

        scored_moves.sort(key=lambda x: x[1], reverse=True)

        if self.rating <= 500:
            # Iniciante (ex: Martin 250): comete imprecisões e erros de visão, mas prefere desenvolver peças
            weights = [1.0 / (1.0 + abs(i - len(scored_moves) // 2)) for i in range(len(scored_moves))]
            return random.choices([m for m, _ in scored_moves], weights=weights, k=1)[0]
        elif self.rating <= 1100:
            # Principiante (ex: Aron 700, Maria 1000): escolhe 2º, 3º ou 4º melhor lance (imprecisão)
            n = min(len(scored_moves), 4)
            candidates = scored_moves[1:n] if len(scored_moves) > 1 else scored_moves
            return random.choice([m for m, _ in candidates])
        else:
            # Intermediário (ex: Nelson 1300, Wendy 1500): 2º melhor lance
            return scored_moves[1][0] if len(scored_moves) > 1 else scored_moves[0][0]

    def get_phrase(self, category: str) -> Optional[str]:
        """Retorna frase de diálogo do bot para determinada situação."""
        return self.phrases.get(category)

    def get_phrase_for_event(
        self,
        event_type: str,
        board: Optional[chess.Board] = None,
        last_move: Optional[chess.Move] = None,
        eval_score: Optional[float] = None,
        bot_color: chess.Color = chess.BLACK,
    ) -> Optional[str]:
        """Retorna frase contextual oficial das 39 categorias do Chess.com."""
        if not self.phrases:
            return None

        # 1. Eventos explícitos de ciclo de jogo
        if event_type == "greeting":
            return self.phrases.get("greeting")
        elif event_type == "won":
            return self.phrases.get("won") or self.phrases.get("winning")
        elif event_type == "lost":
            return self.phrases.get("lost") or self.phrases.get("losing")
        elif event_type == "draw":
            return self.phrases.get("draw")

        # 2. Contexto do tabuleiro após o lance
        if board:
            # Xeque
            if board.is_check():
                if board.turn != bot_color:
                    # O bot acabou de aplicar xeque no oponente
                    if "givingCheck" in self.phrases and random.random() < 0.85:
                        return self.phrases["givingCheck"]
                else:
                    # O oponente colocou o bot em xeque
                    if "beingChecked" in self.phrases and random.random() < 0.75:
                        return self.phrases["beingChecked"]

            # Capturas de Dama
            if last_move and board.is_capture(last_move):
                dest_sq = last_move.to_square
                # Se uma dama foi capturada
                if "capturingQueen" in self.phrases and random.random() < 0.70:
                    return self.phrases["capturingQueen"]

            # Lances de Abertura nos primeiros 3 lances
            if board.fullmove_number <= 3:
                opening_map = {
                    "e4": "openingE4",
                    "d4": "openingD4",
                    "c4": "openingC4English",
                    "Nf3": "openingNf3",
                }
                if last_move:
                    try:
                        uci_san = board.san(last_move)
                        for prefix, key in opening_map.items():
                            if uci_san.startswith(prefix) and key in self.phrases:
                                return self.phrases[key]
                    except Exception:
                        pass

            # Vantagem ou Desvantagem expressiva
            if eval_score is not None:
                bot_adv = eval_score if bot_color == chess.WHITE else -eval_score
                if bot_adv >= 3.0 and "winning" in self.phrases and random.random() < 0.40:
                    return self.phrases["winning"]
                elif bot_adv <= -3.0 and "losing" in self.phrases and random.random() < 0.40:
                    return self.phrases["losing"]

        # Frase aleatória ocasional durante a partida
        if "random" in self.phrases and random.random() < 0.20:
            return self.phrases["random"]

        return None


class ChessBot3200(ChessBot):
    """Subclasse de retrocompatibilidade para códigos que esperam ChessBot3200."""

    def __init__(self, *args, **kwargs):
        if "rate" not in kwargs and "target_elo" not in kwargs and len(args) == 0:
            kwargs["target_elo"] = 3200
        super().__init__(*args, **kwargs)


# Alias
ChessComBot = ChessBot


def play_interactive_game(
    bot: ChessBot,
    player_color: chess.Color = chess.WHITE,
    max_depth: Optional[int] = None,
    max_time_seconds: Optional[float] = None,
    human_delay: bool = True,
):
    """Executa partida interativa no terminal contra o bot configurado."""
    board = chess.Board()
    player_is_white = player_color == chess.WHITE

    print("\n" + "=" * 65)
    print(f"  PARTIDA CONTRA: {bot.name.upper()} (Rating {bot.rating} Elo)")
    print(f"  Categoria     : {bot.group_name}")
    if bot.description:
        print(f"  Bio           : \"{bot.description}\"")
    print("=" * 65)

    greeting = bot.get_phrase("greeting")
    if greeting:
        print(f"\n{bot.name}: \"{greeting}\"\n")

    move_count = 1

    while not board.is_game_over():
        print(render_board(board, player_is_white))
        turn_str = "Brancas" if board.turn == chess.WHITE else "Pretas"
        print(f"\nTurno: {turn_str} (Lance {move_count})")

        if board.turn == player_color:
            while True:
                user_input = input("\nSeu lance (ex: e4, Nf3, e2e4 ou 'sair'): ").strip()
                if user_input.lower() in ["sair", "exit", "quit", "desistir"]:
                    print(f"\n{bot.name}: \"Partida interrompida por desistência.\"")
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
                    print("[!] Formato não reconhecido. Exemplos válidos: 'e4', 'Nf3', 'd2d4'.")
        else:
            t0 = time.time()
            best_move, info = bot.get_best_move(
                board,
                max_depth=max_depth,
                max_time_seconds=max_time_seconds,
            )
            calc_elapsed = time.time() - t0

            if not best_move:
                print("[!] Bot sem lances legais.")
                break

            delay_spent = simulate_human_delay(
                info,
                enabled=human_delay,
                bot_name=bot.name,
            )
            total_elapsed = calc_elapsed + delay_spent

            san_move = board.san(best_move)
            board.push(best_move)

            source_tag = f"[LIVRO {info.get('book', 'polyglot')}]" if info.get("source") == "book" else f"[MOTOR d={info.get('depth', '?')}]"
            score_cp = info.get("score_cp")
            score_str = f" | Eval: {score_cp/100:+.2f}" if score_cp is not None else ""
            tempo_exib = f"{total_elapsed:.2f}s" if human_delay else f"{calc_elapsed:.2f}s"
            print(f"[*] {bot.name} jogou: {san_move} ({source_tag}{score_str} em {tempo_exib})")

            if board.is_check() and "givingCheck" in bot.phrases:
                print(f"    {bot.name}: \"{bot.phrases['givingCheck']}\"")

        if board.turn == chess.WHITE:
            move_count += 1

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
            print(f"{bot.name}: \"{bot.phrases.get('won', 'Xeque-mate. Bom jogo!')}\"")
    elif board.is_stalemate():
        print("Empate por Afogamento (Stalemate)!")
    elif board.is_insufficient_material():
        print("Empate por Material Insuficiente!")
    elif board.can_claim_threefold_repetition():
        print("Empate por Repetição Tripla de Posição!")


def list_available_bots(bots_file: Path):
    """Exibe catálogo resumido de bots disponíveis."""
    if not bots_file.is_file():
        print("[!] Arquivo de dados dos bots não encontrado.")
        return

    with open(bots_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\n================== BOTS DISPONÍVEIS DO CHESS.COM ==================")
    for g in data.get("botGroups", []):
        g_name = g.get("name", "Geral")
        print(f"\n--- {g_name.upper()} ---")
        for b in g.get("botPersonalities", []):
            print(f"  * {b.get('name'):<20} | Elo: {b.get('rating'):<5} | Livro: {b.get('book', 'balanced')}")
    print("===================================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Bot de Xadrez Inteligente com Rate/Elo Dinâmico")
    parser.add_argument("rate_or_bot", nargs="?", default=None, help="Elo ou nome do bot (ex: 2500, 1000 ou 'Nelson')")
    parser.add_argument("--rate", "--elo", dest="rate", type=int, default=None, help="Rating desejado (ex: --rate 1000, --rate 2500)")
    parser.add_argument("--bot", type=str, default=None, help="Nome do bot (ex: 'Nelson', 'Hikaru', 'Martin')")
    parser.add_argument("--play", action="store_true", help="Inicia uma partida interativa contra o bot no terminal")
    parser.add_argument("--color", choices=["white", "black"], default="white", help="Sua cor na partida interativa (padrão: white)")
    parser.add_argument("--depth", type=int, default=None, help="Profundidade máxima de busca (sobrescreve a calibração)")
    parser.add_argument("--time", type=float, default=None, help="Tempo máximo de cálculo em segundos")
    parser.add_argument("--no-delay", action="store_true", help="Desativa o tempo de reflexão simulado")
    parser.add_argument("--info", action="store_true", help="Exibe ficha técnica do bot e sai")
    parser.add_argument("--list", action="store_true", help="Lista todos os bots catalogados")

    args = parser.parse_args()

    s_adb_tools = Path("C:/dev/s_ADB_Tools")
    bots_file = s_adb_tools / "bots_data.json"

    if args.list:
        list_available_bots(bots_file)
        return

    target_rate = args.rate
    bot_name = args.bot

    if args.rate_or_bot:
        val = str(args.rate_or_bot).strip()
        if val.isdigit():
            target_rate = int(val)
        else:
            bot_name = val

    if target_rate is None and bot_name is None:
        target_rate = 2500

    bot = ChessBot(rate=target_rate, bot_name=bot_name, max_depth=args.depth, max_time_seconds=args.time)

    if args.info:
        print("\n" + "=" * 55)
        print(f" Nome          : {bot.name}")
        print(f" Rating        : {bot.rating} Elo")
        print(f" Categoria     : {bot.group_name}")
        print(f" Profundidade  : d={bot.calibrated_depth}")
        print(f" Blunder Rate  : {bot.blunder_rate * 100:.0f}%")
        print(f" Livro         : {bot.book_name}.bin")
        if bot.description:
            print(f" Bio           : \"{bot.description}\"")
        greeting = bot.get_phrase("greeting")
        if greeting:
            print(f" Frase         : \"{greeting}\"")
        print("=" * 55 + "\n")
        return

    if args.play:
        player_color = chess.WHITE if args.color == "white" else chess.BLACK
        play_interactive_game(
            bot=bot,
            player_color=player_color,
            max_depth=args.depth,
            max_time_seconds=args.time,
            human_delay=not args.no_delay,
        )
    else:
        # Se nenhum comando especial, exibe ficha e exemplos de uso
        print(f"[*] Bot carregado: {bot.name} ({bot.rating} Elo | d={bot.calibrated_depth})")
        print("    Para jogar interativamente: python chess_bot.py --play --rate " + str(bot.rating))
        print("    Para duelar contra o Neural: python ../Neural_Bot/batalha.py --rate " + str(bot.rating))


if __name__ == "__main__":
    main()
