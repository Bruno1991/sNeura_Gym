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
        elif (
            self.board.can_claim_threefold_repetition()
            or self.board.is_repetition(3)
            or self.board.is_game_over(claim_draw=True)
        ):
            self.is_terminal = True
            # Contempt Factor: Se o jogador que tem a vez está com vantagem de material, o empate é punido (-0.80)
            piece_vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
            mat_cur = sum(piece_vals.get(p.piece_type, 0) for p in self.board.piece_map().values() if p.color == self.board.turn)
            mat_opp = sum(piece_vals.get(p.piece_type, 0) for p in self.board.piece_map().values() if p.color != self.board.turn)
            net_advantage = mat_cur - mat_opp
            if net_advantage >= 90:
                self.terminal_value = -0.80
            elif net_advantage <= -90:
                self.terminal_value = 0.25
            else:
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
        q = -self.q_value if self.visit_count > 0 else 0.0
        return q + exploration

    def apply_virtual_loss(self, v_loss: float = 3.0):
        """Aplica Virtual Loss para desencorajar outras travessias do batch de escolher o mesmo nó."""
        self.visit_count += int(v_loss)
        self.total_value -= v_loss

    def revert_virtual_loss(self, v_loss: float = 3.0):
        """Reverte o Virtual Loss aplicado previamente antes da backpropagation do valor real."""
        self.visit_count -= int(v_loss)
        self.total_value += v_loss

    def expand(self, move_priors: Dict[chess.Move, float], transposition_graph: Optional[Dict[int, MCTSNode]] = None):
        """Expande o nó criando filhos para todos os lances legais com seus priors e Zobrist Transposition Graph."""
        self.children.clear()
        for move, prior in move_priors.items():
            if move not in self.board.legal_moves:
                continue
            child_board = self.board.copy(stack=False)
            child_board.push(move)
            z_hash = chess.polyglot.zobrist_hash(child_board)

            # Se a posição já foi explorada em outro ramo da busca, compartilha visitas e valor Q (DAG)
            cached_node = transposition_graph.get(z_hash) if transposition_graph is not None else None
            child_node = MCTSNode(
                board=child_board,
                parent=self,
                parent_move=move,
                prior=prior,
            )
            if cached_node is not None and cached_node.visit_count > 0:
                child_node.visit_count = cached_node.visit_count
                child_node.total_value = cached_node.total_value
            elif transposition_graph is not None:
                transposition_graph[z_hash] = child_node

            self.children[move] = child_node
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
        cache_key = board._transposition_key()
        if cache_key in self.eval_cache:
            return self.eval_cache[cache_key]

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            if board.is_checkmate():
                return {}, -1.0
            return {}, 0.0

        state_tensor = encode_board(board).unsqueeze(0).to(self.device)
        indices = [encode_move(m, board.turn) for m in legal_moves]
        idx_tensor = torch.tensor(indices, device=self.device, dtype=torch.long)

        self.model.eval()
        with torch.inference_mode():
            if self.device.type == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                    policy_logits, value_out = self.model(state_tensor)
            else:
                policy_logits, value_out = self.model(state_tensor)
            logits = policy_logits.squeeze(0)
            legal_logits = logits[idx_tensor]
            probs = F.softmax(legal_logits, dim=-1).cpu().float().numpy()
            eval_val = float(value_out.item())

        move_priors: Dict[chess.Move, float] = {}
        for m, p in zip(legal_moves, probs):
            move_priors[m] = float(p)

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
        self.eval_cache[cache_key] = (move_priors, eval_val)

        return move_priors, eval_val

    def evaluate_batch(self, boards: List[chess.Board]) -> List[Tuple[Dict[chess.Move, float], float]]:
        """Avalia múltiplos tabuleiros em um único batch tensorizado na GPU."""
        results: List[Optional[Tuple[Dict[chess.Move, float], float]]] = [None] * len(boards)
        uncached_indices: List[int] = []
        uncached_tensors: List[torch.Tensor] = []

        for i, b in enumerate(boards):
            ck = b._transposition_key()
            if ck in self.eval_cache:
                results[i] = self.eval_cache[ck]
            elif not list(b.legal_moves):
                val = -1.0 if b.is_checkmate() else 0.0
                res = ({}, val)
                self.eval_cache[ck] = res
                results[i] = res
            else:
                uncached_indices.append(i)
                uncached_tensors.append(encode_board(b))

        if not uncached_tensors:
            return [r for r in results if r is not None]

        batch_tensor = torch.stack(uncached_tensors).to(self.device)
        self.model.eval()
        with torch.inference_mode():
            if self.device.type == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                    batch_policy, batch_value = self.model(batch_tensor)
            else:
                batch_policy, batch_value = self.model(batch_tensor)

            values = batch_value.squeeze(1).cpu().float().numpy()

        for j, orig_idx in enumerate(uncached_indices):
            b = boards[orig_idx]
            legal_moves = list(b.legal_moves)
            indices = [encode_move(m, b.turn) for m in legal_moves]
            idx_t = torch.tensor(indices, device=batch_policy.device, dtype=torch.long)
            logits = batch_policy[j][idx_t]
            probs = F.softmax(logits, dim=-1).cpu().float().numpy()
            eval_val = float(values[j])

            move_priors: Dict[chess.Move, float] = {}
            for m, p in zip(legal_moves, probs):
                move_priors[m] = float(p)
            prior_sum = sum(move_priors.values())
            if prior_sum > 0:
                for m in move_priors:
                    move_priors[m] /= prior_sum
            else:
                u = 1.0 / len(legal_moves)
                for m in move_priors:
                    move_priors[m] = u

            ck = b._transposition_key()
            self.eval_cache[ck] = (move_priors, eval_val)
            results[orig_idx] = (move_priors, eval_val)

        return [r for r in results if r is not None]

    def search(
        self,
        board: chess.Board,
        num_simulations: int = 50,
        temperature: float = 0.0,
        add_noise: bool = False,
        batch_size: int = 8,
    ) -> Tuple[Optional[chess.Move], Dict[str, Any]]:
        """Executa a busca MCTS a partir do estado atual com aceleração tensorizada em batch.
        
        Args:
            board: Tabuleiro atual de xadrez.
            num_simulations: Número de iterações de simulação na árvore.
            temperature: 0.0 para lance com mais visitas (argmax); > 0 para amostragem.
            add_noise: Se True, injeta ruído de Dirichlet na raiz (recomendado no treino).
            batch_size: Tamanho do lote tensorizado para inferência simultânea na GPU.
            
        Returns:
            Tuple[melhor_lance, estatísticas_da_busca]
        """
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None, {"source": "no_legal_moves"}

        # Fast-Path: se houver exatamente um único lance legal (lance forçado/evasão de xeque)
        if len(legal_moves) == 1:
            forced_m = legal_moves[0]
            return forced_m, {
                "source": "forced_only_legal_move",
                "visits": {board.san(forced_m): 1},
                "q_values": {board.san(forced_m): 0.0},
                "root_value": 0.0,
                "simulations": 1,
                "depth_reached": 1,
                "principal_variation": [board.san(forced_m)],
            }

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

        # Injetar Prior Punitivo Voraz na Raiz (Reforço imediato para capturas de peças desprotegidas)
        from .tactics import find_punitive_captures
        punitive_moves = find_punitive_captures(board)
        if punitive_moves:
            for p_move, net_delta, _ in punitive_moves:
                if p_move in root_priors:
                    root_priors[p_move] += (net_delta / 1000.0) * 3.0
            total_p = sum(root_priors.values())
            if total_p > 0:
                root_priors = {m: p / total_p for m, p in root_priors.items()}

        # Injetar Ruído de Dirichlet na raiz para exploração variada se solicitado
        if add_noise and len(root_priors) > 1:
            moves = list(root_priors.keys())
            noise = np.random.dirichlet([self.dirichlet_alpha] * len(moves))
            for i, m in enumerate(moves):
                root_priors[m] = (1.0 - self.dirichlet_eps) * root_priors[m] + self.dirichlet_eps * noise[i]

        transposition_graph: Dict[int, MCTSNode] = {}
        root.expand(root_priors, transposition_graph=transposition_graph)

        max_depth_reached = 0

        # Budget Adaptativo Dinâmico de Simulações MCTS:
        top_prior_val = max(root_priors.values()) if root_priors else 0.0
        is_in_check = board.is_check()
        has_heavy_attack = any(
            board.is_attacked_by(not board.turn, sq)
            for sq, p in board.piece_map().items()
            if p.color == board.turn and p.piece_type in (chess.QUEEN, chess.ROOK)
        )
        effective_sims = num_simulations
        if is_in_check or has_heavy_attack:
            effective_sims = int(num_simulations * 1.5)
        elif top_prior_val >= 0.80 and num_simulations > 35:
            effective_sims = 35

        # Loop principal de simulações MCTS (Batched GPU com Virtual Loss ou Sequencial)
        use_batch = (self.device.type == "cuda" and batch_size > 1 and len(legal_moves) > 1)
        curr_sim = 0

        while curr_sim < effective_sims:
            if not use_batch:
                node = root
                search_path = [node]
                depth = 0

                while node.is_expanded and not node.is_terminal:
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

                if node.is_terminal:
                    value = node.terminal_value
                else:
                    priors, value = self.evaluate_board(node.board)
                    if not node.board.is_game_over(claim_draw=True):
                        node.expand(priors, transposition_graph=transposition_graph)
                        if any(node.board.is_capture(m) for m in node.board.legal_moves):
                            from .tactics import find_punitive_captures
                            punitive = find_punitive_captures(node.board)
                            if punitive:
                                best_gain = max(p[1] for p in punitive)
                                if best_gain >= 180:
                                    value = min(1.0, value + (best_gain / 1000.0) * 0.35)

                for n in reversed(search_path):
                    n.visit_count += 1
                    n.total_value += value
                    value = -value

                curr_sim += 1
            else:
                # Batch Traversal com Virtual Loss
                traversals = []
                for _ in range(min(batch_size, effective_sims - curr_sim)):
                    node = root
                    search_path = [node]
                    depth = 0

                    while node.is_expanded and not node.is_terminal:
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

                    for n in search_path:
                        n.apply_virtual_loss(3.0)

                    traversals.append((node, search_path))

                unexpanded_nodes = []
                for node, _ in traversals:
                    if not node.is_terminal and not node.is_expanded and node not in unexpanded_nodes:
                        unexpanded_nodes.append(node)

                if unexpanded_nodes:
                    eval_results = self.evaluate_batch([n.board for n in unexpanded_nodes])
                    node_eval_map = {n: res for n, res in zip(unexpanded_nodes, eval_results)}
                else:
                    node_eval_map = {}

                for node, search_path in traversals:
                    for n in search_path:
                        n.revert_virtual_loss(3.0)

                    if node.is_terminal:
                        value = node.terminal_value
                    elif not node.is_expanded and node in node_eval_map:
                        priors, value = node_eval_map[node]
                        if not node.board.is_game_over(claim_draw=True):
                            node.expand(priors, transposition_graph=transposition_graph)
                            if any(node.board.is_capture(m) for m in node.board.legal_moves):
                                from .tactics import find_punitive_captures
                                punitive = find_punitive_captures(node.board)
                                if punitive:
                                    best_gain = max(p[1] for p in punitive)
                                    if best_gain >= 180:
                                        value = min(1.0, value + (best_gain / 1000.0) * 0.35)
                    else:
                        value = node.q_value

                    for n in reversed(search_path):
                        n.visit_count += 1
                        n.total_value += value
                        value = -value

                curr_sim += len(traversals)

            # Early Stopping Matemático & Dominância AlphaZero
            if curr_sim >= 30 and (curr_sim % 10 == 0):
                child_visits = sorted([c.visit_count for c in root.children.values()], reverse=True)
                if len(child_visits) >= 2:
                    top_v, sec_v = child_visits[0], child_visits[1]
                    remaining = effective_sims - curr_sim
                    if (top_v - sec_v) > remaining:
                        break
                    if curr_sim >= 40 and top_v >= curr_sim * 0.85:
                        break
                elif len(child_visits) == 1:
                    break

        # 4. ESCOLHA DO MELHOR LANCE NA RAIZ
        visit_counts: Dict[chess.Move, int] = {m: child.visit_count for m, child in root.children.items()}
        q_values: Dict[chess.Move, float] = {m: child.q_value for m, child in root.children.items()}

        sorted_moves = sorted(visit_counts.items(), key=lambda x: x[1], reverse=True)
        if not sorted_moves:
            return legal_moves[0], {"source": "mcts_fallback"}

        # Guarda Tática Anti-Blunder na Raiz:
        # Descarta qualquer lance suicida (mate em 1, mate forçado em 2 ou perda crítica)
        from .tactics import evaluate_tactical_safety
        safe_sorted_moves = []
        for m, visits in sorted_moves:
            is_safe, _, _ = evaluate_tactical_safety(board, m)
            if is_safe:
                safe_sorted_moves.append((m, visits))

        # Se houver lances taticamente seguros, restringe a escolha a eles
        if safe_sorted_moves:
            sorted_moves = safe_sorted_moves

        # 4.1 ESCUDO ANTI-REPETIÇÃO E ANTI-EMPATE NA RAIZ (CONTEMPT SYSTEM):
        # Se estamos com vantagem material ou posicional, NUNCA permita empate por repetição tripla
        # e evite repetição dupla se houver alternativas taticamente seguras!
        piece_vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
        mat_cur = sum(piece_vals.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == board.turn)
        mat_opp = sum(piece_vals.get(p.piece_type, 0) for p in board.piece_map().values() if p.color != board.turn)
        is_ahead = (mat_cur >= mat_opp) or (root_eval >= 0.0)

        if is_ahead and len(sorted_moves) > 1:
            # 1. Elimina qualquer lance que permita empate por repetição tripla imediata
            non_draw_moves = []
            for m, v in sorted_moves:
                board.push(m)
                is_draw_3 = board.can_claim_threefold_repetition() or board.is_repetition(3)
                board.pop()
                if not is_draw_3:
                    non_draw_moves.append((m, v))
            if non_draw_moves:
                sorted_moves = non_draw_moves

            # 2. Se ainda restarem opções, evita repetição dupla (is_repetition(2)) para não oscilar peças
            if len(sorted_moves) > 1:
                progressive_moves = []
                for m, v in sorted_moves:
                    board.push(m)
                    is_rep2 = board.is_repetition(2)
                    board.pop()
                    if not is_rep2:
                        progressive_moves.append((m, v))
                if progressive_moves:
                    sorted_moves = progressive_moves


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
