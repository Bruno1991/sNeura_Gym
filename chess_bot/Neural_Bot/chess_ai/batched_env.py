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
from .tactics import evaluate_tactical_safety

import random

def encode_boards_batch(boards: List[chess.Board], device: torch.device) -> torch.Tensor:
    """Codifica múltiplos tabuleiros em um único tensor (B, 18, 8, 8) diretamente no dispositivo."""
    tensors = [encode_board(b) for b in boards]
    return torch.stack(tensors).to(device)


class WorkerState:
    """Estado individual de um trabalhador no ambiente paralelo."""

    __slots__ = ("worker_id", "board", "neural_is_white", "game_id", "ply_count", "transitions", "opponent_bot")

    def __init__(self, worker_id: int, neural_is_white: bool, game_id: int, opponent_bot: Any = None):
        self.worker_id = worker_id
        self.board = chess.Board()
        self.neural_is_white = neural_is_white
        self.game_id = game_id
        self.ply_count = 0
        self.opponent_bot = opponent_bot
        # transição: (state_tensor, action_idx, is_neural)
        self.transitions: List[Tuple[torch.Tensor, int, float]] = []

    def reset(self, new_game_id: int, opponent_bot: Any = None):
        """Reinicia o tabuleiro para uma nova partida alternando a cor."""
        self.board.reset()
        self.neural_is_white = not self.neural_is_white
        self.game_id = new_game_id
        self.ply_count = 0
        self.transitions.clear()
        if opponent_bot is not None:
            self.opponent_bot = opponent_bot


import os
from concurrent.futures import ProcessPoolExecutor
from .parallel_engine import compute_engine_move_task


class BatchedChessEnv:
    """Ambiente Paralelo de Partidas Simultâneas com multiprocessamento para oponentes."""

    def __init__(
        self,
        num_workers: int = 64,
        max_plies: int = 80,
        device: Optional[torch.device | str] = None,
        bot_pool: Optional[List[Any]] = None,
        engine_pool_workers: int = 8,
    ):
        self.num_workers = num_workers
        self.max_plies = max_plies
        self.bot_pool = bot_pool or []

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.next_game_id = 1
        self.workers: List[WorkerState] = []
        for i in range(num_workers):
            opp = random.choice(self.bot_pool) if self.bot_pool else None
            w = WorkerState(worker_id=i, neural_is_white=(i % 2 == 0), game_id=self.next_game_id, opponent_bot=opp)
            self.workers.append(w)
            self.next_game_id += 1

        # Pool multiprocessada persistente para bots oponentes na CPU
        num_procs = max(2, min(engine_pool_workers, os.cpu_count() or 8))
        self.engine_pool = ProcessPoolExecutor(max_workers=num_procs)

        # Estatísticas acumuladas
        self.total_completed_games = 0
        self.neural_wins = 0
        self.engine_wins = 0
        self.draws = 0

        # Estatísticas por faixa de Elo
        self.stats_by_tier = {
            "Iniciante (1-900)": {"wins": 0, "losses": 0, "draws": 0},
            "Intermediário (900-1500)": {"wins": 0, "losses": 0, "draws": 0},
            "Avançado (1500-2100)": {"wins": 0, "losses": 0, "draws": 0},
            "Mestre (2100-2700)": {"wins": 0, "losses": 0, "draws": 0},
            "Elite (2700-3200)": {"wins": 0, "losses": 0, "draws": 0},
        }
        self.stats_by_bot: Dict[str, Dict[str, int]] = {}

    def close(self):
        """Encerra a pool de processos do motor adversário."""
        if hasattr(self, "engine_pool") and self.engine_pool:
            try:
                self.engine_pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

    def step_batch(
        self,
        model: ChessPolicyValueNet,
        bot_3200: Any,
        temperature: float = 0.2,
        use_amp: bool = True,
    ) -> List[Tuple[List[Tuple[torch.Tensor, int, float, float]], str, int]]:
        """Avança um passo em todos os trabalhadores simultaneamente com GPU AMP e CPU multiprocessada."""
        completed_games: List[Tuple[List[Tuple[torch.Tensor, int, float, float]], str, int]] = []

        # 1. Identificar trabalhadores cujo turno é do Neural_Bot
        neural_workers: List[WorkerState] = []
        for w in self.workers:
            is_neural_turn = (w.board.turn == chess.WHITE and w.neural_is_white) or (
                w.board.turn == chess.BLACK and not w.neural_is_white
            )
            if is_neural_turn and not w.board.is_game_over(claim_draw=True) and w.ply_count < self.max_plies:
                neural_workers.append(w)

        # 2. Executar inferência neural em lote na GPU com AMP FP16
        if neural_workers:
            batch_states = encode_boards_batch([w.board for w in neural_workers], self.device)
            model.eval()

            with torch.no_grad():
                if use_amp and self.device.type == "cuda":
                    with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                        policy_logits, _ = model(batch_states)
                else:
                    policy_logits, _ = model(batch_states)

            # Vetorização ultra-rápida: extração direta para numpy em batch único
            logits_np = policy_logits.cpu().numpy()

            for i, w in enumerate(neural_workers):
                legal_moves = list(w.board.legal_moves)
                if not legal_moves:
                    continue

                # Softmax vetorizado estritamente sobre ações legais
                turn = w.board.turn
                action_indices = [encode_move(m, turn) for m in legal_moves]
                sub_logits = logits_np[i, action_indices]
                sub_logits = sub_logits - np.max(sub_logits)
                exp_l = np.exp(sub_logits)
                probs = exp_l / np.sum(exp_l)

                scored_moves = []
                opp_r = getattr(w.opponent_bot, "rating", 3200) if w.opponent_bot else 3200
                for j, m in enumerate(legal_moves):
                    p = float(probs[j])
                    idx = action_indices[j]

                    # Verificação tática rápida de arremate e escudo anti-repetição
                    w.board.push(m)
                    if w.board.is_checkmate():
                        p += 50.0
                    elif w.board.is_repetition(2) or w.board.can_claim_threefold_repetition():
                        if opp_r < 2700:
                            p -= 40.0
                    w.board.pop()
                    scored_moves.append((m, p, idx))

                scored_moves.sort(key=lambda x: x[1], reverse=True)

                if temperature > 0.0 and len(scored_moves) > 1 and w.ply_count < 8:
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

        # 3. Identificar e processar trabalhadores cujo turno é do Bot oponente em paralelo
        engine_workers: List[WorkerState] = []
        for w in self.workers:
            is_engine_turn = (w.board.turn == chess.WHITE and not w.neural_is_white) or (
                w.board.turn == chess.BLACK and w.neural_is_white
            )
            if is_engine_turn and not w.board.is_game_over(claim_draw=True) and w.ply_count < self.max_plies:
                engine_workers.append(w)

        if engine_workers:
            tasks = [
                (
                    w.board.fen(),
                    getattr(w.opponent_bot or bot_3200, "rating", 3200),
                    getattr(w.opponent_bot or bot_3200, "name", None),
                    1,
                    0.01,
                )
                for w in engine_workers
            ]
            results = list(self.engine_pool.map(compute_engine_move_task, tasks))

            for w, (m_uci, _) in zip(engine_workers, results):
                engine_move = chess.Move.from_uci(m_uci) if m_uci else None
                if engine_move is None or engine_move not in w.board.legal_moves:
                    legals = list(w.board.legal_moves)
                    if not legals:
                        continue
                    engine_move = legals[0]

                state_t = encode_board(w.board)
                action_idx = encode_move(engine_move, w.board.turn)
                w.transitions.append((state_t, action_idx, 0.0))
                w.board.push(engine_move)
                w.ply_count += 1

        # 4. Avaliar finalizações e reiniciar trabalhadores concluídos
        for w in self.workers:
            is_over = w.board.is_game_over(claim_draw=True) or (w.ply_count >= self.max_plies)
            if is_over:
                active_bot = w.opponent_bot or bot_3200
                opp_name = getattr(active_bot, "name", "Maximum")
                opp_rating = getattr(active_bot, "rating", 3200)

                # Classificar faixa de Elo
                if opp_rating <= 900:
                    tier_name = "Iniciante (1-900)"
                elif opp_rating <= 1500:
                    tier_name = "Intermediário (900-1500)"
                elif opp_rating <= 2100:
                    tier_name = "Avançado (1500-2100)"
                elif opp_rating <= 2700:
                    tier_name = "Mestre (2100-2700)"
                else:
                    tier_name = "Elite (2700-3200)"

                if opp_name not in self.stats_by_bot:
                    self.stats_by_bot[opp_name] = {"rating": opp_rating, "wins": 0, "losses": 0, "draws": 0}

                # Determinar resultado final
                if w.board.is_checkmate():
                    winner_is_white = (w.board.turn == chess.BLACK)
                    if (winner_is_white and w.neural_is_white) or (not winner_is_white and not w.neural_is_white):
                        outcome = 1.0
                        rl_outcome = 1.0
                        res_str = f"Vitória Neural vs {opp_name}"
                        self.neural_wins += 1
                        self.stats_by_tier[tier_name]["wins"] += 1
                        self.stats_by_bot[opp_name]["wins"] += 1
                    else:
                        outcome = -1.0
                        rl_outcome = -1.0
                        res_str = f"Vitória {opp_name} ({opp_rating})"
                        self.engine_wins += 1
                        self.stats_by_tier[tier_name]["losses"] += 1
                        self.stats_by_bot[opp_name]["losses"] += 1
                else:
                    # Avaliação técnica de material (+180 centipawns / peão passado ou iniciativa clara)
                    piece_vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
                    mat_bal = sum(piece_vals.get(p.piece_type, 0) * (1 if p.color == chess.WHITE else -1) for p in w.board.piece_map().values())
                    neural_mat = mat_bal if w.neural_is_white else -mat_bal

                    if neural_mat >= 180:
                        outcome = 1.0
                        rl_outcome = 1.0
                        res_str = f"Vitória Neural vs {opp_name}"
                        self.neural_wins += 1
                        self.stats_by_tier[tier_name]["wins"] += 1
                        self.stats_by_bot[opp_name]["wins"] += 1
                    elif neural_mat <= -180:
                        outcome = -1.0
                        rl_outcome = -1.0
                        res_str = f"Vitória {opp_name} ({opp_rating})"
                        self.engine_wins += 1
                        self.stats_by_tier[tier_name]["losses"] += 1
                        self.stats_by_bot[opp_name]["losses"] += 1
                    else:
                        outcome = 0.0
                        res_str = f"Empate vs {opp_name}"
                        self.draws += 1
                        self.stats_by_tier[tier_name]["draws"] += 1
                        self.stats_by_bot[opp_name]["draws"] += 1

                        # Calibração de recompensa RL anti-empate passivo baseada no Elo do oponente
                        if opp_rating <= 1500:
                            rl_outcome = -0.35  # Penaliza forte empate contra iniciante/intermediário
                        elif opp_rating <= 2100:
                            rl_outcome = -0.15  # Penaliza empate contra jogador de clube
                        elif opp_rating >= 2700:
                            rl_outcome = 0.10   # Bonifica empate resiliente contra Super GM / 3200
                        else:
                            rl_outcome = -0.05  # Leve penalidade contra mestres para forçar vitória

                self.total_completed_games += 1

                # Processar recompensas finais para as transições
                final_transitions: List[Tuple[torch.Tensor, int, float, float]] = []
                for state_t, act_idx, is_neural in w.transitions:
                    target_val = rl_outcome if is_neural > 0.5 else -rl_outcome
                    final_transitions.append((state_t, act_idx, target_val, is_neural))

                completed_games.append((final_transitions, res_str, w.ply_count))

                # Reiniciar imediatamente o trabalhador escolhendo novo oponente se pool ativa
                new_opp = random.choice(self.bot_pool) if self.bot_pool else w.opponent_bot
                w.reset(new_game_id=self.next_game_id, opponent_bot=new_opp)
                self.next_game_id += 1

        return completed_games
