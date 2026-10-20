"""Agente Neural de Xadrez (NeuralChessBot).

Executa inferência direta utilizando a rede neural treinada (ChessPolicyValueNet),
mascarando lances ilegais e selecionando os melhores lances por política neural.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import chess
import chess.polyglot
import numpy as np
import torch
import torch.nn.functional as F

from .encoder import decode_move, encode_board, encode_move, get_legal_action_mask
from .model import ChessPolicyValueNet
from .mcts import NeuralMCTS
from .tactics import (
    find_punitive_captures,
    find_endgame_finishing_move,
    rank_candidates_with_tactical_shield,
)


class NeuralChessBot:
    """Agente de inferência neural para xadrez com suporte a MCTS Tree Search."""

    def __init__(
        self,
        weights_path: Optional[str | Path] = None,
        model: Optional[ChessPolicyValueNet] = None,
        device: Optional[str | torch.device] = None,
        fallback_book_path: Optional[str | Path] = None,
        use_mcts: bool = False,
        mcts_sims: int = 50,
        mcts_c_puct: float = 2.0,
        adaptive_mcts: bool = True,
        adaptive_sims: int = 35,
        use_book: bool = True,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model: Optional[ChessPolicyValueNet] = model
        self.weights_path = Path(weights_path) if weights_path else None
        self.use_book = use_book
        if fallback_book_path:
            self.fallback_book_path = Path(fallback_book_path)
        elif use_book:
            default_book = Path(__file__).resolve().parent.parent.parent / "Scripted_Bot" / "assets" / "balanced.bin"
            self.fallback_book_path = default_book if default_book.is_file() else None
        else:
            self.fallback_book_path = None
        self.use_mcts = use_mcts
        self.mcts_sims = mcts_sims
        self.mcts_c_puct = mcts_c_puct
        self.adaptive_mcts = adaptive_mcts
        self.adaptive_sims = adaptive_sims
        self.mcts: Optional[NeuralMCTS] = None

        if self.model is None:
            self._load_network()
        else:
            self.model.to(self.device)
            self.mcts = NeuralMCTS(self.model, device=self.device, c_puct=self.mcts_c_puct)

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

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return {}, 0.0

        state_tensor = encode_board(board).unsqueeze(0).to(self.device)
        indices = [encode_move(m, board.turn) for m in legal_moves]
        idx_tensor = torch.tensor(indices, device=self.device, dtype=torch.long)

        self.model.eval()
        with torch.inference_mode():
            policy_logits, value = self.model(state_tensor)
            logits = policy_logits.squeeze(0)
            legal_logits = logits[idx_tensor]
            probs = F.softmax(legal_logits, dim=-1).cpu().numpy()
            eval_val = float(value.item())

        move_probs: Dict[chess.Move, float] = {}
        for m, p in zip(legal_moves, probs):
            move_probs[m] = float(p)

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

        # 0. Livro Canônico Polyglot nos primeiros lances de abertura
        if self.use_book and self.fallback_book_path and self.fallback_book_path.is_file() and board.ply() < 16:
            try:
                with chess.polyglot.open_reader(str(self.fallback_book_path)) as reader:
                    entry = reader.get(board)
                    if entry is not None and entry.move in board.legal_moves:
                        return entry.move, {
                            "source": "polyglot_opening_book",
                            "san": board.san(entry.move),
                            "weight": entry.weight,
                            "value": 0.0,
                            "probability": 1.0,
                        }
            except Exception:
                pass

        # 1. Detector de Xeque-Mate Imediato a favor (vitória instantânea)
        for m in legal_moves:
            board.push(m)
            if board.is_checkmate():
                board.pop()
                return m, {
                    "source": "instant_checkmate",
                    "probability": 1.0,
                    "value": 1.0,
                    "san": board.san(m),
                }
            board.pop()

        # 1.5. Módulo Especialista de Finalização de Finais (Endgame Finisher & Anti-Stalemate)
        # Se estiver em final ganho (ex: Dama/Torre vs Rei, ou poucas peças), arremata com técnica forçada
        endgame_res = find_endgame_finishing_move(board, max_depth=4)
        if endgame_res is not None:
            endgame_move, endgame_info = endgame_res
            return endgame_move, endgame_info

        # 2. Gatilho Punitivo Voraz Supremo:
        # Se o adversário pendurou Dama ou Torre limpa (ganho líquido >= 300 cp), captura imediatamente
        punitive_captures = find_punitive_captures(board)
        if punitive_captures:
            best_punish_move, net_delta, reason = punitive_captures[0]
            if net_delta >= 300:
                return best_punish_move, {
                    "source": "punitive_strike",
                    "net_delta": net_delta,
                    "reason": reason,
                    "value": min(1.0, net_delta / 900.0),
                    "san": board.san(best_punish_move),
                }

        # 3. Verificar se deve usar busca em árvore MCTS
        should_mcts = self.use_mcts if use_mcts is None else use_mcts
        if should_mcts:
            if self.mcts is None:
                self.mcts = NeuralMCTS(self.model, device=self.device, c_puct=self.mcts_c_puct)
            sims = num_simulations or self.mcts_sims
            move, stats = self.mcts.search(board, num_simulations=sims, temperature=temperature)
            if move is not None:
                # Escudo Anti-Repetição estrito no MCTS:
                # Se o bot estiver à frente ou empatado e o lance causar repetição tripla, refutar!
                board.push(move)
                causes_rep = board.can_claim_threefold_repetition() or board.is_repetition(3)
                board.pop()

                if not causes_rep:
                    stats["san"] = board.san(move)
                    stats["value"] = stats.get("root_value", 0.0)
                    stats["probability"] = stats.get("best_move_visits", 1) / max(1, sims)
                    return move, stats
                # Se causou repetição, prossegue para a inferência direta protegida com contempt system

        # Inferência direta via política neural (1-pass)
        move_probs, eval_val = self.evaluate_position(board)
        if not move_probs:
            return legal_moves[0], {"source": "fallback_empty"}

        sorted_moves = sorted(move_probs.items(), key=lambda x: x[1], reverse=True)

        # 2. Escudo Tático Híbrido com Gatilho Punitivo Voraz:
        ranked_candidates = rank_candidates_with_tactical_shield(board, sorted_moves, max_eval_candidates=12)
        if ranked_candidates:
            sorted_moves = [(m, p) for m, p, _ in ranked_candidates]

        # 2.1 Escudo Anti-Repetição e Anti-Empate na Inferência Direta (Contempt System):
        piece_vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
        mat_cur = sum(piece_vals.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == board.turn)
        mat_opp = sum(piece_vals.get(p.piece_type, 0) for p in board.piece_map().values() if p.color != board.turn)
        is_ahead = (mat_cur >= mat_opp) or (eval_val >= 0.0)

        if is_ahead and len(sorted_moves) > 1:
            non_draw_moves = []
            for m, p in sorted_moves:
                board.push(m)
                is_draw_3 = board.can_claim_threefold_repetition() or board.is_repetition(3)
                board.pop()
                if not is_draw_3:
                    non_draw_moves.append((m, p))
            if non_draw_moves:
                sorted_moves = non_draw_moves

            if len(sorted_moves) > 1:
                progressive_moves = []
                for m, p in sorted_moves:
                    board.push(m)
                    is_rep2 = board.is_repetition(2)
                    board.pop()
                    if not is_rep2:
                        progressive_moves.append((m, p))
                if progressive_moves:
                    sorted_moves = progressive_moves
        elif not is_ahead and (mat_opp - mat_cur >= 200 or eval_val <= -0.4):
            # Salvação Tática de Finais (Swindle): se estamos perdendo material, o empate por repetição é vitória!
            for m, p in sorted_moves:
                board.push(m)
                can_draw = board.can_claim_threefold_repetition() or board.is_repetition(3) or board.can_claim_fifty_moves()
                board.pop()
                if can_draw:
                    return m, {
                        "source": "tactical_draw_rescue",
                        "probability": 1.0,
                        "value": 0.0,
                        "san": board.san(m),
                    }

        best_move, best_prob = sorted_moves[0]

        # 3. MCTS Adaptativo: se ativado e a posição for aguda (xeque ao nosso rei, incerteza tática ou lance crítico),
        # dispara busca MCTS de 35 nós para refutar armadilhas profundas
        if self.adaptive_mcts and self.mcts is not None and not self.use_mcts:
            is_sharp = board.is_check() or (
                len(sorted_moves) > 1 and (
                    (sorted_moves[0][1] - sorted_moves[1][1]) < 0.18 or
                    best_prob < 0.45 or
                    abs(eval_val) < 0.25
                )
            )
            if is_sharp:
                sims = self.adaptive_sims
                mcts_move, stats = self.mcts.search(board, num_simulations=sims, temperature=0.0)
                if mcts_move is not None:
                    stats["san"] = board.san(mcts_move)
                    stats["value"] = stats.get("root_value", eval_val)
                    stats["probability"] = stats.get("best_move_visits", 1) / max(1, sims)
                    stats["source"] = "adaptive_neural_mcts"
                    return mcts_move, stats

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
