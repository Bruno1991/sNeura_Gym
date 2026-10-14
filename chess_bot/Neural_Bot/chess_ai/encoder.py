"""Módulo de Codificação de Tabuleiro e Lances em Tensores (Encoder).

Converte objetos chess.Board e chess.Move em representações tensoriais
compatíveis com PyTorch para inferência e treinamento da rede neural.
Utiliza a perspectiva canônica (o jogador da vez sempre joga das brancas para as pretas,
espelhando verticalmente quando forem as pretas a jogar).
"""

from typing import List, Optional, Tuple
import chess
import numpy as np
import torch

NUM_PIECES = 6  # P, N, B, R, Q, K
NUM_CHANNELS = 18  # 6 peças amigas + 6 peças inimigas + 1 en passant + 4 roques + 1 turno
ACTION_SIZE = 4096  # 64 x 64 casas possíveis


def encode_board(board: chess.Board) -> torch.Tensor:
    """Codifica o tabuleiro de xadrez em um tensor de formato (18, 8, 8).
    
    A representação é sempre canônica em relação ao jogador do turno:
    - Se for a vez das Pretas, o tabuleiro é invertido verticalmente e as cores são invertidas.
    """
    planes = np.zeros((NUM_CHANNELS, 8, 8), dtype=np.float32)

    turn = board.turn
    friendly_color = turn
    opponent_color = not turn

    piece_types = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]

    for pt_idx, pt in enumerate(piece_types):
        # Peças amigas (Canais 0 a 5)
        for sq in board.pieces(pt, friendly_color):
            # Se forem pretas, espelhamos o rank
            mapped_sq = chess.square_mirror(sq) if turn == chess.BLACK else sq
            row = chess.square_rank(mapped_sq)
            col = chess.square_file(mapped_sq)
            planes[pt_idx, row, col] = 1.0

        # Peças inimigas (Canais 6 a 11)
        for sq in board.pieces(pt, opponent_color):
            mapped_sq = chess.square_mirror(sq) if turn == chess.BLACK else sq
            row = chess.square_rank(mapped_sq)
            col = chess.square_file(mapped_sq)
            planes[pt_idx + 6, row, col] = 1.0

    # Canal 12: Casa de En Passant
    if board.ep_square is not None:
        mapped_ep = chess.square_mirror(board.ep_square) if turn == chess.BLACK else board.ep_square
        row = chess.square_rank(mapped_ep)
        col = chess.square_file(mapped_ep)
        planes[12, row, col] = 1.0

    # Canais 13-16: Direitos de Roque
    if board.has_kingside_castling_rights(friendly_color):
        planes[13, :, :] = 1.0
    if board.has_queenside_castling_rights(friendly_color):
        planes[14, :, :] = 1.0
    if board.has_kingside_castling_rights(opponent_color):
        planes[15, :, :] = 1.0
    if board.has_queenside_castling_rights(opponent_color):
        planes[16, :, :] = 1.0

    # Canal 17: Vez de jogar original (1.0 para White, 0.0 para Black)
    planes[17, :, :] = 1.0 if turn == chess.WHITE else 0.0

    return torch.from_numpy(planes)


def encode_move(move: chess.Move, turn: chess.Color = chess.WHITE) -> int:
    """Codifica um lance chess.Move em um índice de ação entre 0 e 4095.
    
    Aplica espelhamento canônico se for a vez das Pretas.
    """
    if turn == chess.BLACK:
        from_sq = chess.square_mirror(move.from_square)
        to_sq = chess.square_mirror(move.to_square)
    else:
        from_sq = move.from_square
        to_sq = move.to_square

    return from_sq * 64 + to_sq


def decode_move(action_idx: int, board: chess.Board) -> Optional[chess.Move]:
    """Decodifica um índice de ação (0 a 4095) de volta para um chess.Move legal.
    
    Inverte o espelhamento canônico se for a vez das Pretas e trata promoções.
    """
    from_sq = action_idx // 64
    to_sq = action_idx % 64

    turn = board.turn
    if turn == chess.BLACK:
        real_from = chess.square_mirror(from_sq)
        real_to = chess.square_mirror(to_sq)
    else:
        real_from = from_sq
        real_to = to_sq

    # Verificar se é uma promoção de peão
    piece = board.piece_at(real_from)
    promotion = None
    if piece and piece.piece_type == chess.PAWN:
        target_rank = chess.square_rank(real_to)
        if (piece.color == chess.WHITE and target_rank == 7) or (piece.color == chess.BLACK and target_rank == 0):
            promotion = chess.QUEEN

    candidate = chess.Move(real_from, real_to, promotion=promotion)
    if candidate in board.legal_moves:
        return candidate

    # Se a candidata com dama não for legal (ou sem promoção), tenta as variantes
    for m in board.legal_moves:
        if m.from_square == real_from and m.to_square == real_to:
            return m

    return None


def get_legal_action_mask(board: chess.Board) -> torch.Tensor:
    """Gera uma máscara booleana de 4096 elementos onde True indica lances legais."""
    mask = torch.zeros(ACTION_SIZE, dtype=torch.bool)
    turn = board.turn
    for m in board.legal_moves:
        idx = encode_move(m, turn)
        mask[idx] = True
    return mask
