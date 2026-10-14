"""Testes unitários para o módulo RLChessTrainer."""

import pytest
import chess
import torch
from pathlib import Path

from chess_ai.model import ChessPolicyValueNet
from chess_ai.rl_trainer import RLChessTrainer


class DummyBot:
    def get_best_move(self, board, max_depth=1, max_time_seconds=0.01):
        moves = list(board.legal_moves)
        return moves[0] if moves else None, {"source": "dummy"}


def test_rl_trainer_single_game_and_training():
    """Valida execução de partida única e passo de treino na GPU/CPU."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    dummy_bot = DummyBot()

    trainer = RLChessTrainer(model=model, bot_3200=dummy_bot, device="cpu")

    res, plies, transitions = trainer.play_single_game(game_id=1, neural_is_white=True, max_plies=10)
    assert plies > 0
    assert len(transitions) > 0

    trainer.add_transitions_to_buffer(transitions)
    assert len(trainer.replay_states) == len(transitions)

    metrics = trainer.train_gpu_step(epochs=1, batch_size=4)
    assert "loss" in metrics
    assert metrics["loss"] >= 0.0
