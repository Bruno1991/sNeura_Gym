"""Testes de integracao para o ChessComBot conectado aos dados do Chess.com em s_ADB_Tools."""

import sys
from pathlib import Path
import chess

current_dir = Path(__file__).resolve().parent
neural_dir = current_dir.parent
scripted_dir = neural_dir.parent / "Scripted_Bot"
sys.path.insert(0, str(scripted_dir))

from chess_bot import ChessBot, ChessComBot


def test_chess_com_bot_by_elo():
    bot = ChessBot(rate=2500)
    assert bot.rating == 2500
    assert bot.name == "Luk.AI"
    assert bot.book_name is not None
    greeting = bot.get_phrase("greeting")
    assert isinstance(greeting, str) and len(greeting) > 0


def test_chess_bot_by_rate_1000():
    bot = ChessBot(rate=1000)
    assert bot.rating == 1000
    assert bot.name == "Maria"
    assert "gambit" in bot.book_name
    assert bot.calibrated_depth == 2
    assert bot.blunder_rate == 0.18


def test_chess_com_bot_by_name():
    bot = ChessComBot(bot_name="Nelson")
    assert bot.name == "Nelson"
    assert bot.rating == 1300
    assert "quick_queen" in bot.book_name
    greeting = bot.get_phrase("greeting")
    assert "Molo!" in greeting


def test_chess_com_bot_legal_move():
    bot = ChessComBot(target_elo=2500)
    board = chess.Board()
    move, info = bot.get_best_move(board)
    assert move in board.legal_moves
    assert "source" in info
