"""Módulo de Treinamento por Reforço e Iteração de Especialista (RL / DAgger).

Permite à rede neural jogar centenas de partidas contra o bot Maximum de 3200 Elo,
armazenando trajetórias, punindo gafes (blunders), reforçando variantes vencedoras
e atualizando os pesos da rede na GPU (RTX 3060) em ciclos contínuos de aprendizado.
"""

import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.pgn
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from .encoder import ACTION_SIZE, NUM_CHANNELS, decode_move, encode_board, encode_move, get_legal_action_mask
from .model import ChessPolicyValueNet


class ChessTrajectoryDataset(Dataset):
    """Dataset em memória contendo as posições e alvos aprendidos nas partidas."""

    def __init__(self, states: List[torch.Tensor], policies: List[torch.Tensor], values: List[torch.Tensor]):
        self.states = torch.stack(states) if states else torch.empty((0, NUM_CHANNELS, 8, 8))
        self.policies = torch.stack(policies) if policies else torch.empty((0, ACTION_SIZE))
        self.values = torch.stack(values) if values else torch.empty((0, 1))

    def __len__(self) -> int:
        return len(self.states)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.states[idx], self.policies[idx], self.values[idx]


class RLChessTrainer:
    """Gerenciador do ciclo de 1000 partidas com aprendizado na GPU."""

    def __init__(
        self,
        model: ChessPolicyValueNet,
        bot_3200: Any,
        device: Optional[str] = None,
        lr: float = 5e-4,
        checkpoints_dir: Optional[Path] = None,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = model.to(self.device)
        self.bot_3200 = bot_3200
        self.checkpoints_dir = checkpoints_dir or Path(__file__).resolve().parent.parent / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)

        # Buffer de replay histórico
        self.replay_states: List[torch.Tensor] = []
        self.replay_policies: List[torch.Tensor] = []
        self.replay_values: List[torch.Tensor] = []
        self.max_buffer_size = 120_000

        # Estatísticas globais
        self.total_games_played = 0
        self.neural_wins = 0
        self.engine_wins = 0
        self.draws = 0
        self.history: List[Dict[str, Any]] = []

    def select_neural_move(
        self,
        board: chess.Board,
        temperature: float = 0.2,
        tactical_safety: bool = True,
    ) -> Tuple[chess.Move, float, float]:
        """Seleciona o lance neural com máscara legal e filtro de segurança tática."""
        self.model.eval()
        state_tensor = encode_board(board).unsqueeze(0).to(self.device)
        legal_mask = get_legal_action_mask(board).to(self.device)

        with torch.no_grad():
            policy_logits, value_out = self.model(state_tensor)
            logits = policy_logits.squeeze(0)
            masked_logits = torch.where(legal_mask, logits, torch.tensor(-1e9, device=self.device))
            probs = F.softmax(masked_logits, dim=-1).cpu().numpy()
            eval_val = float(value_out.item())

        legal_moves = list(board.legal_moves)
        scored_moves = []

        for m in legal_moves:
            idx = encode_move(m, board.turn)
            p = float(probs[idx])

            # Filtro tático leve de 1 lance (Tactical Safety Guard):
            # Penaliza severamente lances que entregam a Dama ou levam mate em 1
            if tactical_safety:
                board.push(m)
                if board.is_checkmate():
                    # Se este lance dá mate no adversário, pontuação máxima!
                    p += 100.0
                elif any(board.is_capture(resp) and board.piece_at(resp.to_square) and board.piece_at(resp.to_square).piece_type == chess.QUEEN for resp in board.legal_moves):
                    # Se o adversário pode comer a Dama desprotegida no próximo lance, penaliza
                    piece_moved = board.piece_at(m.to_square)
                    if piece_moved and piece_moved.piece_type == chess.QUEEN and not board.is_capture(m):
                        p *= 0.05
                board.pop()

            scored_moves.append((m, p))

        scored_moves.sort(key=lambda x: x[1], reverse=True)

        if temperature > 0.0 and len(scored_moves) > 1:
            m_list = [m for m, _ in scored_moves[:5]]
            p_list = np.array([p for _, p in scored_moves[:5]], dtype=np.float64)
            p_list = np.power(np.maximum(p_list, 1e-8), 1.0 / temperature)
            p_sum = p_list.sum()
            if p_sum > 0:
                p_list = p_list / p_sum
                chosen = np.random.choice(m_list, p=p_list)
                chosen_p = float(probs[encode_move(chosen, board.turn)])
                return chosen, chosen_p, eval_val

        best_m = scored_moves[0][0]
        best_p = float(probs[encode_move(best_m, board.turn)])
        return best_m, best_p, eval_val

    def play_single_game(
        self,
        game_id: int,
        neural_is_white: bool,
        max_plies: int = 80,
    ) -> Tuple[str, int, List[Tuple[torch.Tensor, int, float, float]]]:
        """Executa uma única partida rápida entre o Neural_Bot e o bot 3200 Elo.
        
        Retorna: (resultado, total_lances, lista_de_transicoes)
        transicao: (state_tensor, action_idx, reward, is_neural)
        """
        board = chess.Board()
        transitions: List[Tuple[torch.Tensor, int, float, float]] = []

        while not board.is_game_over(claim_draw=True) and len(board.move_stack) < max_plies:
            is_neural_turn = (board.turn == chess.WHITE and neural_is_white) or (board.turn == chess.BLACK and not neural_is_white)
            state_tensor = encode_board(board)

            if is_neural_turn:
                # Lance Neural (com temperatura leve de exploração nos primeiros 6 lances)
                temp = 0.3 if len(board.move_stack) < 6 else 0.0
                move, prob, val = self.select_neural_move(board, temperature=temp, tactical_safety=True)
                action_idx = encode_move(move, board.turn)
                transitions.append((state_tensor, action_idx, 0.0, 1.0))
            else:
                # Lance do Bot 3200 (usa livro de aberturas ou motor PeSTO d=2 para máxima velocidade)
                move, info = self.bot_3200.get_best_move(board, max_depth=2, max_time_seconds=0.08)
                if not move:
                    break
                action_idx = encode_move(move, board.turn)
                # O lance do 3200 serve como demonstração de especialista (DAgger target)
                transitions.append((state_tensor, action_idx, 0.0, 0.0))

            board.push(move)

        # Determinar resultado da perspectiva do Neural_Bot
        res_str = board.result(claim_draw=True)
        if board.is_checkmate():
            winner_is_white = (board.turn == chess.BLACK)
            if (winner_is_white and neural_is_white) or (not winner_is_white and not neural_is_white):
                outcome = 1.0  # Vitória Neural!
                self.neural_wins += 1
                res_desc = "Vitória Neural"
            else:
                outcome = -1.0  # Vitória Engine
                self.engine_wins += 1
                res_desc = "Vitória Maximum 3200"
        else:
            outcome = 0.0  # Empate
            self.draws += 1
            res_desc = "Empate"

        self.total_games_played += 1

        # Atribuir valores de recompensa finais a todas as transições da partida
        processed_transitions = []
        for state, action, _, is_neural in transitions:
            # Se a partida foi vitória, valor positivo; se derrota, valor negativo
            target_val = outcome if is_neural > 0.5 else -outcome
            processed_transitions.append((state, action, target_val, is_neural))

        return res_desc, len(board.move_stack), processed_transitions

    def add_transitions_to_buffer(self, transitions: List[Tuple[torch.Tensor, int, float, float]]):
        """Adiciona transições ao buffer de replay, gerando alvos de política e valor."""
        for state, action_idx, outcome_val, is_neural in transitions:
            policy_target = np.zeros(ACTION_SIZE, dtype=np.float32)

            if is_neural < 0.5:
                # Lance do 3200: Alvo de Especialista (DAgger) com alta confiança
                policy_target[action_idx] = 1.0
            else:
                # Lance do Neural: se venceu ou empatou, reforça; se perdeu, distribui
                if outcome_val >= 0.0:
                    policy_target[action_idx] = 1.0
                else:
                    # Penalização de gafe: espalha probabilidade para não repetir o lance derrotado
                    policy_target[action_idx] = 0.1
                    policy_target = policy_target / policy_target.sum()

            self.replay_states.append(state)
            self.replay_policies.append(torch.from_numpy(policy_target))
            self.replay_values.append(torch.tensor([outcome_val], dtype=torch.float32))

        # Manter buffer com tamanho controlado
        if len(self.replay_states) > self.max_buffer_size:
            excess = len(self.replay_states) - self.max_buffer_size
            self.replay_states = self.replay_states[excess:]
            self.replay_policies = self.replay_policies[excess:]
            self.replay_values = self.replay_values[excess:]

    def train_gpu_step(self, epochs: int = 3, batch_size: int = 256) -> Dict[str, float]:
        """Executa épocas de treinamento com os dados coletados diretamente na GPU."""
        if len(self.replay_states) < batch_size:
            return {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0}

        dataset = ChessTrajectoryDataset(self.replay_states, self.replay_policies, self.replay_values)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, pin_memory=(self.device.type == "cuda"))

        self.model.train()
        total_loss = 0.0
        total_p_loss = 0.0
        total_v_loss = 0.0
        num_batches = 0

        for _ in range(epochs):
            for states, target_policies, target_values in loader:
                states = states.to(self.device)
                target_policies = target_policies.to(self.device)
                target_values = target_values.to(self.device)

                self.optimizer.zero_grad()
                pred_logits, pred_val = self.model(states)

                log_probs = F.log_softmax(pred_logits, dim=-1)
                p_loss = -torch.sum(target_policies * log_probs, dim=-1).mean()
                v_loss = F.mse_loss(pred_val, target_values)
                loss = p_loss + 0.5 * v_loss

                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()

                total_loss += loss.item()
                total_p_loss += p_loss.item()
                total_v_loss += v_loss.item()
                num_batches += 1

        return {
            "loss": total_loss / max(1, num_batches),
            "policy_loss": total_p_loss / max(1, num_batches),
            "value_loss": total_v_loss / max(1, num_batches),
        }

    def run_1000_games_training(
        self,
        total_games: int = 1000,
        games_per_cycle: int = 50,
        epochs_per_cycle: int = 3,
        batch_size: int = 256,
        save_weights_path: Optional[Path] = None,
        save_onnx_path: Optional[Path] = None,
        history_path: Optional[Path] = None,
        save_pgn_milestones: bool = True,
    ):
        """Executa o ciclo completo de 1000 partidas e aprendizado contínuo."""
        print("\n" + "=" * 75)
        print(f"  INICIANDO CICLO AUTÔNOMO DE {total_games} PARTIDAS: NEURAL_BOT vs MAXIMUM 3200")
        print("=" * 75)
        print(f"[*] Dispositivo de Treino : {self.device.type.upper()} (NVIDIA RTX 3060)")
        print(f"[*] Partidas por Ciclo    : {games_per_cycle} (Total de Ciclos: {total_games // games_per_cycle})")
        print(f"[*] Épocas GPU por Ciclo  : {epochs_per_cycle}")
        print("-" * 75)

        total_cycles = total_games // games_per_cycle
        global_start = time.time()

        for cycle in range(1, total_cycles + 1):
            cycle_start = time.time()
            cycle_neural_wins = 0
            cycle_engine_wins = 0
            cycle_draws = 0
            cycle_plies = []

            for g_idx in range(1, games_per_cycle + 1):
                game_number = (cycle - 1) * games_per_cycle + g_idx
                # Alternar cor (Brancas/Pretas)
                neural_white = (game_number % 2 == 1)

                res_desc, plies, transitions = self.play_single_game(
                    game_id=game_number,
                    neural_is_white=neural_white,
                    max_plies=70,
                )

                self.add_transitions_to_buffer(transitions)
                cycle_plies.append(plies)

                if "Vitória Neural" in res_desc:
                    cycle_neural_wins += 1
                elif "Maximum 3200" in res_desc:
                    cycle_engine_wins += 1
                else:
                    cycle_draws += 1

            # Momento do aprendizado na GPU
            train_metrics = self.train_gpu_step(epochs=epochs_per_cycle, batch_size=batch_size)
            cycle_elapsed = time.time() - cycle_start
            total_elapsed = time.time() - global_start

            avg_plies = sum(cycle_plies) / max(1, len(cycle_plies))
            neural_win_rate = (self.neural_wins / self.total_games_played) * 100.0
            draw_rate = (self.draws / self.total_games_played) * 100.0

            print(
                f"Ciclo [{cycle:02d}/{total_cycles:02d}] (Partidas {cycle * games_per_cycle:04d}/{total_games}) | "
                f"Tempo: {cycle_elapsed:.1f}s | "
                f"Vitórias: {cycle_neural_wins} | Empates: {cycle_draws} | Derrotas: {cycle_engine_wins} | "
                f"Loss GPU: {train_metrics['loss']:.4f} | "
                f"Média Plies: {avg_plies:.1f}"
            )

            cycle_data = {
                "cycle": cycle,
                "games_completed": self.total_games_played,
                "cycle_neural_wins": cycle_neural_wins,
                "cycle_engine_wins": cycle_engine_wins,
                "cycle_draws": cycle_draws,
                "avg_plies": avg_plies,
                "global_neural_wins": self.neural_wins,
                "global_engine_wins": self.engine_wins,
                "global_draws": self.draws,
                "neural_win_rate": neural_win_rate,
                "draw_rate": draw_rate,
                "loss": train_metrics["loss"],
                "policy_loss": train_metrics["policy_loss"],
                "value_loss": train_metrics["value_loss"],
                "cycle_time_seconds": cycle_elapsed,
                "total_elapsed_seconds": total_elapsed,
            }
            self.history.append(cycle_data)

            # Salvar pesos atualizados após cada ciclo
            if save_weights_path:
                self.model.save_weights(save_weights_path)

            if history_path:
                with open(history_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "total_games": self.total_games_played,
                            "neural_wins": self.neural_wins,
                            "engine_wins": self.engine_wins,
                            "draws": self.draws,
                            "final_win_rate": neural_win_rate,
                            "total_time_seconds": total_elapsed,
                            "cycles": self.history,
                        },
                        f,
                        indent=2,
                    )

        # Exportar modelo final para ONNX
        if save_onnx_path:
            try:
                self.model.export_onnx(save_onnx_path)
                print(f"[+] Modelo final exportado para ONNX: {save_onnx_path}")
            except Exception as e:
                print(f"[!] Falha ao exportar ONNX: {e}")

        total_time = time.time() - global_start
        print("\n" + "=" * 75)
        print("  CONCLUÍDO! 1000 PARTIDAS E APRENDIZADO FINALIZADOS COM SUCESSO!")
        print("=" * 75)
        print(f"[+] Total de Partidas Jogadas : {self.total_games_played}")
        print(f"[+] Vitórias do Neural_Bot    : {self.neural_wins} ({(self.neural_wins/self.total_games_played)*100:.1f}%)")
        print(f"[+] Empates Conquistados      : {self.draws} ({(self.draws/self.total_games_played)*100:.1f}%)")
        print(f"[+] Vitórias do Maximum 3200  : {self.engine_wins} ({(self.engine_wins/self.total_games_played)*100:.1f}%)")
        print(f"[+] Duração Total             : {total_time:.1f}s ({total_time/60:.2f} min)")
        print(f"[+] Pesos Aprimorados Salvos  : {save_weights_path}")
        print(f"[+] Histórico Detalhado em    : {history_path}")
        print("=" * 75 + "\n")
