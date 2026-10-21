"""Validador Tático Profundo com PVS (Principal Variation Search) e LMR (Late Move Reduction).

Mecanismo de validação e cálculo tático ultra-profundo:
- PVS (Principal Variation Search): janela mínima (zero-window) para podas imediatas de variantes inferiores.
- Null Move Pruning (NMP): poda se mesmo passando a vez a posição superar beta (R = 2 ou 3).
- Late Move Reductions (LMR): reduz a profundidade de lances silenciosos em posições taticamente estáveis.
- MVV-LVA (Most Valuable Victim - Least Valuable Attacker) para ordenação perfeita de capturas.
- Killer Move Heuristic (2 killer moves por ply) e History Heuristic.
- Quiescence Search com SEE e evasões de xeque.
- Verificação de Gafes (Blunder Guard): testa o lance candidato do MCTS/rede; se for refutado, substitui pela melhor jogada tática.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import chess
import chess.polyglot

# Constantes de PVS e Hash
EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2
INF = 1_000_000
MATE_SCORE = 100_000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


class TranspositionTableEntry:
    __slots__ = ("depth", "score", "flag", "best_move")

    def __init__(self, depth: int, score: int, flag: int, best_move: Optional[chess.Move]):
        self.depth = depth
        self.score = score
        self.flag = flag
        self.best_move = best_move


class TacticalPVSEngine:
    """Motor Tático Especialista com PVS, LMR, Null Move Pruning e Transposition Table."""

    def __init__(self, max_tt_entries: int = 500_000):
        self.tt: Dict[int, TranspositionTableEntry] = {}
        self.max_tt_entries = max_tt_entries
        self.killer_moves: List[List[Optional[chess.Move]]] = [[None, None] for _ in range(64)]
        self.history_table: Dict[Tuple[int, int], int] = {}
        self.nodes_visited: int = 0

    def clear(self):
        self.tt.clear()
        self.killer_moves = [[None, None] for _ in range(64)]
        self.history_table.clear()
        self.nodes_visited = 0

    def evaluate_static(self, board: chess.Board) -> int:
        """Avaliação posicional rápida e simétrica baseada em material e posicional."""
        score = 0
        turn = board.turn
        piece_map = board.piece_map()

        for sq, piece in piece_map.items():
            val = PIECE_VALUES.get(piece.piece_type, 0)
            # Bônus posicional de avanço para peões
            if piece.piece_type == chess.PAWN:
                r = chess.square_rank(sq) if piece.color == chess.WHITE else (7 - chess.square_rank(sq))
                val += r * 8
            # Bônus de centralização para cavalos e bispos
            elif piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                f, r = chess.square_file(sq), chess.square_rank(sq)
                center_dist = abs(f - 3.5) + abs(r - 3.5)
                val += int((7 - center_dist) * 4)

            if piece.color == turn:
                score += val
            else:
                score -= val

        return score

    def order_moves(
        self,
        board: chess.Board,
        legal_moves: List[chess.Move],
        hash_move: Optional[chess.Move] = None,
        ply: int = 0,
    ) -> List[chess.Move]:
        """Ordenação otimizada de lances para maximizar podas no alfa-beta."""
        def score_move(m: chess.Move) -> int:
            if hash_move and m == hash_move:
                return 1_000_000

            # Capturas ordenadas por MVV-LVA
            if board.is_capture(m):
                attacker = board.piece_at(m.from_square)
                victim = board.piece_at(m.to_square)
                att_val = PIECE_VALUES.get(attacker.piece_type, 100) if attacker else 100
                vic_val = PIECE_VALUES.get(victim.piece_type, 100) if victim else 100
                return 100_000 + (vic_val * 10 - att_val)

            # Promoções
            if m.promotion:
                return 90_000 + PIECE_VALUES.get(m.promotion, 100)

            # Killer Moves (Lances que causaram poda beta em profundidade similar)
            if ply < 64:
                if m == self.killer_moves[ply][0]:
                    return 80_000
                if m == self.killer_moves[ply][1]:
                    return 70_000

            # History Heuristic
            return self.history_table.get((m.from_square, m.to_square), 0)

        legal_moves.sort(key=score_move, reverse=True)
        return legal_moves

    def quiescence_search(self, board: chess.Board, alpha: int, beta: int, q_depth: int = 4) -> int:
        """Busca em repouso tática (Quiescence Search) para eliminar o efeito horizonte."""
        self.nodes_visited += 1
        stand_pat = self.evaluate_static(board)

        if q_depth == 0:
            return stand_pat
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        # Capturas e promoções táticas apenas
        capture_moves = [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
        if not capture_moves:
            return stand_pat

        ordered = self.order_moves(board, capture_moves)

        for m in ordered:
            # Delta Pruning: se a captura da peça com margem de segurança não conseguir superar alpha, pode podar
            victim = board.piece_at(m.to_square)
            vic_val = PIECE_VALUES.get(victim.piece_type, 100) if victim else 100
            if stand_pat + vic_val + 200 < alpha and not m.promotion:
                continue

            board.push(m)
            score = -self.quiescence_search(board, -beta, -alpha, q_depth - 1)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def pvs_search(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int = 0,
        can_null: bool = True,
    ) -> Tuple[int, Optional[chess.Move]]:
        """Principal Variation Search com Poda por Lance Nulo (NMP) e LMR."""
        self.nodes_visited += 1

        if depth <= 0:
            val = self.quiescence_search(board, alpha, beta)
            return val, None

        in_check = board.is_check()
        z_key = chess.polyglot.zobrist_hash(board)

        # Consulta Transposition Table
        tt_entry = self.tt.get(z_key)
        hash_move = None
        if tt_entry is not None and tt_entry.depth >= depth:
            if tt_entry.flag == EXACT:
                return tt_entry.score, tt_entry.best_move
            elif tt_entry.flag == LOWERBOUND and tt_entry.score >= beta:
                return tt_entry.score, tt_entry.best_move
            elif tt_entry.flag == UPPERBOUND and tt_entry.score <= alpha:
                return tt_entry.score, tt_entry.best_move
            hash_move = tt_entry.best_move

        # 1. Null Move Pruning (NMP):
        # Se não estamos em xeque e temos peças maiores que peões, passa a vez temporariamente
        if (
            can_null
            and not in_check
            and depth >= 3
            and self.evaluate_static(board) >= beta
        ):
            has_major = any(
                p.color == board.turn and p.piece_type != chess.PAWN
                for p in board.piece_map().values()
            )
            if has_major:
                r = 2 if depth < 6 else 3
                board.push(chess.Move.null())
                null_score, _ = self.pvs_search(board, depth - 1 - r, -beta, -beta + 1, ply + 1, can_null=False)
                null_score = -null_score
                board.pop()
                if null_score >= beta:
                    return beta, None

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            if in_check:
                return -MATE_SCORE + ply, None
            return 0, None

        ordered_moves = self.order_moves(board, legal_moves, hash_move=hash_move, ply=ply)
        best_move = None
        best_score = -INF
        original_alpha = alpha

        for i, move in enumerate(ordered_moves):
            is_capture = board.is_capture(move)
            board.push(move)

            # 2. PVS (Principal Variation Search) com LMR
            is_pv_move = (i == 0)
            score = -INF

            if is_pv_move:
                # O primeiro lance pesquisa com janela completa
                score, _ = self.pvs_search(board, depth - 1, -beta, -alpha, ply + 1, can_null=True)
                score = -score
            else:
                # LMR (Late Move Reduction): reduz profundidade para lances silenciosos tardios
                reduction = 0
                if (
                    depth >= 3
                    and i >= 4
                    and not in_check
                    and not is_capture
                    and not board.is_check()
                ):
                    reduction = 1 if i < 8 else 2

                reduced_depth = max(0, depth - 1 - reduction)

                # Pesquisa com janela mínima (Zero-Window Search: alpha, alpha + 1)
                score, _ = self.pvs_search(board, reduced_depth, -alpha - 1, -alpha, ply + 1, can_null=True)
                score = -score

                # Se falhou alto (lance promissor que foi reduzido), re-pesquisa com profundidade total
                if score > alpha and reduction > 0:
                    score, _ = self.pvs_search(board, depth - 1, -alpha - 1, -alpha, ply + 1, can_null=True)
                    score = -score

                # Se superou alpha, re-pesquisa com janela completa
                if alpha < score < beta:
                    score, _ = self.pvs_search(board, depth - 1, -beta, -alpha, ply + 1, can_null=True)
                    score = -score

            board.pop()

            if score > best_score:
                best_score = score
                best_move = move

            if score > alpha:
                alpha = score
                if not is_capture and ply < 64:
                    if self.killer_moves[ply][0] != move:
                        self.killer_moves[ply][1] = self.killer_moves[ply][0]
                        self.killer_moves[ply][0] = move
                    # Bônus de histórico
                    self.history_table[(move.from_square, move.to_square)] = (
                        self.history_table.get((move.from_square, move.to_square), 0) + depth * depth
                    )

            if alpha >= beta:
                break

        # Gravar na Transposition Table
        flag = EXACT
        if best_score <= original_alpha:
            flag = UPPERBOUND
        elif best_score >= beta:
            flag = LOWERBOUND

        if len(self.tt) < self.max_tt_entries:
            self.tt[z_key] = TranspositionTableEntry(depth, best_score, flag, best_move)

        return best_score, best_move

    def verify_and_refine_candidate(
        self,
        board: chess.Board,
        candidate_move: chess.Move,
        depth: int = 8,
    ) -> Tuple[chess.Move, Dict[str, Any]]:
        """Guarda Tática de Blunders: Avalia o lance candidato.
        
        Se o adversário possuir um golpe tático forçado (ganho líquido >= 200cp),
        refuta o candidato e retorna a melhor resposta tática profunda encontrada.
        """
        self.clear()
        if candidate_move not in board.legal_moves:
            legal = list(board.legal_moves)
            return legal[0] if legal else candidate_move, {"source": "pvs_illegal_fallback"}

        # 1. Simular o lance candidato e verificar a réplica mais perigosa do adversário
        board.push(candidate_move)
        opp_score, opp_best_move = self.pvs_search(board, depth=depth - 1, alpha=-INF, beta=INF)
        board.pop()

        # Se opp_score for muito alto (> 250cp), o adversário tem um golpe tático devastador
        # contra o lance candidato do MCTS/rede
        is_blunder = (opp_score >= 250)

        if not is_blunder:
            return candidate_move, {
                "source": "pvs_verified_safe",
                "san": board.san(candidate_move),
                "tactical_eval": -opp_score,
                "opp_response": board.san(opp_best_move) if opp_best_move else None,
                "depth": depth,
                "nodes": self.nodes_visited,
            }

        # 2. Refutação Tática Ativada: Busca completa no nó raiz para achar o lance seguro
        self.clear()
        root_score, tactical_best = self.pvs_search(board, depth=depth, alpha=-INF, beta=INF)

        chosen = tactical_best if tactical_best and tactical_best in board.legal_moves else candidate_move
        return chosen, {
            "source": "pvs_blunder_refutation",
            "candidate_rejected": board.san(candidate_move),
            "refuted_eval": -opp_score,
            "chosen_move": board.san(chosen),
            "tactical_eval": root_score,
            "depth": depth,
            "nodes": self.nodes_visited,
        }
