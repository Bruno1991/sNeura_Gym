"""Suíte de Testes para o Ambiente Paralelo (BatchedChessEnv e BatchedRLTrainer)."""

import pytest
import chess
import torch
from chess_ai.model import ChessPolicyValueNet
from chess_ai.batched_env import BatchedChessEnv, encode_boards_batch
from chess_ai.batched_rl_trainer import BatchedRLTrainer


class FastDummyBot:
    """Bot de teste que escolhe o primeiro lance legal disponível."""

    def get_best_move(self, board, max_depth=1, max_time_seconds=0.01):
        moves = list(board.legal_moves)
        return moves[0] if moves else None, {"source": "fast_dummy"}


def test_encode_boards_batch():
    """Valida formato do tensor gerado pela codificação de lote de 64 tabuleiros."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    boards = [chess.Board() for _ in range(64)]

    tensor = encode_boards_batch(boards, device)
    assert tensor.shape == (64, 18, 8, 8)
    assert tensor.dtype == torch.float32
    assert tensor.device.type == device.type


def test_batched_chess_env_initialization():
    """Valida inicialização dos 64 workers e distribuição alternada de cores."""
    env = BatchedChessEnv(num_workers=64, max_plies=20)
    assert len(env.workers) == 64
    assert env.workers[0].neural_is_white is True
    assert env.workers[1].neural_is_white is False
    assert env.workers[2].neural_is_white is True


def test_batched_chess_env_step_batch():
    """Testa avanço de passos em lote no ambiente paralelo."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    dummy_bot = FastDummyBot()

    env = BatchedChessEnv(num_workers=16, max_plies=6, device=device)

    # Executar 10 passos em lote
    all_finished = []
    for _ in range(10):
        finished = env.step_batch(model=model, bot_3200=dummy_bot, temperature=0.0, use_amp=False)
        all_finished.extend(finished)

    # Pelo menos algumas partidas devem ter atingido o limite max_plies=6 e finalizado
    assert env.total_completed_games > 0
    assert len(all_finished) > 0


def test_batched_rl_trainer_small_cycle():
    """Valida ciclo completo do BatchedRLTrainer com otimização GPU/AMP."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dummy_bot = FastDummyBot()

    trainer = BatchedRLTrainer(
        model=model,
        bot_3200=dummy_bot,
        num_workers=16,
        device=device,
        use_amp=(device == "cuda"),
    )

    # Executar um ciclo curto de 8 partidas
    trainer.run_batched_training(
        total_games=8,
        games_per_cycle=8,
        epochs_per_cycle=1,
        batch_size=32,
    )

    assert trainer.env.total_completed_games >= 8
    assert len(trainer.history) == 1
    assert "loss" in trainer.history[0]
