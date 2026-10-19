"""Módulo de Busca com Alpha-Beta, Transposition Table, Quiescence Search e MVV-LVA.

Implementa um motor de busca de alto desempenho para partidas quando o bot sai
do livro de abertura Polyglot (balanced.bin).
"""

import time
from typing import Dict, List, Optional, Tuple
import chess
import chess.polyglot

from .evaluation import evaluate_board

# Constantes de Pontuação
CHECKMATE_SCORE = 20000
INFINITY = 50000

# Flags da Transposition Table
TT_EXACT = 0
TT_LOWERBOUND = 1  # Beta cutoff (o score real é >= ao score armazenado)
TT_UPPERBOUND = 2  # Fail-low (o score real é <= ao score armazenado)

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


class TranspositionTable:
    """Tabela de transposição em memória usando hashing Zobrist."""

    def __init__(self, max_entries: int = 200_000):
        self.max_entries = max_entries
        self.table: Dict[int, Tuple[int, int, int, Optional[chess.Move]]] = {}

    def clear(self):
        self.table.clear()

    def get(self, key: int) -> Optional[Tuple[int, int, int, Optional[chess.Move]]]:
        return self.table.get(key)

    def store(self, key: int, depth: int, score: int, flag: int, best_move: Optional[chess.Move]):
        if len(self.table) >= self.max_entries:
            # Estratégia simples de limpeza rápida para evitar consumo excessivo de RAM
            self.table.clear()
        self.table[key] = (depth, score, flag, best_move)


class AlphaBetaSearcher:
    """Mecanismo de busca Alpha-Beta minimax com poda e ordenação de movimentos."""

    def __init__(self, max_depth: int = 4, max_time_seconds: float = 3.0):
        self.default_max_depth = max_depth
        self.default_max_time = max_time_seconds
        self.tt = TranspositionTable()
        self.killer_moves: List[List[Optional[chess.Move]]] = [[None, None] for _ in range(64)]
        self.history_table: Dict[Tuple[int, int], int] = {}
        self.nodes_visited = 0
        self.start_time = 0.0
        self.time_limit = 0.0
        self.time_up = False

    def order_moves(
        self,
        board: chess.Board,
        legal_moves: List[chess.Move],
        tt_move: Optional[chess.Move],
        ply: int,
    ) -> List[chess.Move]:
        """Ordena movimentos para maximizar podas beta logo nos primeiros ramos."""
        scored_moves = []
        for move in legal_moves:
            score = 0
            # 1. Movimento da Transposition Table (Hash Move)
            if tt_move and move == tt_move:
                score += 300_000

            # 2. Capturas ordenadas por MVV-LVA (Most Valuable Victim - Least Valuable Attacker)
            elif board.is_capture(move):
                captured_piece = board.piece_at(move.to_square)
                attacker_piece = board.piece_at(move.from_square)
                victim_val = PIECE_VALUES.get(captured_piece.piece_type, 100) if captured_piece else 100
                attacker_val = PIECE_VALUES.get(attacker_piece.piece_type, 100) if attacker_piece else 100
                score += 100_000 + (victim_val * 10 - attacker_val)

            # 3. Promoções de Peão
            elif move.promotion:
                score += 90_000 + PIECE_VALUES.get(move.promotion, 0)

            # 4. Killer Moves (movimentos silenciosos que causaram poda recentemente no mesmo ply)
            elif ply < 64 and move in self.killer_moves[ply]:
                score += 80_000

            # 5. History Heuristic (movimentos bem-sucedidos em nós irmãos)
            else:
                score += self.history_table.get((move.from_square, move.to_square), 0)

            scored_moves.append((score, move))

        scored_moves.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored_moves]

    def quiescence_search(self, board: chess.Board, alpha: int, beta: int, ply: int) -> int:
        """Busca de quiescência: continua avaliando capturas para eliminar o efeito horizonte."""
        self.nodes_visited += 1

        if self.nodes_visited % 64 == 0:
            if time.time() - self.start_time > self.time_limit:
                self.time_up = True
                return evaluate_board(board)

        stand_pat = evaluate_board(board)
        if ply > 3:
            return stand_pat

        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        # Delta pruning: se nem com captura da dama bate o alpha, ignora ramos fracos
        if stand_pat + 950 < alpha:
            return alpha

        # Analisar apenas capturas legais
        legal_captures = [m for m in board.legal_moves if board.is_capture(m)]
        ordered_captures = self.order_moves(board, legal_captures, None, ply)

        for move in ordered_captures:
            board.push(move)
            score = -self.quiescence_search(board, -beta, -alpha, ply + 1)
            board.pop()

            if self.time_up:
                return stand_pat

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def alpha_beta(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
    ) -> Tuple[int, Optional[chess.Move]]:
        """Busca minimax com poda Alpha-Beta e Transposition Table."""
        self.nodes_visited += 1

        if self.nodes_visited % 64 == 0:
            if time.time() - self.start_time > self.time_limit:
                self.time_up = True
                return evaluate_board(board), None

        # Verificação de fim de jogo
        if board.is_checkmate():
            return -CHECKMATE_SCORE + ply, None
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            return 0, None

        # Base da recursão: desce para busca de quiescência
        if depth <= 0:
            return self.quiescence_search(board, alpha, beta, ply), None

        zobrist = chess.polyglot.zobrist_hash(board)
        tt_entry = self.tt.get(zobrist)
        tt_move = None

        if tt_entry:
            stored_depth, stored_score, flag, stored_move = tt_entry
            tt_move = stored_move
            if stored_depth >= depth:
                if flag == TT_EXACT:
                    return stored_score, stored_move
                elif flag == TT_LOWERBOUND and stored_score >= beta:
                    return stored_score, stored_move
                elif flag == TT_UPPERBOUND and stored_score <= alpha:
                    return stored_score, stored_move

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            if board.is_check():
                return -CHECKMATE_SCORE + ply, None
            return 0, None

        ordered_moves = self.order_moves(board, legal_moves, tt_move, ply)

        best_score = -INFINITY
        best_move = ordered_moves[0]
        original_alpha = alpha

        for move in ordered_moves:
            board.push(move)
            score, _ = self.alpha_beta(board, depth - 1, -beta, -alpha, ply + 1)
            score = -score
            board.pop()

            if self.time_up:
                return best_score if best_score != -INFINITY else evaluate_board(board), best_move

            if score > best_score:
                best_score = score
                best_move = move

            if score > alpha:
                alpha = score

            if alpha >= beta:
                # Poda Beta!
                if not board.is_capture(move) and ply < 64:
                    self.killer_moves[ply][1] = self.killer_moves[ply][0]
                    self.killer_moves[ply][0] = move
                    key = (move.from_square, move.to_square)
                    self.history_table[key] = self.history_table.get(key, 0) + depth * depth
                break

        # Gravação na Transposition Table
        flag = TT_EXACT
        if best_score <= original_alpha:
            flag = TT_UPPERBOUND
        elif best_score >= beta:
            flag = TT_LOWERBOUND

        self.tt.store(zobrist, depth, best_score, flag, best_move)
        return best_score, best_move

    def search_best_move(
        self,
        board: chess.Board,
        max_depth: Optional[int] = None,
        max_time_seconds: Optional[float] = None,
    ) -> Tuple[Optional[chess.Move], int, int, int]:
        """Aprofundamento iterativo (Iterative Deepening).
        
        Retorna: (best_move, evaluation_score, depth_achieved, nodes_searched)
        """
        depth_target = max_depth or self.default_max_depth
        self.time_limit = max_time_seconds or self.default_max_time
        self.start_time = time.time()
        self.time_up = False
        self.nodes_visited = 0

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None, 0, 0, 0

        best_move = legal_moves[0]
        best_score = 0
        depth_achieved = 1

        # Iterative Deepening de profundidade 1 até depth_target
        for d in range(1, depth_target + 1):
            score, move = self.alpha_beta(board, d, -INFINITY, INFINITY, 0)
            if self.time_up:
                break

            if move:
                best_move = move
                best_score = score
                depth_achieved = d

            # Se encontrou mate iminente, interrompe busca mais profunda
            if abs(best_score) > CHECKMATE_SCORE - 100:
                break

        return best_move, best_score, depth_achieved, self.nodes_visited
