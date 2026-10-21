"""Pipeline de Auto-Aperfeiçoamento por Reforço (Self-Play AlphaZero Engine).

Gera partidas onde o Neural_Bot joga contra si mesmo, extraindo:
- Distribuição de visitas do MCTS como alvo de política (policy target pi)
- Desfecho real da partida como alvo de valor (value target z in {-1, 0, +1})
- Otimização por gradiente descendente com AMP FP16 para elevar o Elo além de 3300+.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import chess
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from .encoder import ACTION_SIZE, NUM_CHANNELS, encode_board, encode_move
from .mcts import NeuralMCTS
from .model import ChessPolicyValueNet


class SelfPlayDataset(torch.utils.data.Dataset):
    """Dataset para amostras e trajetórias de auto-jogo (Self-Play AlphaZero)."""

    def __init__(self, max_samples: int = 50_000):
        self.max_samples = max_samples
        self.samples: List[Tuple[torch.Tensor, np.ndarray, float]] = []

    def add_sample(self, state: torch.Tensor, policy: np.ndarray, value: float):
        if len(self.samples) >= self.max_samples:
            self.samples.pop(0)
        self.samples.append((state, policy, value))

    def add_trajectory(self, boards: List[chess.Board], target_pis: List[Dict[str, float]], outcome: float):
        for b, pi_dict in zip(boards, target_pis):
            state_t = encode_board(b)
            pi_vec = np.zeros(ACTION_SIZE, dtype=np.float32)
            for m in b.legal_moves:
                san = b.san(m)
                if san in pi_dict:
                    idx = encode_move(m, b.turn)
                    pi_vec[idx] = float(pi_dict[san])
            s = pi_vec.sum()
            if s > 0:
                pi_vec /= s
            val = outcome if b.turn == chess.WHITE else -outcome
            self.add_sample(state_t, pi_vec, val)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        state, policy, value = self.samples[idx]
        return {
            "state": state,
            "target_policy": torch.tensor(policy, dtype=torch.float32),
            "target_value": torch.tensor([value], dtype=torch.float32),
        }


class SelfPlayTrainer:
    """Orquestrador de auto-jogo e treinamento por reforço contínuo."""

    def __init__(
        self,
        model: ChessPolicyValueNet,
        weights_path: str | Path,
        device: Optional[torch.device | str] = None,
        lr: float = 0.0005,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = model.to(self.device)
        self.weights_path = Path(weights_path)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        self.mcts = NeuralMCTS(self.model, device=self.device, c_puct=2.0)

    def play_self_play_game(self, sims: int = 60, max_moves: int = 120) -> List[Tuple[torch.Tensor, np.ndarray, chess.Color]]:
        """Executa uma partida completa de auto-jogo com exploração estocástica."""
        board = chess.Board()
        game_history: List[Tuple[torch.Tensor, np.ndarray, chess.Color]] = []
        move_count = 0

        while not board.is_game_over(claim_draw=True) and move_count < max_moves:
            temp = 1.0 if move_count < 15 else 0.2
            state_tensor = encode_board(board)

            best_move, stats = self.mcts.search(
                board,
                num_simulations=sims,
                temperature=temp,
                add_noise=True,
                batch_size=8,
            )

            if best_move is None:
                break

            # Montar vetor de alvo de política (4096)
            pi_target = np.zeros(ACTION_SIZE, dtype=np.float32)
            visits = stats.get("visits", {})
            for m in board.legal_moves:
                san = board.san(m)
                cnt = visits.get(san, 0)
                idx = encode_move(m, board.turn)
                pi_target[idx] = float(cnt)

            pi_sum = pi_target.sum()
            if pi_sum > 0:
                pi_target /= pi_sum

            game_history.append((state_tensor, pi_target, board.turn))
            board.push(best_move)
            move_count += 1

        # Determinar desfecho final da perspectiva das Brancas
        res = board.result(claim_draw=True)
        if res == "1-0":
            white_outcome = 1.0
        elif res == "0-1":
            white_outcome = -1.0
        else:
            white_outcome = 0.0

        training_samples = []
        for state_t, pi, turn in game_history:
            val_target = white_outcome if turn == chess.WHITE else -white_outcome
            training_samples.append((state_t, pi, val_target))

        return training_samples

    def train_on_samples(self, samples: List[Tuple[torch.Tensor, np.ndarray, float]], batch_size: int = 32, epochs: int = 2) -> Dict[str, float]:
        """Treina a rede neural nos exemplos coletados de auto-jogo."""
        if not samples:
            return {"loss": 0.0}

        random.shuffle(samples)
        self.model.train()

        total_loss = 0.0
        batches_count = 0

        states = torch.stack([s[0] for s in samples])
        policies = torch.tensor(np.array([s[1] for s in samples]), dtype=torch.float32)
        values = torch.tensor([[s[2]] for s in samples], dtype=torch.float32)

        dataset = torch.utils.data.TensorDataset(states, policies, values)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

        for _ in range(epochs):
            for b_states, b_policies, b_values in loader:
                b_states = b_states.to(self.device)
                b_policies = b_policies.to(self.device)
                b_values = b_values.to(self.device)

                self.optimizer.zero_grad()

                if self.device.type == "cuda":
                    with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                        pred_logits, pred_val = self.model(b_states)
                        log_probs = F.log_softmax(pred_logits, dim=-1)
                        loss_policy = -(b_policies * log_probs).sum(dim=-1).mean()
                        loss_value = F.mse_loss(pred_val, b_values)
                        loss = loss_policy + loss_value
                else:
                    pred_logits, pred_val = self.model(b_states)
                    log_probs = F.log_softmax(pred_logits, dim=-1)
                    loss_policy = -(b_policies * log_probs).sum(dim=-1).mean()
                    loss_value = F.mse_loss(pred_val, b_values)
                    loss = loss_policy + loss_value

                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()

                total_loss += float(loss.item())
                batches_count += 1

        self.model.eval()
        self.model.save_weights(self.weights_path)

        avg_loss = total_loss / max(1, batches_count)
        return {
            "avg_loss": avg_loss,
            "samples_trained": len(samples),
            "batches": batches_count,
        }
