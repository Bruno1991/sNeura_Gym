"""Testes unitários para o módulo de Aprendizado Online Contínuo (OnlineLearner)."""

import tempfile
from pathlib import Path

import chess
import pytest
import torch

from chess_ai.model import ChessPolicyValueNet
from chess_ai.online_learning import OnlineLearner


@pytest.fixture
def temp_learner():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        weights_path = tmp_path / "test_weights.pt"
        onnx_path = tmp_path / "test_weights.onnx"
        history_path = tmp_path / "test_history.json"

        model = ChessPolicyValueNet(num_channels=32, num_blocks=2)
        learner = OnlineLearner(
            model=model,
            weights_path=weights_path,
            onnx_path=onnx_path,
            history_path=history_path,
            device="cpu",
        )
        yield learner, weights_path, history_path


def test_trajectory_recording(temp_learner):
    learner, _, _ = temp_learner
    learner.start_game()
    board = chess.Board()

    move = chess.Move.from_uci("e2e4")
    learner.record_move(board, move, is_neural=True)
    board.push(move)

    assert len(learner.current_trajectory) == 1
    state_t, act_idx, is_neural = learner.current_trajectory[0]
    assert state_t.shape == (18, 8, 8)
    assert is_neural is True


def test_evaluate_game_outcome_checkmate(temp_learner):
    learner, _, _ = temp_learner
    # Fool's mate: 1. f3 e5 2. g4 Qh4#
    board = chess.Board()
    for m in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        board.push(chess.Move.from_uci(m))

    assert board.is_checkmate()
    outcome_black_neural, desc = learner.evaluate_game_outcome(board, neural_is_white=False)
    assert outcome_black_neural == 1.0
    assert "Vitória Neural" in desc

    outcome_white_neural, _ = learner.evaluate_game_outcome(board, neural_is_white=True)
    assert outcome_white_neural == -1.0


def test_learn_from_completed_game(temp_learner):
    learner, weights_path, history_path = temp_learner
    learner.start_game()
    board = chess.Board()

    # Executar 4 lances simulados
    moves = ["e2e4", "e7e5", "g1f3", "b8c6"]
    for i, m_str in enumerate(moves):
        move = chess.Move.from_uci(m_str)
        learner.record_move(board, move, is_neural=(i % 2 == 0))
        board.push(move)

    res = learner.learn_from_completed_game(board, neural_is_white=True, opponent_name="TestBot", epochs=1)

    assert res["trained"] is True
    assert res["positions_trained"] == 4
    assert res["loss"] > 0.0
    assert weights_path.is_file()
    assert history_path.is_file()
    assert len(learner.current_trajectory) == 0
