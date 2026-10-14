"""Módulo de Avaliação Heurística Posicional e Tática (PeSTO + Positional Factors).

Implementa avaliação detalhada baseada no padrão PeSTO (Piece-Square Tables para
Middlegame e Endgame com interpolação de fases da partida), bônus de par de bispos,
estrutura de peões (passados, dobrados, isolados), colunas abertas para torres e
segurança do rei.
"""

from typing import Dict, List, Tuple
import chess

# Valores base das peças (PeSTO MidGame e EndGame)
MG_VALUE = {
    chess.PAWN: 82,
    chess.KNIGHT: 337,
    chess.BISHOP: 365,
    chess.ROOK: 477,
    chess.QUEEN: 1025,
    chess.KING: 0,
}

EG_VALUE = {
    chess.PAWN: 94,
    chess.KNIGHT: 281,
    chess.BISHOP: 297,
    chess.ROOK: 512,
    chess.QUEEN: 936,
    chess.KING: 0,
}

# Pesos para cálculo da fase de jogo (Total = 24)
GAME_PHASE_WEIGHT = {
    chess.PAWN: 0,
    chess.KNIGHT: 1,
    chess.BISHOP: 1,
    chess.ROOK: 2,
    chess.QUEEN: 4,
    chess.KING: 0,
}
TOTAL_PHASE = 24

# Tabelas PeSTO de Posicionamento (Middlegame e Endgame) ordenadas de A1 (índice 0) a H8 (índice 63)
# Ranks 1 a 8
MG_PAWN_TABLE = [
      0,   0,   0,   0,   0,   0,   0,   0,
     98, 134,  61,  95,  68, 126,  34, -11,
     -6,   7,  26,  31,  65,  56,  25, -20,
    -14,  13,   6,  21,  23,  12,  17, -23,
    -27,  -2,  -5,  12,  17,   6,  10, -25,
    -26,  -4,  -4, -10,   3,   3,  33, -12,
    -35,  -1, -20, -23, -15,  24,  38, -22,
      0,   0,   0,   0,   0,   0,   0,   0,
]

EG_PAWN_TABLE = [
      0,   0,   0,   0,   0,   0,   0,   0,
    178, 173, 158, 134, 147, 132, 165, 187,
     94, 100,  85,  67,  56,  53,  82,  84,
     32,  24,  13,   5,  -2,   4,  17,  17,
     13,   9,  -3,  -7,  -7,  -8,   3,  -1,
      4,   7,  -6,   1,   0,  -5,  -1,  -8,
     13,   9,   8,  10,  11,   0,  14,   5,
      0,   0,   0,   0,   0,   0,   0,   0,
]

MG_KNIGHT_TABLE = [
   -167, -89, -34, -49,  61, -97, -15, -107,
    -73, -41,  72,  36,  23,  62,   7,  -17,
    -47,  60,  37,  65,  84, 129,  73,   44,
     -9,  17,  19,  53,  37,  69,  18,   22,
    -13,   4,  16,  13,  28,  19,  21,   -8,
    -23,  -9,  12,  10,  19,  17,  25,  -16,
    -29, -53, -12,  -3,  -1,  18, -14,  -19,
   -105, -21, -58, -33, -17, -28, -19,  -23,
]

EG_KNIGHT_TABLE = [
    -58, -38, -13, -28, -31, -27, -63, -99,
    -25,  -8, -25,  -2,  -9, -25, -24, -52,
    -24, -20,  10,   9,  -1,  -9, -19, -41,
    -17,   3,  22,  22,  22,  11,   8, -18,
    -18,  -6,  16,  25,  16,  17,   4, -18,
    -23,  -3,  -1,  15,  10,  -3, -20, -22,
    -42, -20, -10,  -5,  -2, -20, -23, -44,
    -29, -51, -23, -15, -22, -18, -50, -64,
]

MG_BISHOP_TABLE = [
    -29,   4, -82, -37, -25, -42,   7,  -8,
    -26,  16, -18, -13,  30,  59,  18, -47,
    -16,  37,  43,  40,  35,  50,  37,  -2,
     -4,   5,  19,  50,  37,  37,   7,  -2,
     -6,  13,  13,  26,  34,  12,  10,   4,
      0,  15,  15,  15,  14,  27,  18,  10,
      4,  15,  16,   0,   7,  21,  33,   1,
    -33,  -3, -14, -21, -13, -12, -39, -21,
]

EG_BISHOP_TABLE = [
    -14, -21, -11,  -8,  -7,  -9, -17, -24,
     -8,  -4,   7, -12,  -3, -13,  -4, -14,
      2,  -8,   0,  -1,  -2,   6,   0,   4,
     -3,   9,  12,   9,  14,  10,   3,   2,
     -6,   3,  13,  19,   7,  10,  -3,  -9,
    -12,  -3,   8,  10,  13,   3,  -7, -15,
    -14, -18,  -7,  -1,   4,  -9, -15, -27,
    -23,  -9, -23,  -5,  -9, -16,  -5, -17,
]

MG_ROOK_TABLE = [
     32,  42,  32,  51,  63,   9,  31,  43,
     27,  32,  58,  62,  80,  67,  26,  44,
     -5,  19,  26,  36,  17,  45,  61,  16,
    -24, -11,   7,  26,  24,  35,  -8, -20,
    -36, -26, -12,  -1,   9,  -7,   6, -23,
    -45, -25, -16, -17,   3,   0,  -5, -33,
    -44, -16, -20,  -9,  -1,  11,  -6, -71,
    -19, -13,   1,  17,  16,   7, -37, -26,
]

EG_ROOK_TABLE = [
     13,  10,  18,  15,  12,  12,   8,   5,
     11,  13,  13,  11,  -3,   3,   8,   3,
      7,   7,   7,   5,   4,  -3,  -5,  -3,
      4,   3,  13,   1,   2,   1,  -1,   2,
      3,   5,   8,   4,  -5,  -6,  -8, -11,
     -4,   0,  -5,  -1,  -7, -12,  -8, -16,
     -6,  -6,   0,   2,  -9,  -9, -11,  -3,
     -9,   2,   3,  -1,  -5, -13,   4, -20,
]

MG_QUEEN_TABLE = [
    -28,   0,  29,  12,  59,  44,  43,  45,
    -24, -39,  -5,   1, -16,  57,  28,  54,
    -18, -15,  -9,  20,  21,   4,  26,  25,
    -14, -10,  -9,  -1,  12,  17,  -5,   0,
    -10,  -6,  -7,   2,   5,   6,  -2,  -1,
     -9, -14,  -9,  -3,  -2,  -2,   1,  -5,
    -11,  -5,   5,  -4,  -6,  -6,  -3,  -9,
    -19, -13,   1,  17,  16,   7, -37, -26,
]

EG_QUEEN_TABLE = [
     -9,  22,  22,  27,  27,  19,  10,  20,
    -17,  20,  32,  41,  58,  25,  30,   0,
    -20,   6,   9,  49,  47,  35,  19,   9,
      3,  22,  24,  45,  57,  40,  57,  36,
    -18,  28,  19,  47,  31,  34,  39,  18,
    -16, -27,  15,   6,   9,  17,  10,   5,
    -22, -23, -30, -16, -16, -23, -36, -32,
    -33, -28, -22, -43,  -5, -32, -20, -41,
]

MG_KING_TABLE = [
   -65,  23,  16, -15, -56, -34,   2,  13,
    29,  -1, -20,  -7,  -8,  -4, -38, -29,
    -9,  24,   2, -16, -20,   6,  22, -22,
   -17, -20, -12, -27, -30, -25, -14, -36,
   -49,  -1, -27, -39, -46, -44, -33, -51,
   -14, -14, -22, -46, -44, -30, -15, -27,
     1,   7,  -8, -64, -43, -16,   9,   8,
   -15,  36,  12, -54,   8, -28,  24,  14,
]

EG_KING_TABLE = [
    -74, -35, -18, -18, -11,  15,   4, -17,
    -12,  17,  14,  17,  17,  38,  23,  11,
     10,  17,  23,  15,  20,  45,  44,  13,
     -8,  22,  24,  27,  26,  33,  26,   3,
    -18,  -4,  21,  24,  27,  23,   9, -11,
    -19,  -3,  11,  21,  23,  16,   7,  -9,
    -27, -11,   4,  13,  14,   4,  -5, -17,
    -53, -34, -21, -11, -28, -14, -24, -43,
]

MG_PST = {
    chess.PAWN: MG_PAWN_TABLE,
    chess.KNIGHT: MG_KNIGHT_TABLE,
    chess.BISHOP: MG_BISHOP_TABLE,
    chess.ROOK: MG_ROOK_TABLE,
    chess.QUEEN: MG_QUEEN_TABLE,
    chess.KING: MG_KING_TABLE,
}

EG_PST = {
    chess.PAWN: EG_PAWN_TABLE,
    chess.KNIGHT: EG_KNIGHT_TABLE,
    chess.BISHOP: EG_BISHOP_TABLE,
    chess.ROOK: EG_ROOK_TABLE,
    chess.QUEEN: EG_QUEEN_TABLE,
    chess.KING: EG_KING_TABLE,
}

PASSED_PAWN_BONUS = [0, 5, 10, 20, 35, 60, 100, 0]


def evaluate_board(board: chess.Board) -> int:
    """Avalia o estado do tabuleiro em centipawns da perspectiva do lado a jogar.
    
    Valores positivos favorecem quem joga no momento; valores negativos desfavorecem.
    """
    if board.is_checkmate():
        return -20000

    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    mg_white = 0
    eg_white = 0
    mg_black = 0
    eg_black = 0
    game_phase = 0

    white_bishops = 0
    black_bishops = 0
    white_pawns_by_file = [0] * 8
    black_pawns_by_file = [0] * 8

    # Varredura das 64 casas
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece:
            continue

        pt = piece.piece_type
        color = piece.color

        game_phase += GAME_PHASE_WEIGHT[pt]

        if color == chess.WHITE:
            sq_idx = sq
            mg_white += MG_VALUE[pt] + MG_PST[pt][sq_idx]
            eg_white += EG_VALUE[pt] + EG_PST[pt][sq_idx]

            if pt == chess.BISHOP:
                white_bishops += 1
            elif pt == chess.PAWN:
                white_pawns_by_file[chess.square_file(sq)] += 1
        else:
            # Para as pretas, espelhamos o índice verticalmente
            sq_idx = chess.square_mirror(sq)
            mg_black += MG_VALUE[pt] + MG_PST[pt][sq_idx]
            eg_black += EG_VALUE[pt] + EG_PST[pt][sq_idx]

            if pt == chess.BISHOP:
                black_bishops += 1
            elif pt == chess.PAWN:
                black_pawns_by_file[chess.square_file(sq)] += 1

    # Bônus de par de bispos (+45 cp)
    if white_bishops >= 2:
        mg_white += 45
        eg_white += 45
    if black_bishops >= 2:
        mg_black += 45
        eg_black += 45

    # Penalidades e bônus de peões
    for f in range(8):
        # Peões dobrados (-15 cp por peão extra na coluna)
        if white_pawns_by_file[f] > 1:
            mg_white -= 15 * (white_pawns_by_file[f] - 1)
            eg_white -= 20 * (white_pawns_by_file[f] - 1)
        if black_pawns_by_file[f] > 1:
            mg_black -= 15 * (black_pawns_by_file[f] - 1)
            eg_black -= 20 * (black_pawns_by_file[f] - 1)

        # Peões isolados (-15 cp se não houver peões amigos nas colunas adjacentes)
        has_white_neighbor = (f > 0 and white_pawns_by_file[f - 1] > 0) or (f < 7 and white_pawns_by_file[f + 1] > 0)
        if white_pawns_by_file[f] > 0 and not has_white_neighbor:
            mg_white -= 15
            eg_white -= 20

        has_black_neighbor = (f > 0 and black_pawns_by_file[f - 1] > 0) or (f < 7 and black_pawns_by_file[f + 1] > 0)
        if black_pawns_by_file[f] > 0 and not has_black_neighbor:
            mg_black -= 15
            eg_black -= 20

    # Bônus de coluna aberta/semi-aberta para torres
    for sq in board.pieces(chess.ROOK, chess.WHITE):
        f = chess.square_file(sq)
        if white_pawns_by_file[f] == 0:
            if black_pawns_by_file[f] == 0:
                mg_white += 25  # Coluna totalmente aberta
                eg_white += 25
            else:
                mg_white += 15  # Coluna semi-aberta
                eg_white += 15

    for sq in board.pieces(chess.ROOK, chess.BLACK):
        f = chess.square_file(sq)
        if black_pawns_by_file[f] == 0:
            if white_pawns_by_file[f] == 0:
                mg_black += 25
                eg_black += 25
            else:
                mg_black += 15
                eg_black += 15

    # Interpolação de fase da partida (Tapered Eval)
    phase = min(game_phase, TOTAL_PHASE)
    mg_score = mg_white - mg_black
    eg_score = eg_white - eg_black
    eval_score = ((mg_score * phase) + (eg_score * (TOTAL_PHASE - phase))) // TOTAL_PHASE

    # Retorna sob o ponto de vista do jogador do turno (White ou Black)
    return eval_score if board.turn == chess.WHITE else -eval_score
