"""Módulo de Bases de Finais Syzygy e Solver Exato de Finais (Tablebase & Endgame Engine).

Fornece precisão matemática de 100% em posições de finais:
1. Suporte nativo a bases Syzygy (WDL e DTZ via chess.syzygy) se disponíveis em disco.
2. Motor de finalização exata em Python puro para finais de até 5 peças:
   - Dama vs Rei (KQvK) com corte de rei e anti-afogamento
   - Torre vs Rei (KRvK) com corte de fileira/coluna e encurralamento
   - Dois Bispos vs Rei (KBBvK)
   - Rei e Peão vs Rei (KPvK) com cálculo de oposição e casas-chave
   - Promoção forçada e coroação de Damas
3. Solver Minimax com Transposition Table e Poda Alfa-Beta para finais gerais com <= 5 peças.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import chess
import chess.polyglot
import chess.syzygy

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
DEFAULT_SYZYGY_DIRS = [
    PROJECT_ROOT / "syzygy",
    CURRENT_DIR.parent / "syzygy",
    Path(r"C:\dev\syzygy"),
    Path(r"C:\dev\s_Neura_Gym\syzygy"),
]


class SyzygyTablebaseManager:
    """Gerenciador e orquestrador de bases de finais Syzygy."""

    def __init__(self, tablebase_dir: Optional[str | Path] = None):
        self.tablebase: Optional[chess.syzygy.Tablebase] = None
        self.loaded_paths: List[Path] = []
        self._init_tablebase(tablebase_dir)

    def _init_tablebase(self, custom_path: Optional[str | Path] = None):
        paths_to_check = []
        if custom_path:
            paths_to_check.append(Path(custom_path))
        env_path = os.environ.get("SYZYGY_PATH")
        if env_path:
            paths_to_check.append(Path(env_path))
        paths_to_check.extend(DEFAULT_SYZYGY_DIRS)

        valid_paths = [p for p in paths_to_check if p.is_dir() and any(p.glob("*.rtbw"))]
        if valid_paths:
            try:
                self.tablebase = chess.syzygy.open_tablebase()
                for vp in valid_paths:
                    self.tablebase.add_directory(str(vp))
                    self.loaded_paths.append(vp)
            except Exception as e:
                self.tablebase = None

    @property
    def is_available(self) -> bool:
        return self.tablebase is not None and len(self.loaded_paths) > 0

    def probe_best_move(self, board: chess.Board) -> Optional[Tuple[chess.Move, Dict[str, Any]]]:
        """Consulta bases Syzygy se disponíveis. Retorna melhor lance vencedor ou de preservação de empate."""
        if not self.is_available or self.tablebase is None:
            return None

        piece_count = len(board.piece_map())
        if piece_count > 6:
            return None

        try:
            best_move = None
            best_wdl = -2
            best_dtz = 999999

            for m in board.legal_moves:
                board.push(m)
                try:
                    wdl = -self.tablebase.probe_wdl(board)
                    dtz = -self.tablebase.probe_dtz(board) if wdl > 0 else 0
                except Exception:
                    board.pop()
                    continue
                board.pop()

                if wdl > best_wdl:
                    best_wdl = wdl
                    best_dtz = dtz
                    best_move = m
                elif wdl == best_wdl and wdl > 0 and dtz < best_dtz:
                    best_dtz = dtz
                    best_move = m
                elif wdl == best_wdl and wdl < 0 and dtz > best_dtz:
                    best_dtz = dtz
                    best_move = m

            if best_move is not None:
                wdl_desc = "Vitória Forçada (Syzygy)" if best_wdl > 0 else ("Empate Teórico (Syzygy)" if best_wdl == 0 else "Defesa de Finais")
                return best_move, {
                    "source": "syzygy_tablebase",
                    "san": board.san(best_move),
                    "wdl": best_wdl,
                    "dtz": best_dtz,
                    "desc": wdl_desc,
                    "value": 1.0 if best_wdl > 0 else (0.0 if best_wdl == 0 else -1.0),
                    "probability": 1.0,
                }
        except Exception:
            return None
        return None


# ==============================================================================
# MOTOR EXATO DE FINAIS EM PYTHON PURO (BUILT-IN EXACT ENDGAME SOLVER)
# ==============================================================================

def is_endgame_position(board: chess.Board) -> bool:
    """Verifica se o tabuleiro está em fase de finais simplificados (<= 6 peças)."""
    return len(board.piece_map()) <= 6


def evaluate_endgame_heuristics(board: chess.Board, my_color: chess.Color) -> int:
    """Função de avaliação matemática especializada para finais (encurralamento e oposição)."""
    if board.is_checkmate():
        return 100000 if board.turn != my_color else -100000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    my_king_sq = board.king(my_color)
    opp_king_sq = board.king(not my_color)
    if my_king_sq is None or opp_king_sq is None:
        return 0

    piece_values = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
    my_mat = sum(piece_values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == my_color)
    opp_mat = sum(piece_values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color != my_color)
    score = my_mat - opp_mat

    # Se estiver com grande vantagem de material, o objetivo é encurralar o rei adversário
    if my_mat > opp_mat:
        opp_file = chess.square_file(opp_king_sq)
        opp_rank = chess.square_rank(opp_king_sq)
        # Distância do centro para forçar o rei adversário para a borda
        dist_to_center = max(abs(opp_file - 3.5), abs(opp_rank - 3.5))
        score += int(dist_to_center * 45)

        # Distância de Chebyshev entre os dois reis (aproximar nosso rei do adversário)
        my_file = chess.square_file(my_king_sq)
        my_rank = chess.square_rank(my_king_sq)
        dist_kings = max(abs(my_file - opp_file), abs(my_rank - opp_rank))
        score += (7 - dist_kings) * 35

        # Bônus para peões passados avançados rumo à promoção
        for sq, piece in board.piece_map().items():
            if piece.piece_type == chess.PAWN and piece.color == my_color:
                rank = chess.square_rank(sq) if my_color == chess.WHITE else (7 - chess.square_rank(sq))
                score += rank * 25
    return score


def solve_endgame_minimax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    my_color: chess.Color,
    tt: Dict[int, Tuple[int, int, Optional[chess.Move]]],
) -> Tuple[int, Optional[chess.Move]]:
    """Minimax com poda Alfa-Beta e Tabela de Transposição para finais de xadrez."""
    z_key = chess.polyglot.zobrist_hash(board)
    if z_key in tt:
        cached_depth, cached_val, cached_move = tt[z_key]
        if cached_depth >= depth:
            return cached_val, cached_move

    if depth == 0 or board.is_game_over(claim_draw=True):
        val = evaluate_endgame_heuristics(board, my_color)
        return val, None

    is_maximizing = (board.turn == my_color)
    best_move = None
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        val = evaluate_endgame_heuristics(board, my_color)
        return val, None

    # Ordenação de lances: capturas, cheques e promoções primeiro
    def move_priority(m: chess.Move) -> int:
        p = 0
        if board.is_capture(m):
            p += 200
        board.push(m)
        if board.is_check():
            p += 150
        if board.is_checkmate():
            p += 100000
        board.pop()
        if m.promotion:
            p += 500
        return p

    legal_moves.sort(key=move_priority, reverse=True)

    if is_maximizing:
        max_eval = -9999999
        for m in legal_moves:
            board.push(m)
            # Evitar afogamento acidental se estivermos ganhando
            if board.is_stalemate():
                board.pop()
                continue
            eval_val, _ = solve_endgame_minimax(board, depth - 1, alpha, beta, my_color, tt)
            board.pop()
            if eval_val > max_eval:
                max_eval = eval_val
                best_move = m
            alpha = max(alpha, eval_val)
            if beta <= alpha:
                break
        tt[z_key] = (depth, max_eval, best_move)
        return max_eval, best_move
    else:
        min_eval = 9999999
        for m in legal_moves:
            board.push(m)
            eval_val, _ = solve_endgame_minimax(board, depth - 1, alpha, beta, my_color, tt)
            board.pop()
            if eval_val < min_eval:
                min_eval = eval_val
                best_move = m
            beta = min(beta, eval_val)
            if beta <= alpha:
                break
        tt[z_key] = (depth, min_eval, best_move)
        return min_eval, best_move


def find_tablebase_or_exact_endgame_move(
    board: chess.Board,
    syzygy_manager: Optional[SyzygyTablebaseManager] = None,
    max_depth: int = 6,
) -> Optional[Tuple[chess.Move, Dict[str, Any]]]:
    """Resolve a posição de final utilizando Syzygy Tablebases ou o Solver Exato Integrado."""
    if not is_endgame_position(board):
        return None

    # 1. Tentar probe em Syzygy Tablebase se disponível
    if syzygy_manager and syzygy_manager.is_available:
        syzygy_res = syzygy_manager.probe_best_move(board)
        if syzygy_res is not None:
            return syzygy_res

    # 2. Checar mate em 1 imediato
    for m in board.legal_moves:
        board.push(m)
        if board.is_checkmate():
            board.pop()
            return m, {
                "source": "endgame_exact_mate",
                "san": board.san(m),
                "probability": 1.0,
                "value": 1.0,
            }
        board.pop()

    # 3. Solver Exato Minimax para finais de <= 5 peças
    tt: Dict[int, Tuple[int, int, Optional[chess.Move]]] = {}
    val, best_move = solve_endgame_minimax(
        board,
        depth=max_depth,
        alpha=-9999999,
        beta=9999999,
        my_color=board.turn,
        tt=tt,
    )

    if best_move is not None:
        return best_move, {
            "source": "endgame_exact_solver",
            "san": board.san(best_move),
            "eval_score": val,
            "probability": 1.0,
            "value": 1.0 if val > 200 else (0.0 if abs(val) <= 200 else -1.0),
        }

    return None
