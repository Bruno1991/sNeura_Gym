"""Testes unitários para o módulo de segurança tática (tactics.py)."""

import chess
import pytest

from chess_ai.tactics import (
    evaluate_tactical_safety,
    get_piece_value,
    rank_candidates_with_tactical_shield,
)


def test_get_piece_value():
    assert get_piece_value(chess.Piece(chess.PAWN, chess.WHITE)) == 100
    assert get_piece_value(chess.Piece(chess.QUEEN, chess.BLACK)) == 900
    assert get_piece_value(None) == 0


def test_detect_hanging_queen_blunder():
    # Posição onde jogar Dd5 entrega a dama para um peão em c6
    board = chess.Board()
    # 1. e4 c6 2. d4 d5
    board.push_san("e4")
    board.push_san("c6")
    board.push_san("d4")
    board.push_san("d5")

    # Lance suicida: 3. Qd3 ou colocar a dama onde pode ser capturada de graça
    # Exemplo: Qd3 é seguro, mas Qf3 ou Qg4 (atacada por bispo de c8)?
    # 3. Qg4? O bispo preto em c8 captura a dama de graça (Bxg4)
    blunder_move = chess.Move.from_uci("d1g4")
    is_safe, delta, reason = evaluate_tactical_safety(board, blunder_move)
    assert not is_safe
    assert delta <= -800
    assert reason == "hanging_material"

    # Lance seguro normal: 3. e5
    safe_move = chess.Move.from_uci("e4e5")
    is_safe_2, delta_2, reason_2 = evaluate_tactical_safety(board, safe_move)
    assert is_safe_2
    assert reason_2 == "safe"


def test_detect_walking_into_checkmate():
    # Fool's mate setup: 1. f3 e5 2. g4?? (walks into Qh4#)
    board = chess.Board()
    board.push_san("f3")
    board.push_san("e5")

    # Jogar 2. g4 permite às pretas darem xeque-mate imediato com Qh4#
    blunder_mate = chess.Move.from_uci("g2g4")
    is_safe, delta, reason = evaluate_tactical_safety(board, blunder_mate)
    assert not is_safe
    assert reason == "opp_checkmate"


def test_rank_candidates_prefers_safe_move_over_blunder():
    board = chess.Board()
    board.push_san("f3")
    board.push_san("e5")

    # Suponha que a rede neural atribuiu maior probabilidade para o lance suicida g4
    # e menor probabilidade para o lance seguro Kf2 ou e4
    blunder_m = chess.Move.from_uci("g2g4")  # Dá mate para as pretas
    safe_m = chess.Move.from_uci("e2e4")     # Seguro

    candidates = [(blunder_m, 0.70), (safe_m, 0.30)]
    ranked = rank_candidates_with_tactical_shield(board, candidates)

    assert len(ranked) >= 1
    # O primeiro lance escolhido DEVE ser o seguro
    best_move, best_prob, is_safe = ranked[0]
    assert best_move == safe_m
    assert is_safe


def test_punitive_strike_captures_hanging_piece():
    # Oponente (Pretas) deixou uma Dama de graça em d5
    board = chess.Board()
    board.set_fen("rnb1kbnr/pppp1ppp/8/3q4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1")

    # Brancas têm exd5 (captura a Dama de graça com ganho líquido de +900 cp)
    # Suponha que a rede sugeriu um lance calmo (Nf3 com 0.60) e a captura (exd5 com apenas 0.15)
    calm_move = chess.Move.from_uci("g1f3")
    capture_queen = chess.Move.from_uci("e4d5")

    candidates = [(calm_move, 0.60), (capture_queen, 0.15)]
    ranked = rank_candidates_with_tactical_shield(board, candidates, enable_punishment_trigger=True)

    # O gatilho punitivo voraz DEVE promover exd5 para o 1º lugar com score altíssimo
    best_move, _, is_safe = ranked[0]
    assert best_move == capture_queen
    assert is_safe

