"""Gerenciador de Treinamento Paralelo por Reforço com 64 Workers e AMP FP16 (BatchedRLTrainer).

Coordena 64 partidas simultâneas de xadrez na GPU NVIDIA RTX 3060,
utilizando Automatic Mixed Precision (AMP FP16) com GradScaler da PyTorch,
gerando dezenas de milhares de posições por minuto e otimizando a rede com alta taxa de transferência.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import chess
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from .batched_env import BatchedChessEnv
from .encoder import ACTION_SIZE, NUM_CHANNELS
from .model import ChessPolicyValueNet
from .report_generator import generate_tournament_markdown_report


class BatchedTrajectoryDataset(Dataset):
    """Dataset em memória para transições coletadas pelos 64 workers."""

    def __init__(self, states: List[torch.Tensor], policies: List[torch.Tensor], values: List[torch.Tensor]):
        self.states = torch.stack(states) if states else torch.empty((0, NUM_CHANNELS, 8, 8))
        self.policies = torch.stack(policies) if policies else torch.empty((0, ACTION_SIZE))
        self.values = torch.stack(values) if values else torch.empty((0, 1))

    def __len__(self) -> int:
        return len(self.states)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.states[idx], self.policies[idx], self.values[idx]


class BatchedRLTrainer:
    """Treinador Paralelo de Xadrez com 64 Workers e AMP FP16."""

    def __init__(
        self,
        model: ChessPolicyValueNet,
        bot_3200: Any = None,
        num_workers: int = 64,
        device: Optional[str] = None,
        lr: float = 4e-4,
        checkpoints_dir: Optional[Path] = None,
        use_amp: bool = True,
        bot_pool: Optional[List[Any]] = None,
        max_plies: int = 80,
        engine_pool_workers: int = 8,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = model.to(self.device)
        self.bot_3200 = bot_3200
        self.num_workers = num_workers
        self.use_amp = use_amp and (self.device.type == "cuda")
        self.bot_pool = bot_pool

        self.checkpoints_dir = checkpoints_dir or Path(__file__).resolve().parent.parent / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)

        # PyTorch AMP FP16 GradScaler para Ampere Tensor Cores
        if self.use_amp:
            self.scaler = torch.amp.GradScaler("cuda")
        else:
            self.scaler = None

        # Ambiente paralelo com bot_pool e multiprocessamento para oponentes
        self.env = BatchedChessEnv(
            num_workers=self.num_workers,
            max_plies=max_plies,
            device=self.device,
            bot_pool=self.bot_pool,
            engine_pool_workers=engine_pool_workers,
        )

        # Buffer de replay histórico
        self.replay_states: List[torch.Tensor] = []
        self.replay_policies: List[torch.Tensor] = []
        self.replay_values: List[torch.Tensor] = []
        self.max_buffer_size = 200_000

        # Histórico de métricas
        self.history: List[Dict[str, Any]] = []

    def add_transitions_to_buffer(self, transitions: List[Tuple[torch.Tensor, int, float, float]]):
        """Adiciona transições ao buffer de replay, gerando alvos de política e valor."""
        for state_t, action_idx, outcome_val, is_neural in transitions:
            policy_target = np.zeros(ACTION_SIZE, dtype=np.float32)

            if is_neural < 0.5:
                # Alvo do Especialista 3200 Elo (DAgger)
                policy_target[action_idx] = 1.0
            else:
                # Alvo Neural: reforça vitórias (+1.0), atenua empates e pune derrotas / passividade (<0.0)
                if outcome_val > 0.0:
                    policy_target[action_idx] = 1.0
                elif outcome_val < 0.0:
                    # Derrota ou empate punido contra bot fraco:
                    # Penaliza fortemente o lance perdedor/passivo e dispersa probabilidade
                    policy_target.fill(1.0 / (ACTION_SIZE - 1))
                    policy_target[action_idx] = 0.0001
                    policy_target /= policy_target.sum()
                else:
                    # Empate neutro contra mestre: dispersa parcialmente para incentivar busca de vitória
                    policy_target.fill(0.6 / ACTION_SIZE)
                    policy_target[action_idx] = 0.4
                    policy_target /= policy_target.sum()

            self.replay_states.append(state_t)
            self.replay_policies.append(torch.from_numpy(policy_target))
            self.replay_values.append(torch.tensor([outcome_val], dtype=torch.float32))

        # Manter buffer com tamanho controlado
        if len(self.replay_states) > self.max_buffer_size:
            excess = len(self.replay_states) - self.max_buffer_size
            self.replay_states = self.replay_states[excess:]
            self.replay_policies = self.replay_policies[excess:]
            self.replay_values = self.replay_values[excess:]

    def train_gpu_step_amp(self, epochs: int = 3, batch_size: int = 512) -> Dict[str, float]:
        """Executa épocas de treino utilizando PyTorch AMP FP16 e batch size ampliado."""
        if len(self.replay_states) < batch_size:
            return {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0}

        dataset = BatchedTrajectoryDataset(self.replay_states, self.replay_policies, self.replay_values)
        loader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=True,
            pin_memory=(self.device.type == "cuda"),
            num_workers=0,
        )

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

                if self.use_amp:
                    with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                        pred_logits, pred_val = self.model(states)
                        log_probs = F.log_softmax(pred_logits, dim=-1)
                        p_loss = -torch.sum(target_policies * log_probs, dim=-1).mean()
                        v_loss = F.mse_loss(pred_val, target_values)
                        loss = p_loss + 0.5 * v_loss

                    self.scaler.scale(loss).backward()
                    self.scaler.unscale_(self.optimizer)
                    nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
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

    def run_batched_training(
        self,
        total_games: int = 1000,
        games_per_cycle: int = 100,
        epochs_per_cycle: int = 3,
        batch_size: int = 512,
        save_weights_path: Optional[Path] = None,
        save_onnx_path: Optional[Path] = None,
        history_path: Optional[Path] = None,
        max_hours: Optional[float] = None,
    ):
        """Executa o ciclo de partidas paralelizadas em 64 workers com AMP FP16."""
        print("\n" + "=" * 78)
        print(f"  BATCHED RL TRAINER (64 WORKERS PARALELOS + AMP FP16)")
        if max_hours:
            print(f"  Objetivo: Torneio Contínuo por {max_hours:.2f} Horas | Neural_Bot vs Todos os Bots")
        else:
            print(f"  Objetivo: {total_games} Partidas Paralelas | Neural_Bot vs Todos os Bots")
        print("=" * 78)
        print(f"[*] Dispositivo       : {self.device.type.upper()} ({torch.cuda.get_device_name(0) if self.device.type == 'cuda' else 'CPU'})")
        print(f"[*] Workers Paralelos : {self.num_workers} partidas simultâneas")
        print(f"[*] AMP FP16 Ativo    : {self.use_amp} (NVIDIA Tensor Cores)")
        print(f"[*] Partidas p/ Ciclo : {games_per_cycle}")
        if max_hours:
            print(f"[*] Duração Alvo      : {max_hours:.2f} horas ({(max_hours * 3600):.0f} segundos)")
        else:
            print(f"[*] Total de Ciclos   : {total_games // games_per_cycle}")
        print(f"[*] Batch Size Treino : {batch_size}")
        print("-" * 78)

        max_seconds = (max_hours * 3600.0) if max_hours else None
        total_cycles = 999_999 if max_hours else max(1, total_games // games_per_cycle)
        global_start = time.time()
        
        # Carregamento de checkpoint prévio para retomada contínua (Resume)
        initial_cycle = 0
        cumulative_elapsed = 0.0
        if history_path and Path(history_path).is_file():
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                cycles = saved.get("cycles", [])
                if cycles:
                    self.history = list(cycles)
                    initial_cycle = len(cycles)
                    cumulative_elapsed = float(saved.get("total_time_seconds", 0.0))
                    self.env.total_completed_games = int(saved.get("total_games", self.env.total_completed_games))
                    self.env.neural_wins = int(saved.get("neural_wins", self.env.neural_wins))
                    self.env.engine_wins = int(saved.get("engine_wins", self.env.engine_wins))
                    self.env.draws = int(saved.get("draws", self.env.draws))
                    if "stats_by_tier" in saved and isinstance(saved["stats_by_tier"], dict):
                        self.env.stats_by_tier = saved["stats_by_tier"]
                    if "stats_by_bot" in saved and isinstance(saved["stats_by_bot"], dict):
                        self.env.stats_by_bot = saved["stats_by_bot"]
                    print(f"[*] RESUME ATIVO: Carregadas {self.env.total_completed_games:,} partidas prévias ({initial_cycle} ciclos já concluídos em {cumulative_elapsed/3600:.2f}h).")
            except Exception as e:
                print(f"[!] Aviso: erro ao carregar checkpoint para resume: {e}")

        cycle = initial_cycle
        while True:
            cycle += 1
            if max_seconds is not None and (time.time() - global_start) >= max_seconds:
                print(f"\n[+] Meta de duração atingida: {max_hours:.2f} horas! Finalizando torneio com sucesso.\n", flush=True)
                break
            if max_seconds is None and cycle > total_cycles:
                break

            cycle_start = time.time()
            cycle_target = cycle * games_per_cycle

            cycle_neural_wins = 0
            cycle_engine_wins = 0
            cycle_draws = 0
            cycle_plies_list = []

            # Loop de avanço paralelo dos 64 workers até atingir a meta do ciclo
            while self.env.total_completed_games < cycle_target:
                finished = self.env.step_batch(
                    model=self.model,
                    bot_3200=self.bot_3200,
                    temperature=0.2,
                    use_amp=self.use_amp,
                )
                for transitions, res_str, plies in finished:
                    self.add_transitions_to_buffer(transitions)
                    cycle_plies_list.append(plies)
                    if "Vitória Neural" in res_str:
                        cycle_neural_wins += 1
                    elif "Vitória" in res_str:
                        cycle_engine_wins += 1
                    else:
                        cycle_draws += 1

            # Passo de otimização na GPU com PyTorch AMP FP16
            train_metrics = self.train_gpu_step_amp(epochs=epochs_per_cycle, batch_size=batch_size)
            cycle_elapsed = time.time() - cycle_start
            total_elapsed = cumulative_elapsed + (time.time() - global_start)

            avg_plies = sum(cycle_plies_list) / max(1, len(cycle_plies_list))
            total_played = self.env.total_completed_games
            neural_win_rate = (self.env.neural_wins / max(1, total_played)) * 100.0
            draw_rate = (self.env.draws / max(1, total_played)) * 100.0

            fps = len(self.replay_states) / max(0.1, (time.time() - global_start))

            cycle_tag = f"Ciclo [{cycle:02d}]" if max_hours else f"Ciclo [{cycle:02d}/{total_cycles:02d}]"
            games_tag = f"Partidas: {total_played:05d}" if max_hours else f"Partidas {total_played:05d}/{total_games}"
            time_tag = f"Total: {total_elapsed/3600:4.2f}h ({cycle_elapsed:4.1f}s/c)"

            print(
                f"{cycle_tag} ({games_tag}) | {time_tag} | "
                f"V: {cycle_neural_wins} | E: {cycle_draws} | D: {cycle_engine_wins} | "
                f"Taxa Vit: {neural_win_rate:.1f}% | Loss AMP: {train_metrics['loss']:.4f} | "
                f"Buffer: {len(self.replay_states):,} ({fps:.0f} pos/s)",
                flush=True,
            )

            cycle_data = {
                "cycle": cycle,
                "total_completed_games": total_played,
                "cycle_neural_wins": cycle_neural_wins,
                "cycle_engine_wins": cycle_engine_wins,
                "cycle_draws": cycle_draws,
                "avg_plies": avg_plies,
                "global_neural_wins": self.env.neural_wins,
                "global_engine_wins": self.env.engine_wins,
                "global_draws": self.env.draws,
                "neural_win_rate": neural_win_rate,
                "draw_rate": draw_rate,
                "loss": train_metrics["loss"],
                "policy_loss": train_metrics["policy_loss"],
                "value_loss": train_metrics["value_loss"],
                "buffer_size": len(self.replay_states),
                "cycle_time_seconds": cycle_elapsed,
                "total_elapsed_seconds": total_elapsed,
            }
            self.history.append(cycle_data)

            # Salvar pesos atualizados após cada ciclo
            if save_weights_path:
                try:
                    self.model.save_weights(save_weights_path)
                except Exception as e:
                    print(f"[!] Aviso: erro transitório ao salvar pesos no ciclo {cycle}: {e}")

            if history_path:
                try:
                    with open(history_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "num_workers": self.num_workers,
                                "use_amp": self.use_amp,
                                "max_hours": max_hours,
                                "elapsed_hours": round(total_elapsed / 3600.0, 3),
                                "total_games": total_played,
                                "neural_wins": self.env.neural_wins,
                                "engine_wins": self.env.engine_wins,
                                "draws": self.env.draws,
                                "final_win_rate": neural_win_rate,
                                "draw_rate": draw_rate,
                                "total_time_seconds": total_elapsed,
                                "stats_by_tier": getattr(self.env, "stats_by_tier", {}),
                                "stats_by_bot": getattr(self.env, "stats_by_bot", {}),
                                "cycles": self.history,
                            },
                            f,
                            indent=2,
                        )
                except Exception as e:
                    print(f"[!] Aviso: erro transitório ao salvar histórico JSON no ciclo {cycle}: {e}")

        # Encerramento dos processos do ambiente
        self.env.close()

        # Exportar modelo final para ONNX
        if save_onnx_path:
            try:
                self.model.export_onnx(save_onnx_path)
                print(f"[+] Modelo final exportado com sucesso para ONNX: {save_onnx_path}")
            except Exception as e:
                print(f"[!] Falha na exportação ONNX: {e}")

        total_time = time.time() - global_start
        print("\n" + "=" * 78)
        print("  TREINAMENTO PARALELO DE 1000 PARTIDAS FINALIZADO COM SUCESSO!")
        print("=" * 78)
        print(f"[+] Total de Partidas Concluídas: {self.env.total_completed_games}")
        print(f"[+] Vitórias do Neural_Bot      : {self.env.neural_wins} ({(self.env.neural_wins/max(1, self.env.total_completed_games))*100:.1f}%)")
        print(f"[+] Empates Conquistados        : {self.env.draws} ({(self.env.draws/max(1, self.env.total_completed_games))*100:.1f}%)")
        print(f"[+] Derrotas (Bots Adversários) : {self.env.engine_wins} ({(self.env.engine_wins/max(1, self.env.total_completed_games))*100:.1f}%)")
        print(f"[+] Duração Total               : {total_time:.1f}s ({total_time/60:.2f} min)")
        print(f"[+] Amostras no Buffer Replay   : {len(self.replay_states):,}")
        print(f"[+] Pesos Aprimorados Salvos    : {save_weights_path}")
        print(f"[+] Histórico Detalhado em      : {history_path}")

        if hasattr(self.env, "stats_by_tier") and any(st["wins"] + st["losses"] + st["draws"] > 0 for st in self.env.stats_by_tier.values()):
            print("\n" + "=" * 78)
            print("  DESEMPENHO POR FAIXA DE ELO DOS ADVERSÁRIOS (MULTI-BOT):")
            print("=" * 78)
            for tier, st in self.env.stats_by_tier.items():
                tot = st["wins"] + st["losses"] + st["draws"]
                if tot > 0:
                    pct = ((st["wins"] + 0.5 * st["draws"]) / tot) * 100
                    print(f"  * {tier:<26} | Partidas: {tot:<4} | V: {st['wins']:<3} | E: {st['draws']:<3} | D: {st['losses']:<3} | Score: {pct:.1f}%")
            print("=" * 78)

        if hasattr(self.env, "stats_by_bot") and any(st["wins"] + st["losses"] + st["draws"] > 0 for st in self.env.stats_by_bot.values()):
            print("\n" + "=" * 78)
            print("  DESEMPENHO INDIVIDUAL CONTRA CADA BOT (CHESS.COM):")
            print("=" * 78)
            sorted_bots = sorted(self.env.stats_by_bot.items(), key=lambda x: x[1].get("rating", 0))
            for b_name, b_st in sorted_bots:
                tot = b_st["wins"] + b_st["losses"] + b_st["draws"]
                if tot > 0:
                    pct = ((b_st["wins"] + 0.5 * b_st["draws"]) / tot) * 100
                    print(f"  * {b_name:<20} (Elo {b_st.get('rating', '?'):<4}) | Partidas: {tot:<3} | V: {b_st['wins']:<2} | E: {b_st['draws']:<2} | D: {b_st['losses']:<2} | Score: {pct:5.1f}%")
            print("=" * 78)
        print("=" * 78 + "\n")

        # Salvar relatório analítico consolidado no diretório exclusivo de avanços do projeto
        reports_dir = Path("C:/dev/s_Neura_Gym/chess_bot/relatorios_avancos")
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"relatorio_torneio_{self.env.total_completed_games}_partidas.md"
        history_payload = {
            "num_workers": self.num_workers,
            "use_amp": self.use_amp,
            "max_hours": max_hours,
            "elapsed_hours": round(total_elapsed / 3600.0, 3),
            "total_games": self.env.total_completed_games,
            "neural_wins": self.env.neural_wins,
            "engine_wins": self.env.engine_wins,
            "draws": self.env.draws,
            "final_win_rate": (self.env.neural_wins / max(1, self.env.total_completed_games)) * 100.0,
            "draw_rate": (self.env.draws / max(1, self.env.total_completed_games)) * 100.0,
            "total_time_seconds": total_elapsed,
            "stats_by_tier": getattr(self.env, "stats_by_tier", {}),
            "stats_by_bot": getattr(self.env, "stats_by_bot", {}),
            "cycles": self.history,
        }
        try:
            generate_tournament_markdown_report(history_payload, report_path)
            print(f"[+] Relatório analítico detalhado salvo com sucesso em: {report_path}")
        except Exception as e:
            print(f"[!] Erro ao gerar relatório markdown: {e}")

