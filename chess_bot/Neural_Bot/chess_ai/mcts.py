"""Motor de Busca Neural (Neural MCTS / Monte Carlo Tree Search).

Implementa busca em árvore guiada pela rede neural com fórmula PUCT (estilo AlphaZero / Leela Chess Zero),
transposition table (cache de avaliações), ruído de Dirichlet para exploração e backpropagation minimax.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import chess
import numpy as np
import torch
import torch.nn.functional as F

from .encoder import ACTION_SIZE, NUM_CHANNELS, decode_move, encode_board, encode_move, get_legal_action_mask
from .model import ChessPolicyValueNet


class MCTSNode:
    """Nó individual da árvore de busca Monte Carlo."""

    __slots__ = (
        "board",
        "parent",
        "parent_move",
        "children",
        "visit_count",
        "total_value",
        "prior",
        "is_expanded",
        "is_terminal",
        "terminal_value",
    )

    def __init__(
        self,
        board: chess.Board,
        parent: Optional[MCTSNode] = None,
        parent_move: Optional[chess.Move] = None,
        prior: float = 0.0,
    ):
        self.board = board
        self.parent = parent
        self.parent_move = parent_move
        self.children: Dict[chess.Move, MCTSNode] = {}
        self.visit_count: int = 0
        self.total_value: float = 0.0
        self.prior: float = prior
        self.is_expanded: bool = False
        self.is_terminal: bool = False
        self.terminal_value: float = 0.0

        # Checar se este nó é estado terminal
        self._check_terminal()

    def _check_terminal(self):
        """Verifica se o estado é xeque-mate ou empate."""
        if self.board.is_checkmate():
            self.is_terminal = True
            # Quem tem a vez de jogar está em xeque-mate, portanto perdeu (-1.0)
            self.terminal_value = -1.0
        elif self.board.is_game_over(claim_draw=True):
            self.is_terminal = True
            self.terminal_value = 0.0

    @property
    def q_value(self) -> float:
        """Valor médio de ação Q = W / N."""
        if self.visit_count == 0:
            return 0.0
        return self.total_value / self.visit_count

    def puct_score(self, c_puct: float, parent_visits: int) -> float:
        """Calcula o score PUCT da perspectiva do nó pai.
        
        Score = -Q(filho) + c_puct * P * sqrt(N_pai) / (1 + N_filho)
        Nota: -Q(filho) porque o valor do filho é da perspectiva do oponente.
        """
        exploration = c_puct * self.prior * (math.sqrt(parent_visits) / (1.0 + self.visit_count))
        # Se o filho ainda não foi visitado, o valor estimado de Q é neutro (0.0)
        q = -self.q_value if self.visit_count > 0 else 0.0
        return q + exploration

    def expand(self, move_priors: Dict[chess.Move, float]):
        """Expande o nó criando filhos para todos os lances legais com seus priors."""
        self.children.clear()
        for move, prior in move_priors.items():
            child_board = self.board.copy(stack=False)
            child_board.push(move)
            self.children[move] = MCTSNode(
                board=child_board,
                parent=self,
                parent_move=move,
                prior=prior,
            )
        self.is_expanded = True


class NeuralMCTS:
    """Motor de Busca Neural em Árvore (MCTS com PUCT).
    
    Combina a intuição da rede (política prior + valor) com cálculo antecipado
    de variantes táticas, garantindo eliminação de gafes e conversão de vantagens.
    """

    def __init__(
        self,
        model: ChessPolicyValueNet,
        device: Optional[torch.device | str] = None,
        c_puct: float = 2.0,
        dirichlet_alpha: float = 0.3,
        dirichlet_eps: float = 0.25,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = model.to(self.device)
        self.c_puct = c_puct
        self.dirichlet_alpha = dirichlet_alpha
        self.dirichlet_eps = dirichlet_eps

        # Tabela de transposição em memória para reutilizar avaliações da rede
        self.eval_cache: Dict[str, Tuple[Dict[chess.Move, float], float]] = {}

    def clear_cache(self):
        """Limpa o cache de avaliações."""
        self.eval_cache.clear()

    def evaluate_board(self, board: chess.Board) -> Tuple[Dict[chess.Move, float], float]:
        """Avalia um tabuleiro usando a rede neural e cache de transposição."""
        board_fen = board.fen()
        if board_fen in self.eval_cache:
            return self.eval_cache[board_fen]

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            if board.is_checkmate():
                return {}, -1.0
            return {}, 0.0

        state_tensor = encode_board(board).unsqueeze(0).to(self.device)
        legal_mask = get_legal_action_mask(board).to(self.device)

        self.model.eval()
        with torch.no_grad():
            policy_logits, value_out = self.model(state_tensor)
            logits = policy_logits.squeeze(0)
            masked_logits = torch.where(legal_mask, logits, torch.tensor(-1e9, device=self.device))
            probs = F.softmax(masked_logits, dim=-1).cpu().numpy()
            eval_val = float(value_out.item())

        move_priors: Dict[chess.Move, float] = {}
        for m in legal_moves:
            idx = encode_move(m, board.turn)
            move_priors[m] = float(probs[idx])

        # Normalizar priors caso haja desvios numéricos
        prior_sum = sum(move_priors.values())
        if prior_sum > 0:
            for m in move_priors:
                move_priors[m] /= prior_sum
        else:
            uniform_p = 1.0 / len(legal_moves)
            for m in move_priors:
                move_priors[m] = uniform_p

        # Guardar no cache de transposição
        if len(self.eval_cache) > 200_000:
            self.eval_cache.clear()
        self.eval_cache[board_fen] = (move_priors, eval_val)

        return move_priors, eval_val

    def search(
        self,
        board: chess.Board,
        num_simulations: int = 50,
        temperature: float = 0.0,
        add_noise: bool = False,
    ) -> Tuple[Optional[chess.Move], Dict[str, Any]]:
        """Executa a busca MCTS a partir do estado atual.
        
        Args:
            board: Tabuleiro atual de xadrez.
            num_simulations: Número de iterações de simulação na árvore.
            temperature: 0.0 para lance com mais visitas (argmax); > 0 para amostragem.
            add_noise: Se True, injeta ruído de Dirichlet na raiz (recomendado no treino).
            
        Returns:
            Tuple[melhor_lance, estatísticas_da_busca]
        """
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None, {"source": "no_legal_moves"}

        # Detector tático instantâneo de mate em 1
        for m in legal_moves:
            board.push(m)
            if board.is_checkmate():
                board.pop()
                return m, {
                    "source": "mcts_instant_checkmate",
                    "visits": {board.san(m): num_simulations},
                    "q_values": {board.san(m): 1.0},
                    "root_value": 1.0,
                    "simulations": 1,
                    "depth_reached": 1,
                    "principal_variation": [board.san(m)],
                }
            board.pop()

        root = MCTSNode(board=board.copy())
        root_priors, root_eval = self.evaluate_board(root.board)

        if not root_priors:
            return legal_moves[0], {"source": "root_no_priors"}

        # Injetar Ruído de Dirichlet na raiz para exploração variada se solicitado
        if add_noise and len(root_priors) > 1:
            moves = list(root_priors.keys())
            noise = np.random.dirichlet([self.dirichlet_alpha] * len(moves))
            for i, m in enumerate(moves):
                root_priors[m] = (1.0 - self.dirichlet_eps) * root_priors[m] + self.dirichlet_eps * noise[i]

        root.expand(root_priors)

        max_depth_reached = 0

        # Loop principal de simulações MCTS
        for _ in range(num_simulations):
            node = root
            search_path = [node]
            depth = 0

            # 1. SELEÇÃO: Desce pela árvore até encontrar um nó folha
            while node.is_expanded and not node.is_terminal:
                # Escolhe o filho que maximiza a fórmula PUCT
                best_score = -float("inf")
                best_child = None

                for child in node.children.values():
                    score = child.puct_score(self.c_puct, node.visit_count)
                    if score > best_score:
                        best_score = score
                        best_child = child

                if best_child is None:
                    break

                node = best_child
                search_path.append(node)
                depth += 1

            if depth > max_depth_reached:
                max_depth_reached = depth

            # 2. EXPANSÃO E AVALIAÇÃO DO NÓ FOLHA
            if node.is_terminal:
                value = node.terminal_value
            else:
                priors, value = self.evaluate_board(node.board)
                if not node.board.is_game_over(claim_draw=True):
                    node.expand(priors)

            # 3. BACKPROPAGATION (MINIMAX RETROSPECTIVO)
            # O valor 'value' é da perspectiva do jogador com a vez no nó folha.
            # Cada nível acima inverte o sinal do valor.
            for n in reversed(search_path):
                n.visit_count += 1
                n.total_value += value
                value = -value

        # 4. ESCOLHA DO MELHOR LANCE NA RAIZ
        visit_counts: Dict[chess.Move, int] = {m: child.visit_count for m, child in root.children.items()}
        q_values: Dict[chess.Move, float] = {m: child.q_value for m, child in root.children.items()}

        sorted_moves = sorted(visit_counts.items(), key=lambda x: x[1], reverse=True)
        if not sorted_moves:
            return legal_moves[0], {"source": "mcts_fallback"}

        if temperature > 0.0 and len(sorted_moves) > 1:
            moves = [m for m, _ in sorted_moves]
            counts = np.array([c for _, c in sorted_moves], dtype=np.float64)
            # Distribuição de probabilidade baseada no número de visitas
            probs = np.power(np.maximum(counts, 1e-4), 1.0 / temperature)
            p_sum = probs.sum()
            if p_sum > 0:
                probs /= p_sum
                chosen_idx = np.random.choice(len(moves), p=probs)
                best_move = moves[chosen_idx]
            else:
                best_move = sorted_moves[0][0]
        else:
            best_move = sorted_moves[0][0]

        # Extrair Linha Principal (Principal Variation - PV)
        pv: List[str] = []
        curr = root
        for _ in range(5):
            if not curr.children:
                break
            best_next_m = max(curr.children.keys(), key=lambda m: curr.children[m].visit_count)
            pv.append(curr.board.san(best_next_m))
            curr = curr.children[best_next_m]
            if curr.visit_count <= 1:
                break

        stats = {
            "source": "neural_mcts",
            "simulations": num_simulations,
            "depth_reached": max_depth_reached,
            "root_value": -root.children[best_move].q_value if best_move in root.children else root_eval,
            "best_move_visits": visit_counts.get(best_move, 0),
            "best_move_q": q_values.get(best_move, 0.0),
            "principal_variation": pv,
            "visits": {board.san(m): c for m, c in sorted_moves[:5]},
            "top_q": {board.san(m): round(q_values[m], 3) for m, _ in sorted_moves[:5]},
        }

        return best_move, stats
