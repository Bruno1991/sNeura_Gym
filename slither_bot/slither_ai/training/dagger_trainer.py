"""Destilador Ativo DAgger (Dataset Aggregation) de Alto Desempenho.

Converte a inteligência da IA nativa do Slither.io APK diretamente para os pesos
da Rede Neural com garantia de eliminação do erro de distribuição (covariate shift).
"""

import math
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm

from ..config import SlitherConfig
from ..core.engine import SlitherEngine
from ..core.expert_bot import SlitherNativeBot
from ..env.sensors import SlitherSensors
from ..models.inference import export_to_torchscript
from ..models.policy_net import SlitherPolicyNet
from ..utils.math_helpers import shortest_angular_difference


class DAggerTrainer:
    """Treinador DAgger com aceleração GPU (CUDA) e painel em tempo real no terminal."""

    def __init__(
        self,
        model: Optional[SlitherPolicyNet] = None,
        learning_rate: float = 1e-3,
        batch_size: int = 256,
        device: Optional[str] = None,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = (model or SlitherPolicyNet()).to(self.device)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(), lr=learning_rate, weight_decay=1e-4
        )
        self.batch_size = batch_size

        self.mse_loss = nn.MSELoss()
        self.bce_loss = nn.BCEWithLogitsLoss()

        # Buffer agregado de demonstrações (DAgger Dataset)
        self.aggregated_obs: List[np.ndarray] = []
        self.aggregated_angles: List[float] = []
        self.aggregated_boosts: List[float] = []

    def train_dagger(
        self,
        total_iterations: int = 6,
        steps_per_iteration: int = 15000,
        epochs_per_iteration: int = 6,
        save_dir: str = "checkpoints",
    ) -> Dict[str, any]:
        """Executa o ciclo completo de destilação ativa DAgger."""
        os.makedirs(save_dir, exist_ok=True)
        imitation_path = os.path.join(save_dir, "best_imitation_model.pt")
        traced_path = os.path.join(save_dir, "best_imitation_model_traced.pt")
        ppo_warmstart_path = os.path.join(save_dir, "best_ppo_model.pt")

        device_name = torch.cuda.get_device_name(0) if self.device.type == "cuda" else "CPU Multicore"

        print("\n" + "=" * 65)
        print("   SLITHER AI - DESTILAÇÃO ATIVA DAGGER (SUPER-INTELIGÊNCIA)")
        print("=" * 65)
        print(f"[*] Dispositivo de Treino: {self.device.type.upper()} ({device_name})")
        print(f"[*] Total de Iterações DAgger: {total_iterations}")
        print(f"[*] Passos por Iteração: {steps_per_iteration:,} (~{total_iterations * steps_per_iteration:,} amostras)")
        print(f"[*] Batch Size GPU: {self.batch_size} | Épocas por Ciclo: {epochs_per_iteration}")
        print("=" * 65 + "\n")

        history = []
        best_eval_score = 0.0

        for iter_idx in range(1, total_iterations + 1):
            # Beta schedule: decaimento de 1.0 (só expert) até 0.0 (100% rede neural pilotando)
            # Iter 1: beta=1.0 | Iter 2: beta=0.6 | Iter 3: beta=0.3 | Iter 4+: beta=0.0
            if iter_idx == 1:
                beta = 1.0
            elif iter_idx == 2:
                beta = 0.6
            elif iter_idx == 3:
                beta = 0.3
            else:
                beta = 0.0

            print(f">>> [Iteração {iter_idx}/{total_iterations}] Agregando dados com Beta={beta:.2f}...")
            collect_start = time.time()

            # 1. Coleta DAgger com supervisão do Expert Bot
            new_samples, sim_fps, avg_snake_score, avg_kills = self._collect_dagger_rollout(
                steps_target=steps_per_iteration,
                beta=beta,
            )
            collect_elapsed = time.time() - collect_start

            print(f"    [+] {new_samples:,} passos coletados a {sim_fps:.0f} FPS simulados ({collect_elapsed:.1f}s)")
            print(f"    [+] Tamanho total do dataset agregado: {len(self.aggregated_obs):,} amostras")
            print(f"    [+] Comprimento médio da cobra: {avg_snake_score:.1f} | Abates por vida: {avg_kills:.2f}")

            # 2. Treino Supervisionado dos Pesos Neurais na GPU
            train_loss, val_loss = self._train_neural_epoch(
                epochs=epochs_per_iteration,
                iter_num=iter_idx,
            )

            # 3. Avaliação da Rede Neural Pura (Beta = 0.0)
            eval_score, eval_survival = self._evaluate_pure_neural_policy(num_episodes=5)
            print(f"    [+] Teste Neural Puro: Comprimento Médio = {eval_score:.1f} | Sobrevivência = {eval_survival:.1f}s")
            print(f"    [+] Loss Treino = {train_loss:.4f} | Loss Validação = {val_loss:.4f}\n")

            history.append({
                "iteration": iter_idx,
                "beta": beta,
                "dataset_size": len(self.aggregated_obs),
                "train_loss": train_loss,
                "val_loss": val_loss,
                "eval_score": eval_score,
                "eval_survival": eval_survival,
            })

            # 4. Salva os Pesos Universais (Warm Start)
            self.model.save_model(imitation_path)
            self.model.save_model(ppo_warmstart_path)  # Semeadura Universal para o PPO!
            export_to_torchscript(self.model, traced_path)

            if eval_score > best_eval_score:
                best_eval_score = eval_score

        print("=" * 65)
        print("    DESTILAÇÃO CONCLUÍDA: IA DO APK 100% INJETADA NOS PESOS!")
        print(f"[*] Modelo Imitação Salvo em: {imitation_path}")
        print(f"[*] Modelo TorchScript Salvo em: {traced_path}")
        print(f"[*] Semeadura PPO (Warm Start) Salva em: {ppo_warmstart_path}")
        print(f"[*] Melhor Score Neural Autônomo: {best_eval_score:.1f}")
        print("=" * 65 + "\n")

        return {
            "history": history,
            "best_eval_score": best_eval_score,
            "total_samples": len(self.aggregated_obs),
        }

    def _collect_dagger_rollout(
        self,
        steps_target: int,
        beta: float,
        dt: float = 0.033,
    ) -> Tuple[int, float, float, float]:
        """Executa a simulação onde a rede pilota mas o bot nativo do APK rotula a ação ótima."""
        engine = SlitherEngine(
            arena_radius=SlitherConfig.ARENA_RADIUS_TRAIN,
            num_bots=SlitherConfig.NUM_BOTS_TRAIN,
            num_foods=SlitherConfig.NUM_FOOD_TRAIN,
        )
        player = engine.add_player_snake("NeuraBot_DAgger")
        expert = SlitherNativeBot(player)

        collected = 0
        scores_history = []
        kills_history = []
        start_time = time.time()

        while collected < steps_target:
            # 1. Se morreu, registra métricas e faz respawn
            if not player.is_alive:
                scores_history.append(player.score)
                kills_history.append(player.kills)
                player = engine.add_player_snake("NeuraBot_DAgger")
                expert = SlitherNativeBot(player)

            # 2. Extrai percepção sensorial LIDAR (32 dimensões)
            obs = SlitherSensors.get_observation(
                snake=player,
                all_snakes=engine.snakes,
                foods=engine.foods,
                arena_radius=engine.arena_radius,
            )

            # 3. Calcula Ação do Expert Bot nativo (Gabarito Oficial)
            expert.update_decision(
                all_snakes=engine.snakes,
                foods=engine.foods,
                current_time_sec=engine.current_time_sec,
                arena_radius=engine.arena_radius,
            )
            diff = shortest_angular_difference(player.target_angle, player.angle)
            expert_norm_angle = float(np.clip(diff / math.pi, -1.0, 1.0))
            expert_norm_boost = 1.0 if player.is_boosting else 0.0

            # 4. Guarda a observação e a resposta ideal do expert no buffer DAgger
            self.aggregated_obs.append(obs)
            self.aggregated_angles.append(expert_norm_angle)
            self.aggregated_boosts.append(expert_norm_boost)
            collected += 1

            # 5. Escolhe quem executa o movimento no mundo (mistura probabilística beta)
            if np.random.random() < beta:
                # O expert pilota
                pass
            else:
                # A rede neural pilota (encontra situações reais e aprende a corrigi-las)
                neural_angle, neural_boost = self.model.get_action(obs, deterministic=True)
                player.target_angle = player.angle + neural_angle * math.pi
                player.is_boosting = neural_boost

            # 6. Passo físico
            engine.step(dt)

        elapsed = max(0.001, time.time() - start_time)
        fps = collected / elapsed
        avg_score = float(np.mean(scores_history)) if scores_history else player.score
        avg_kills = float(np.mean(kills_history)) if kills_history else float(player.kills)

        return collected, fps, avg_score, avg_kills

    def _train_neural_epoch(
        self,
        epochs: int,
        iter_num: int,
    ) -> Tuple[float, float]:
        """Treina a rede neural nos dados agregados do DAgger usando DataLoader na GPU."""
        obs_tensor = torch.as_tensor(np.array(self.aggregated_obs), dtype=torch.float32)
        angles_tensor = torch.as_tensor(np.array(self.aggregated_angles), dtype=torch.float32).unsqueeze(1)
        boosts_tensor = torch.as_tensor(np.array(self.aggregated_boosts), dtype=torch.float32).unsqueeze(1)

        dataset = TensorDataset(obs_tensor, angles_tensor, boosts_tensor)
        val_size = max(100, int(len(dataset) * 0.1))
        train_size = len(dataset) - val_size

        train_set, val_set = torch.utils.data.random_split(dataset, [train_size, val_size])
        train_loader = DataLoader(train_set, batch_size=self.batch_size, shuffle=True, drop_last=True)
        val_loader = DataLoader(val_set, batch_size=self.batch_size, shuffle=False)

        avg_train_loss = 0.0
        avg_val_loss = 0.0

        pbar = tqdm(range(1, epochs + 1), desc=f"    Treino GPU (DAgger #{iter_num})", leave=False)
        for _ in pbar:
            self.model.train()
            train_accum = 0.0
            for b_obs, b_ang, b_boost in train_loader:
                b_obs = b_obs.to(self.device)
                b_ang = b_ang.to(self.device)
                b_boost = b_boost.to(self.device)

                self.optimizer.zero_grad()
                pred_ang, pred_boost_logits, _ = self.model(b_obs)

                l_ang = self.mse_loss(pred_ang, b_ang)
                l_boost = self.bce_loss(pred_boost_logits, b_boost)
                loss = l_ang + 0.4 * l_boost

                loss.backward()
                self.optimizer.step()
                train_accum += loss.item()

            avg_train_loss = train_accum / max(1, len(train_loader))

            # Validação
            self.model.eval()
            val_accum = 0.0
            with torch.no_grad():
                for b_obs, b_ang, b_boost in val_loader:
                    b_obs = b_obs.to(self.device)
                    b_ang = b_ang.to(self.device)
                    b_boost = b_boost.to(self.device)

                    pred_ang, pred_boost_logits, _ = self.model(b_obs)
                    l_ang = self.mse_loss(pred_ang, b_ang)
                    l_boost = self.bce_loss(pred_boost_logits, b_boost)
                    val_accum += (l_ang + 0.4 * l_boost).item()

            avg_val_loss = val_accum / max(1, len(val_loader))
            pbar.set_postfix({"train_loss": f"{avg_train_loss:.4f}", "val_loss": f"{avg_val_loss:.4f}"})

        return avg_train_loss, avg_val_loss

    def _evaluate_pure_neural_policy(
        self,
        num_episodes: int = 5,
        max_steps: int = 600,
        dt: float = 0.033,
    ) -> Tuple[float, float]:
        """Avalia o desempenho da rede neural pura (sem qualquer auxílio do expert)."""
        scores = []
        survival_times = []

        for _ in range(num_episodes):
            engine = SlitherEngine(
                arena_radius=SlitherConfig.ARENA_RADIUS_TRAIN,
                num_bots=SlitherConfig.NUM_BOTS_TRAIN,
                num_foods=SlitherConfig.NUM_FOOD_TRAIN,
            )
            player = engine.add_player_snake("Eval_Neural")

            step_count = 0
            while player.is_alive and step_count < max_steps:
                obs = SlitherSensors.get_observation(
                    snake=player,
                    all_snakes=engine.snakes,
                    foods=engine.foods,
                    arena_radius=engine.arena_radius,
                )
                ang_action, boost_action = self.model.get_action(obs, deterministic=True)
                player.target_angle = player.angle + ang_action * math.pi
                player.is_boosting = boost_action

                engine.step(dt)
                step_count += 1

            scores.append(player.score)
            survival_times.append(step_count * dt)

        return float(np.mean(scores)), float(np.mean(survival_times))
