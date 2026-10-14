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
from .mcts import NeuralMCTS


class NeuralChessBot:
    """Agente de inferência neural para xadrez com suporte a MCTS Tree Search."""

    def __init__(
        self,
        weights_path: Optional[str | Path] = None,
        device: Optional[str] = None,
        fallback_book_path: Optional[str | Path] = None,
        use_mcts: bool = False,
        mcts_sims: int = 50,
        mcts_c_puct: float = 2.0,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model: Optional[ChessPolicyValueNet] = None
        self.weights_path = Path(weights_path) if weights_path else None
        self.fallback_book_path = Path(fallback_book_path) if fallback_book_path else None
        self.use_mcts = use_mcts
        self.mcts_sims = mcts_sims
        self.mcts_c_puct = mcts_c_puct
        self.mcts: Optional[NeuralMCTS] = None

        self._load_network()

    def _load_network(self):
        """Carrega a rede e os pesos pré-treinados se disponíveis."""
        if self.weights_path and self.weights_path.is_file():
            try:
                self.model = ChessPolicyValueNet.load_weights(self.weights_path, device=str(self.device))
                print(f"[*] Pesos neurais carregados com sucesso de: {self.weights_path.name}")
                self.mcts = NeuralMCTS(self.model, device=self.device, c_puct=self.mcts_c_puct)
            except Exception as e:
                print(f"[!] Erro ao carregar pesos neurais de {self.weights_path}: {e}")
                self.model = None
                self.mcts = None
        else:
            self.model = None
            self.mcts = None

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
        use_mcts: Optional[bool] = None,
        num_simulations: Optional[int] = None,
    ) -> Tuple[Optional[chess.Move], Dict[str, Any]]:
        """Seleciona o melhor lance segundo a rede neural ou busca MCTS.
        
        Args:
            board: Estado do tabuleiro.
            temperature: Se 0.0, escolhe o lance com maior probabilidade/visitas (Greedy Argmax).
                         Se > 0.0, sorteia proporcionalmente à distribuição ajustada por temperatura.
            use_mcts: Se True, utiliza o Motor de Busca Neural (Tree Search). Se None, usa self.use_mcts.
            num_simulations: Número de simulações para a busca em árvore. Se None, usa self.mcts_sims.
        """
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None, {"source": "game_over"}

        if not self.model:
            # Fallback se a rede ainda não tiver pesos salvos
            return legal_moves[0], {"source": "fallback_uninitialized"}

        # Verificar se deve usar busca em árvore MCTS
        should_mcts = self.use_mcts if use_mcts is None else use_mcts
        if should_mcts:
            if self.mcts is None:
                self.mcts = NeuralMCTS(self.model, device=self.device, c_puct=self.mcts_c_puct)
            sims = num_simulations or self.mcts_sims
            move, stats = self.mcts.search(board, num_simulations=sims, temperature=temperature)
            if move is not None:
                stats["san"] = board.san(move)
                stats["value"] = stats.get("root_value", 0.0)
                stats["probability"] = stats.get("best_move_visits", 1) / max(1, sims)
                return move, stats

        # Inferência direta via política neural (1-pass)
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
