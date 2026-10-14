"""Pacote chess_ai para redes neurais de xadrez em s_Neura_Gym."""

from .agent import NeuralChessBot
from .dataset import ChessOpeningDataset, extract_polyglot_data
from .encoder import ACTION_SIZE, NUM_CHANNELS, decode_move, encode_board, encode_move, get_legal_action_mask
from .model import ChessPolicyValueNet
from .trainer import PolicyDistillationTrainer
from .rl_trainer import RLChessTrainer

__all__ = [
    "NeuralChessBot",
    "ChessPolicyValueNet",
    "ChessOpeningDataset",
    "PolicyDistillationTrainer",
    "RLChessTrainer",
    "extract_polyglot_data",
    "encode_board",
    "encode_move",
    "decode_move",
    "get_legal_action_mask",
    "ACTION_SIZE",
    "NUM_CHANNELS",
]
