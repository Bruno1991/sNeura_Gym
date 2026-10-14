"""Ambiente Paralelo de Xadrez Vetorizado (BatchedChessEnv).

Gerencia 64 (ou N) partidas de xadrez em paralelo simultaneamente,
vetorizando a codificação dos tabuleiros para inferência em lote na GPU
e mantendo um fluxo contínuo onde trabalhadores finalizados reiniciam imediatamente.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
import chess
import numpy as np
import torch
import torch.nn.functional as F

from .encoder import ACTION_SIZE, NUM_CHANNELS, encode_board, encode_move, get_legal_action_mask
from .model import ChessPolicyValueNet


def encode_boards_batch(boards: List[chess.Board], device: torch.device) -> torch.Tensor:
    """Codifica múltiplos tabuleiros em um único tensor (B, 18, 8, 8) diretamente no dispositivo."""
    tensors = [encode_board(b) for b in boards]
    return torch.stack(tensors).to(device)


class WorkerState:
    """Estado individual de um trabalhador no ambiente paralelo."""

    __slots__ = ("worker_id", "board", "neural_is_white", "game_id", "ply_count", "transitions")

    def __init__(self, worker_id: int, neural_is_white: bool, game_id: int):
        self.worker_id = worker_id
        self.board = chess.Board()
        self.neural_is_white = neural_is_white
        self.game_id = game_id
        self.ply_count = 0
        # transição: (state_tensor, action_idx, is_neural)
        self.transitions: List[Tuple[torch.Tensor, int, float]] = []

    def reset(self, new_game_id: int):
        """Reinicia o tabuleiro para uma nova partida alternando a cor."""
        self.board.reset()
        self.neural_is_white = not self.neural_is_white
        self.game_id = new_game_id
        self.ply_count = 0
        self.transitions.clear()


class BatchedChessEnv:
    """Ambiente Paralelo de 64 Partidas Simultâneas."""

    def __init__(
        self,
        num_workers: int = 64,
        max_plies: int = 70,
        device: Optional[torch.device | str] = None,
    ):
        self.num_workers = num_workers
        self.max_plies = max_plies

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.next_game_id = 1
        self.workers: List[WorkerState] = []
        for i in range(num_workers):
            # Trabalhadores pares começam de brancas, ímpares de pretas
            w = WorkerState(worker_id=i, neural_is_white=(i % 2 == 0), game_id=self.next_game_id)
            self.workers.append(w)
            self.next_game_id += 1

        # Estatísticas acumuladas
        self.total_completed_games = 0
        self.neural_wins = 0
        self.engine_wins = 0
        self.draws = 0

    def step_batch(
        self,
        model: ChessPolicyValueNet,
        bot_3200: Any,
        temperature: float = 0.2,
        use_amp: bool = True,
    ) -> List[Tuple[List[Tuple[torch.Tensor, int, float, float]], str, int]]:
        """Avança um passo em todos os 64 trabalhadores simultaneamente.
        
        Processa os lances neurais em lote (batch tensor na GPU com AMP FP16)
        e os lances do bot de 3200 Elo.
        
        Retorna:
            Lista de partidas concluídas neste passo:
            [(transições_finais, resultado_str, plies_totais), ...]
        """
        completed_games: List[Tuple[List[Tuple[torch.Tensor, int, float, float]], str, int]] = []

        # 1. Identificar trabalhadores cujo turno é do Neural_Bot
        neural_workers: List[WorkerState] = []
        for w in self.workers:
            is_neural_turn = (w.board.turn == chess.WHITE and w.neural_is_white) or (
                w.board.turn == chess.BLACK and not w.neural_is_white
            )
            if is_neural_turn and not w.board.is_game_over(claim_draw=True) and w.ply_count < self.max_plies:
                neural_workers.append(w)

        # 2. Executar inferência neural em lote na GPU
        if neural_workers:
            batch_states = encode_boards_batch([w.board for w in neural_workers], self.device)
            model.eval()

            with torch.no_grad():
                if use_amp and self.device.type == "cuda":
                    with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                        policy_logits, _ = model(batch_states)
                else:
                    policy_logits, _ = model(batch_states)

            # Processar cada trabalhador neural
            for i, w in enumerate(neural_workers):
                logits = policy_logits[i]
                mask = get_legal_action_mask(w.board).to(self.device)
                masked_logits = torch.where(mask, logits, torch.tensor(-1e9, device=self.device))
                probs = F.softmax(masked_logits, dim=-1).cpu().numpy()

                legal_moves = list(w.board.legal_moves)
                if not legal_moves:
                    continue

                scored_moves = []
                for m in legal_moves:
                    idx = encode_move(m, w.board.turn)
                    p = float(probs[idx])
                    # Verificação tática rápida: se dá mate, prioridade total
                    w.board.push(m)
                    if w.board.is_checkmate():
                        p += 50.0
                    w.board.pop()
                    scored_moves.append((m, p, idx))

                scored_moves.sort(key=lambda x: x[1], reverse=True)

                if temperature > 0.0 and len(scored_moves) > 1 and w.ply_count < 10:
                    cand_moves = scored_moves[:4]
                    cand_probs = np.array([p for _, p, _ in cand_moves], dtype=np.float64)
                    cand_probs = np.power(np.maximum(cand_probs, 1e-8), 1.0 / temperature)
                    cand_probs /= cand_probs.sum()
                    chosen_idx = np.random.choice(len(cand_moves), p=cand_probs)
                    chosen_move, _, action_idx = cand_moves[chosen_idx]
                else:
                    chosen_move, _, action_idx = scored_moves[0]

                # Salvar transição neural
                state_t = batch_states[i].cpu()
                w.transitions.append((state_t, action_idx, 1.0))
                w.board.push(chosen_move)
                w.ply_count += 1

        # 3. Identificar e processar trabalhadores cujo turno é do Bot 3200
        engine_workers: List[WorkerState] = []
        for w in self.workers:
            is_engine_turn = (w.board.turn == chess.WHITE and not w.neural_is_white) or (
                w.board.turn == chess.BLACK and w.neural_is_white
            )
            if is_engine_turn and not w.board.is_game_over(claim_draw=True) and w.ply_count < self.max_plies:
                engine_workers.append(w)

        for w in engine_workers:
            # Bot 3200: consulta livro balanced.bin ou motor rápido PeSTO d=1..2
            engine_move, _ = bot_3200.get_best_move(w.board, max_depth=2, max_time_seconds=0.03)
            if engine_move is None or engine_move not in w.board.legal_moves:
                legals = list(w.board.legal_moves)
                if not legals:
                    continue
                engine_move = legals[0]

            state_t = encode_board(w.board)
            action_idx = encode_move(engine_move, w.board.turn)
            # Salvar transição do especialista (DAgger target)
            w.transitions.append((state_t, action_idx, 0.0))
            w.board.push(engine_move)
            w.ply_count += 1

        # 4. Avaliar finalizações e reiniciar trabalhadores concluídos
        for w in self.workers:
            is_over = w.board.is_game_over(claim_draw=True) or (w.ply_count >= self.max_plies)
            if is_over:
                # Determinar resultado final
                if w.board.is_checkmate():
                    winner_is_white = (w.board.turn == chess.BLACK)
                    if (winner_is_white and w.neural_is_white) or (not winner_is_white and not w.neural_is_white):
                        outcome = 1.0
                        res_str = "Vitória Neural"
                        self.neural_wins += 1
                    else:
                        outcome = -1.0
                        res_str = "Vitória Maximum 3200"
                        self.engine_wins += 1
                else:
                    outcome = 0.0
                    res_str = "Empate"
                    self.draws += 1

                self.total_completed_games += 1

                # Processar recompensas finais para as transições
                final_transitions: List[Tuple[torch.Tensor, int, float, float]] = []
                for state_t, act_idx, is_neural in w.transitions:
                    target_val = outcome if is_neural > 0.5 else -outcome
                    final_transitions.append((state_t, act_idx, target_val, is_neural))

                completed_games.append((final_transitions, res_str, w.ply_count))

                # Reiniciar imediatamente o trabalhador para manter ocupação de 100%
                w.reset(new_game_id=self.next_game_id)
                self.next_game_id += 1

        return completed_games
