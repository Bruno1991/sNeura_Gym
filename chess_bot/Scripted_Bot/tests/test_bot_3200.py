"""Suíte de Testes Automatizados para o Bot de Xadrez 3200 Elo (Maximum / Komodo 25)."""

import pytest
import chess
from pathlib import Path

from bot_3200 import ChessBot3200
from engine.evaluation import evaluate_board
from engine.search import AlphaBetaSearcher


@pytest.fixture
def bot():
    return ChessBot3200()


def test_assets_exist(bot):
    """Verifica se os arquivos essenciais estão presentes no diretório assets/."""
    assert bot.book_path.is_file(), "O arquivo balanced.bin deve existir."
    assert bot.book_path.stat().st_size > 1_000_000, "O balanced.bin deve ter mais de 1 MB."
    assert bot.profile_path.is_file(), "O arquivo bot_3200_profile.json deve existir."


def test_bot_profile(bot):
    """Valida as propriedades técnicas do bot oficial de 3200."""
    assert bot.name == "Maximum"
    assert bot.username == "Komodo25"
    assert bot.rating == 3200
    assert bot.komodo_skill == 25
    assert "greeting" in bot.phrases


def test_opening_book_lookup(bot):
    """Testa a leitura de variantes oficiais no livro Polyglot balanced.bin."""
    board = chess.Board()
    book_result = bot.get_book_move(board)
    assert book_result is not None, "A posição inicial deve conter lances no livro."
    move, weight = book_result
    assert move in board.legal_moves
    assert weight > 0
    assert board.san(move) in ["e4", "d4", "Nf3", "c4", "g3", "b3"]


def test_opening_book_sicilian_response(bot):
    """Testa resposta de pretas no livro contra 1. e4."""
    board = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    book_result = bot.get_book_move(board)
    assert book_result is not None
    move, weight = book_result
    assert move in board.legal_moves
    assert board.san(move) in ["c5", "e5", "e6", "c6", "d6", "Nf6"]


def test_evaluation_initial_board():
    """Avaliação da posição inicial deve ser próxima de zero (equilíbrio posicional)."""
    board = chess.Board()
    score = evaluate_board(board)
    assert abs(score) < 50, f"Posição inicial equilibrada, obtido: {score}"


def test_evaluation_material_advantage():
    """Brancas com uma dama extra devem ter pontuação fortemente positiva."""
    board = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")  # Pretas sem dama
    score = evaluate_board(board)
    assert score > 800, f"Vantagem de dama deve ser > 800 cp, obtido: {score}"


def test_tactical_mate_in_one():
    """O motor deve identificar e executar mate em 1 lance imediatamente."""
    # Posição clássica de mate do pastor com Qxf7#
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
    searcher = AlphaBetaSearcher(max_depth=2)
    move, score, depth, _ = searcher.search_best_move(board, max_depth=2)
    assert move == chess.Move.from_uci("h5f7"), f"Esperado Qxf7#, obtido: {move}"
    assert score > 15000, "Pontuação deve indicar xeque-mate iminente."


def test_bot_get_best_move_in_book(bot):
    """Testa chamada get_best_move quando a posição está no livro de abertura."""
    board = chess.Board()
    move, info = bot.get_best_move(board)
    assert move in board.legal_moves
    assert info.get("source") == "book"
    assert info.get("book") == "balanced.bin"


def test_bot_get_best_move_out_of_book(bot):
    """Testa chamada get_best_move quando a posição sai do livro de abertura."""
    # Posição incomum sem lances em livro de abertura
    board = chess.Board("r1bqk2r/pp1p1ppp/2n1pn2/8/1bPP4/2N2N2/PP3PPP/R1BQKB1R w KQkq - 2 7")
    move, info = bot.get_best_move(board, max_depth=2, max_time_seconds=1.5)
    assert move in board.legal_moves
    assert info.get("source") in ["builtin_alphabeta", "uci_engine"]
    assert "score_cp" in info


def test_game_simulation_short(bot):
    """Executa pequena simulação de partida automática de 4 lances sem erros."""
    board = chess.Board()
    for _ in range(4):
        move, _ = bot.get_best_move(board, max_depth=2, max_time_seconds=1.0)
        assert move is not None
        assert move in board.legal_moves
        board.push(move)
    assert len(board.move_stack) == 4
