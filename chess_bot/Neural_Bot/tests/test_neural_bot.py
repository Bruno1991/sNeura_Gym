"""Suíte de Testes Automatizados para o Neural_Bot (ResNet Policy-Value)."""

import pytest
import chess
import torch
from pathlib import Path

from chess_ai.encoder import encode_board, encode_move, decode_move, get_legal_action_mask, ACTION_SIZE, NUM_CHANNELS
from chess_ai.model import ChessPolicyValueNet
from chess_ai.dataset import extract_polyglot_data
from chess_ai.agent import NeuralChessBot


def test_encoder_board_shape():
    """Valida formato do tensor gerado pelo encoder."""
    board = chess.Board()
    tensor = encode_board(board)
    assert tensor.shape == (NUM_CHANNELS, 8, 8)
    assert tensor.dtype == torch.float32
    # Na posição inicial, canal 17 (vez de jogar) deve ser 1.0 (brancas)
    assert tensor[17, 0, 0] == 1.0


def test_encoder_canonical_symmetry():
    """Valida espelhamento canônico para o turno das Pretas."""
    board = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    tensor = encode_board(board)
    # Canal 17 para pretas deve ser 0.0
    assert tensor[17, 0, 0] == 0.0


def test_encoder_move_roundtrip():
    """Testa codificação e decodificação de lances."""
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    idx = encode_move(move, board.turn)
    decoded = decode_move(idx, board)
    assert decoded == move

    # Lance das Pretas
    board.push(move)
    black_move = chess.Move.from_uci("c7c5")
    idx_black = encode_move(black_move, board.turn)
    decoded_black = decode_move(idx_black, board)
    assert decoded_black == black_move


def test_legal_action_mask():
    """Na posição inicial devem existir exatamente 20 lances legais (16 de peão + 4 de cavalo)."""
    board = chess.Board()
    mask = get_legal_action_mask(board)
    assert mask.shape == (ACTION_SIZE,)
    assert mask.sum().item() == 20


def test_model_forward_pass():
    """Testa passagem direta (forward pass) pela ChessPolicyValueNet."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    x = torch.randn(2, NUM_CHANNELS, 8, 8)
    policy_logits, value = model(x)

    assert policy_logits.shape == (2, ACTION_SIZE)
    assert value.shape == (2, 1)
    assert torch.all(value >= -1.0) and torch.all(value <= 1.0)


def test_dataset_extraction_small():
    """Testa extração de pequena amostra de 10 posições do balanced.bin."""
    book_path = Path(__file__).resolve().parent.parent.parent / "Scripted_Bot" / "assets" / "balanced.bin"
    assert book_path.is_file(), "O balanced.bin deve existir em Scripted_Bot."

    states, policies, values = extract_polyglot_data(book_path, max_positions=10)
    assert len(states) == 10
    assert states.shape == (10, NUM_CHANNELS, 8, 8)
    assert policies.shape == (10, ACTION_SIZE)
    assert values.shape == (10, 1)


def test_agent_legal_inference():
    """Testa se o agente escolhe sempre lances legais a partir da rede."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    temp_weights = Path(__file__).resolve().parent / "temp_weights.pt"
    model.save_weights(temp_weights)

    try:
        agent = NeuralChessBot(weights_path=temp_weights, device="cpu")
        assert agent.is_ready()

        board = chess.Board()
        move, info = agent.get_best_move(board)
        assert move in board.legal_moves
        assert "probability" in info
        assert "value" in info
    finally:
        if temp_weights.is_file():
            temp_weights.unlink()
