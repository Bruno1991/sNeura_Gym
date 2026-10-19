"""Motor Paralelo Multiprocessado para Bots Oponentes do Chess.com."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import chess

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTED_DIR = ROOT_DIR / "Scripted_Bot"
if str(SCRIPTED_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTED_DIR))

from chess_bot import ChessBot

_BOT_CACHE: Dict[Tuple[int, Optional[str]], ChessBot] = {}

def get_cached_bot(rate: int, bot_name: Optional[str] = None) -> ChessBot:
    key = (rate, bot_name)
    if key not in _BOT_CACHE:
        _BOT_CACHE[key] = ChessBot(rate=rate, bot_name=bot_name)
    return _BOT_CACHE[key]

def compute_engine_move_task(task: Tuple[str, int, Optional[str], int, float]) -> Tuple[Optional[str], str]:
    """Calcula o melhor lance do bot oponente em um processo separado.
    
    task: (fen, rating, bot_name, max_depth, max_time_seconds)
    retorna: (move_uci, fen)
    """
    fen, rating, bot_name, depth, max_time = task
    try:
        board = chess.Board(fen)
        bot = get_cached_bot(rating, bot_name)
        m, _ = bot.get_best_move(board, max_depth=depth, max_time_seconds=max_time)
        return (m.uci() if m else None, fen)
    except Exception:
        return (None, fen)
