"""Suíte de Testes para o Motor de Busca Neural (NeuralMCTS / PUCT Tree Search)."""

import pytest
import chess
import torch
from chess_ai.model import ChessPolicyValueNet
from chess_ai.mcts import MCTSNode, NeuralMCTS


def test_mcts_node_properties():
    """Valida propriedades básicas do nó MCTS."""
    board = chess.Board()
    node = MCTSNode(board=board, prior=0.5)

    assert node.visit_count == 0
    assert node.total_value == 0.0
    assert node.q_value == 0.0
    assert not node.is_expanded
    assert not node.is_terminal


def test_mcts_node_terminal_detection():
    """Valida identificação de nós terminais (mate e afogamento)."""
    # Posição de Xeque-Mate (Fool's Mate)
    mate_board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert mate_board.is_checkmate()

    mate_node = MCTSNode(board=mate_board)
    assert mate_node.is_terminal
    # Como as brancas estão em mate e é a vez delas, o valor terminal é -1.0
    assert mate_node.terminal_value == -1.0

    # Posição de Afogamento (Stalemate)
    stalemate_board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert stalemate_board.is_stalemate()

    st_node = MCTSNode(board=stalemate_board)
    assert st_node.is_terminal
    assert st_node.terminal_value in (0.0, 0.25)


def test_mcts_search_opening():
    """Testa busca MCTS na posição inicial com 20 simulações."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    mcts = NeuralMCTS(model=model, device=device, c_puct=2.0)

    board = chess.Board()
    move, stats = mcts.search(board, num_simulations=20, temperature=0.0)

    assert move is not None
    assert move in board.legal_moves
    assert stats["source"] == "neural_mcts"
    assert stats["simulations"] == 20
    assert stats["depth_reached"] >= 1
    assert "principal_variation" in stats
    assert len(stats["principal_variation"]) >= 1


def test_mcts_instant_checkmate_detector():
    """Valida se o MCTS detecta e executa xeque-mate em 1 instantaneamente."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    mcts = NeuralMCTS(model=model, device="cpu")

    # Posição onde Dh5# é mate em 1 (Scholar's Mate final move: Qxf7#)
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
    mate_move = chess.Move.from_uci("h5f7")
    assert mate_move in board.legal_moves

    move, stats = mcts.search(board, num_simulations=50)
    assert move == mate_move
    assert stats["source"] == "mcts_instant_checkmate"
    assert stats["root_value"] == 1.0


def test_mcts_with_dirichlet_noise():
    """Testa busca MCTS com ruído de Dirichlet ativado para exploração."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    mcts = NeuralMCTS(model=model, device="cpu", dirichlet_alpha=0.3, dirichlet_eps=0.25)

    board = chess.Board()
    move, stats = mcts.search(board, num_simulations=15, add_noise=True, temperature=0.5)

    assert move is not None
    assert move in board.legal_moves
    assert stats["simulations"] == 15


def test_mcts_anti_blunder_guard_prevents_mate():
    """Valida se a Guarda Tática Anti-Blunder impede o bot de permitir mate em 1."""
    model = ChessPolicyValueNet(num_channels=64, num_blocks=2)
    mcts = NeuralMCTS(model=model, device="cpu")

    # Posição onde as Brancas ameaçam Qxf7# (Pastor) e as Pretas precisam se defender
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR b KQkq - 3 3")
    move, stats = mcts.search(board, num_simulations=30, temperature=0.0)

    assert move is not None
    assert move in board.legal_moves

    # O lance escolhido NUNCA pode permitir que as Brancas joguem Qxf7# no lance seguinte
    board.push(move)
    for white_move in board.legal_moves:
        board.push(white_move)
        assert not board.is_checkmate(), f"O lance {move} permitiu mate imediato com {white_move}!"
        board.pop()
    board.pop()

