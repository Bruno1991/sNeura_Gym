"""Agente Neural de Xadrez (NeuralChessBot).

Executa inferência direta utilizando a rede neural treinada (ChessPolicyValueNet),
mascarando lances ilegais e selecionando os melhores lances por política neural.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import chess
import numpy as np
import torch
import torch.nn.functional as F

from .encoder import decode_move, encode_board, encode_move, get_legal_action_mask
from .model import ChessPolicyValueNet


class NeuralChessBot:
    """Agente de inferência neural para xadrez."""

    def __init__(
        self,
        weights_path: Optional[str | Path] = None,
        device: Optional[str] = None,
        fallback_book_path: Optional[str | Path] = None,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model: Optional[ChessPolicyValueNet] = None
        self.weights_path = Path(weights_path) if weights_path else None
        self.fallback_book_path = Path(fallback_book_path) if fallback_book_path else None

        self._load_network()

    def _load_network(self):
        """Carrega a rede e os pesos pré-treinados se disponíveis."""
        if self.weights_path and self.weights_path.is_file():
            try:
                self.model = ChessPolicyValueNet.load_weights(self.weights_path, device=str(self.device))
                print(f"[*] Pesos neurais carregados com sucesso de: {self.weights_path.name}")
            except Exception as e:
                print(f"[!] Erro ao carregar pesos neurais de {self.weights_path}: {e}")
                self.model = None
        else:
            self.model = None

    def is_ready(self) -> bool:
        """Verifica se o modelo neural está carregado e pronto para inferência."""
        return self.model is not None

    def evaluate_position(self, board: chess.Board) -> Tuple[Dict[chess.Move, float], float]:
        """Calcula as probabilidades de todos os lances legais e o valor posicional."""
        if not self.model or board.is_game_over():
            return {}, 0.0

        state_tensor = encode_board(board).unsqueeze(0).to(self.device)
        legal_mask = get_legal_action_mask(board).to(self.device)

        with torch.no_grad():
            policy_logits, value = self.model(state_tensor)
            logits = policy_logits.squeeze(0)

            # Mascarar lances ilegais com valor negativo extremo (-inf)
            masked_logits = torch.where(legal_mask, logits, torch.tensor(-1e9, device=self.device))
            probs = F.softmax(masked_logits, dim=-1).cpu().numpy()
            eval_val = float(value.item())

        move_probs: Dict[chess.Move, float] = {}
        for m in board.legal_moves:
            idx = encode_move(m, board.turn)
            move_probs[m] = float(probs[idx])

        return move_probs, eval_val

    def get_best_move(
        self,
        board: chess.Board,
        temperature: float = 0.0,
    ) -> Tuple[Optional[chess.Move], Dict[str, Any]]:
        """Seleciona o melhor lance segundo a rede neural.
        
        Args:
            board: Estado do tabuleiro.
            temperature: Se 0.0, escolhe o lance com maior probabilidade (Greedy Argmax).
                         Se > 0.0, sorteia proporcionalmente à probabilidade ajustada por temperatura.
        """
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None, {"source": "game_over"}

        if not self.model:
            # Fallback se a rede ainda não tiver pesos salvos
            return legal_moves[0], {"source": "fallback_uninitialized"}

        move_probs, eval_val = self.evaluate_position(board)
        if not move_probs:
            return legal_moves[0], {"source": "fallback_empty"}

        sorted_moves = sorted(move_probs.items(), key=lambda x: x[1], reverse=True)
        best_move, best_prob = sorted_moves[0]

        if temperature > 0.0 and len(move_probs) > 1:
            moves = [m for m, _ in sorted_moves]
            probs = np.array([p for _, p in sorted_moves], dtype=np.float64)
            # Aplicar temperatura
            probs = np.power(np.maximum(probs, 1e-8), 1.0 / temperature)
            probs = probs / np.sum(probs)
            chosen_move = np.random.choice(moves, p=probs)
            chosen_prob = float(move_probs[chosen_move])
            return chosen_move, {
                "source": "neural_policy_sampled",
                "probability": chosen_prob,
                "value": eval_val,
                "temperature": temperature,
                "san": board.san(chosen_move),
            }

        return best_move, {
            "source": "neural_policy_argmax",
            "probability": best_prob,
            "value": eval_val,
            "san": board.san(best_move),
            "top_candidates": [
                {"san": board.san(m), "prob": round(p, 4)} for m, p in sorted_moves[:3]
            ],
        }
