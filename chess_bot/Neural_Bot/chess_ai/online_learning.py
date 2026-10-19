"""Módulo de Aprendizado Online Contínuo para o Neural_Bot.

Garante que TODA partida da qual o Neural_Bot participa (seja contra humano,
contra bot scriptado de qualquer Elo, ou em torneio) se torne experiência
de treinamento imediata, aperfeiçoando os pesos da rede neural via GPU (AMP FP16).
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import torch
import torch.nn as nn
import torch.nn.functional as F

from chess_ai.encoder import encode_board, encode_move
from chess_ai.model import ChessPolicyValueNet


class OnlineLearner:
    """Coletor de partidas e otimizador online para a rede neural."""

    def __init__(
        self,
        model: ChessPolicyValueNet,
        weights_path: Path,
        onnx_path: Optional[Path] = None,
        history_path: Optional[Path] = None,
        lr: float = 3e-4,
        device: Optional[torch.device | str] = None,
    ):
        self.model = model
        self.weights_path = Path(weights_path)
        self.onnx_path = Path(onnx_path) if onnx_path else None
        self.history_path = Path(history_path) if history_path else None

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model.to(self.device)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        self.use_amp = (self.device.type == "cuda")
        self.scaler = torch.amp.GradScaler("cuda", enabled=self.use_amp)

        # Buffer da partida corrente: List of (board_tensor, action_idx, is_neural)
        self.current_trajectory: List[Tuple[torch.Tensor, int, bool]] = []
        self.total_online_games = 0
        self.total_online_positions = 0

    def start_game(self):
        """Reinicia o buffer para o início de uma nova partida."""
        self.current_trajectory.clear()

    def record_move(self, board_before_move: chess.Board, move: chess.Move, is_neural: bool):
        """Registra um lance realizado na partida para treinamento posterior."""
        state_tensor = encode_board(board_before_move).cpu()
        action_idx = encode_move(move, board_before_move.turn)
        self.current_trajectory.append((state_tensor, action_idx, is_neural))

    def evaluate_game_outcome(self, board: chess.Board, neural_is_white: bool) -> Tuple[float, str]:
        """Calcula o resultado formal ou adjudicação técnica por material."""
        if board.is_checkmate():
            winner_is_white = (board.turn == chess.BLACK)
            if (winner_is_white and neural_is_white) or (not winner_is_white and not neural_is_white):
                return 1.0, "Vitória Neural por Xeque-Mate"
            else:
                return -1.0, "Derrota Neural por Xeque-Mate"

        if board.is_stalemate():
            return 0.0, "Empate por Afogamento"
        if board.is_insufficient_material():
            return 0.0, "Empate por Material Insuficiente"
        if board.can_claim_threefold_repetition():
            return 0.0, "Empate por Repetição Tripla"
        if board.can_claim_fifty_moves():
            return 0.0, "Empate pela Regra dos 50 Lances"

        # Adjudicação técnica por saldo de material (se a partida for finalizada sem mate)
        piece_vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
        mat_bal = sum(piece_vals.get(p.piece_type, 0) * (1 if p.color == chess.WHITE else -1) for p in board.piece_map().values())
        neural_mat = mat_bal if neural_is_white else -mat_bal

        if neural_mat >= 300:
            return 1.0, f"Vitória Técnica Neural (+{neural_mat/100:.1f} material)"
        elif neural_mat <= -300:
            return -1.0, f"Derrota Técnica Neural ({neural_mat/100:.1f} material)"
        else:
            return 0.0, f"Empate por Posição Equilibrada ({neural_mat/100:+.1f} material)"

    def learn_from_completed_game(
        self,
        board: chess.Board,
        neural_is_white: bool,
        opponent_name: str = "Oponente",
        epochs: int = 2,
    ) -> Dict[str, Any]:
        """Aplica gradientes imediatos na GPU usando a trajetória da partida encerrada."""
        if not self.current_trajectory:
            return {"trained": False, "reason": "trajetória vazia"}

        outcome, outcome_desc = self.evaluate_game_outcome(board, neural_is_white)

        states = []
        target_policies = []
        target_values = []

        num_actions = 4096
        for state_t, action_idx, is_neural in self.current_trajectory:
            states.append(state_t)
            
            # Alvo de política (One-hot distribution)
            target_p = torch.zeros(num_actions, dtype=torch.float32)
            if 0 <= action_idx < num_actions:
                target_p[action_idx] = 1.0
            target_policies.append(target_p)

            # Se foi o Neural_Bot, o valor mira o outcome final da partida
            # Se foi lance do especialista oponente vencedor, valor positivo incentiva imitação
            if is_neural:
                target_val = outcome
            else:
                target_val = -outcome
            target_values.append(torch.tensor([target_val], dtype=torch.float32))

        batch_states = torch.stack(states).to(self.device)
        batch_policies = torch.stack(target_policies).to(self.device)
        batch_values = torch.stack(target_values).to(self.device)

        self.model.train()
        total_loss = 0.0
        total_p_loss = 0.0
        total_v_loss = 0.0

        for _ in range(epochs):
            self.optimizer.zero_grad()
            if self.use_amp:
                with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                    pred_logits, pred_val = self.model(batch_states)
                    log_probs = F.log_softmax(pred_logits, dim=-1)
                    p_loss = -torch.sum(batch_policies * log_probs, dim=-1).mean()
                    v_loss = F.mse_loss(pred_val, batch_values)
                    loss = p_loss + 0.5 * v_loss

                self.scaler.scale(loss).backward()
                self.scaler.unscale_(self.optimizer)
                nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                pred_logits, pred_val = self.model(batch_states)
                log_probs = F.log_softmax(pred_logits, dim=-1)
                p_loss = -torch.sum(batch_policies * log_probs, dim=-1).mean()
                v_loss = F.mse_loss(pred_val, batch_values)
                loss = p_loss + 0.5 * v_loss

                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()

            total_loss += loss.item()
            total_p_loss += p_loss.item()
            total_v_loss += v_loss.item()

        avg_loss = total_loss / max(1, epochs)
        self.total_online_games += 1
        self.total_online_positions += len(self.current_trajectory)

        # Salvar pesos atualizados
        self.model.save_weights(self.weights_path)
        if self.onnx_path:
            try:
                self.model.export_onnx(self.onnx_path)
            except Exception:
                pass

        # Registrar no histórico online
        history_entry = {
            "timestamp": time.time(),
            "game_number": self.total_online_games,
            "opponent": opponent_name,
            "outcome": outcome,
            "outcome_description": outcome_desc,
            "positions_trained": len(self.current_trajectory),
            "loss": avg_loss,
            "policy_loss": total_p_loss / max(1, epochs),
            "value_loss": total_v_loss / max(1, epochs),
        }

        if self.history_path:
            existing_history = []
            if self.history_path.is_file():
                try:
                    with open(self.history_path, "r", encoding="utf-8") as f:
                        existing_history = json.load(f)
                except Exception:
                    existing_history = []
            existing_history.append(history_entry)
            try:
                with open(self.history_path, "w", encoding="utf-8") as f:
                    json.dump(existing_history[-1000:], f, indent=2)
            except Exception:
                pass

        # Limpar trajetória
        self.current_trajectory.clear()

        return {
            "trained": True,
            "outcome": outcome,
            "outcome_description": outcome_desc,
            "positions_trained": history_entry["positions_trained"],
            "loss": avg_loss,
            "weights_saved": str(self.weights_path),
        }
