"""Treinador PPO (Proximal Policy Optimization) com ancoragem anti-esquecimento.

Permite auto-evolução por reforço preservando 100% da base inteligente destilada do APK.
"""

import copy
import os
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..env.slither_env import SlitherEnv
from ..models.policy_net import SlitherPolicyNet


class PPOTrainer:
    """Implementa o algoritmo PPO com ancoragem para evitar esquecimento catastrófico."""

    def __init__(
        self,
        env: Optional[SlitherEnv] = None,
        model: Optional[SlitherPolicyNet] = None,
        lr: float = 1e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        value_coef: float = 0.5,
        anchor_coef: float = 0.2,
        exploration_std: float = 0.12,
        device: Optional[str] = None,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.env = env or SlitherEnv()
        self.model = (model or SlitherPolicyNet()).to(self.device)

        # Cópia de referência congelada para ancorar a política pré-treinada
        self.ref_model = copy.deepcopy(self.model).to(self.device)
        self.ref_model.eval()
        for p in self.ref_model.parameters():
            p.requires_grad = False

        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, eps=1e-5)

        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.value_coef = value_coef
        self.anchor_coef = anchor_coef
        self.exploration_std = exploration_std

    def _get_log_prob(self, mean_angle: torch.Tensor, logits_boost: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        """Calcula a log-probabilidade conjunta da ação contínua (ângulo) e discreta (turbo)."""
        act_angle = actions[:, 0]
        act_boost = actions[:, 1]

        # 1. Log-probabilidade normal para o ângulo
        std = torch.full_like(mean_angle.squeeze(), self.exploration_std)
        var = std.pow(2)
        log_prob_angle = -0.5 * (((act_angle - mean_angle.squeeze()).pow(2)) / var + 2.0 * torch.log(std) + 1.837877)

        # 2. Log-probabilidade Bernoulli para o turbo
        prob_boost = torch.sigmoid(logits_boost.squeeze()).clamp(1e-6, 1.0 - 1e-6)
        log_prob_boost = act_boost * torch.log(prob_boost) + (1.0 - act_boost) * torch.log(1.0 - prob_boost)

        return log_prob_angle + 0.5 * log_prob_boost

    def collect_rollout(self, steps_per_rollout: int = 2048) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Executa episódios no ambiente e armazena trajetórias com log-probs."""
        obs_buf, actions_buf, log_probs_buf, rewards_buf, values_buf, dones_buf = [], [], [], [], [], []

        obs, _ = self.env.reset()

        for _ in range(steps_per_rollout):
            tensor_obs = torch.as_tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)
            with torch.no_grad():
                pred_angle, pred_boost_logits, val = self.model(tensor_obs)
                mean_ang = pred_angle.squeeze().item()
                boost_prob = torch.sigmoid(pred_boost_logits).item()

            # Amostragem estocástica com ruído de exploração controlado
            sampled_angle = float(np.clip(np.random.normal(mean_ang, self.exploration_std), -1.0, 1.0))
            sampled_boost = 1.0 if np.random.random() < boost_prob else 0.0
            act_np = np.array([sampled_angle, sampled_boost], dtype=np.float32)

            # Log-probabilidade no momento da amostragem
            act_tensor = torch.as_tensor(act_np, dtype=torch.float32, device=self.device).unsqueeze(0)
            with torch.no_grad():
                old_log_prob = self._get_log_prob(pred_angle, pred_boost_logits, act_tensor).item()

            next_obs, reward, terminated, truncated, _ = self.env.step(act_np)
            done = terminated or truncated

            obs_buf.append(obs)
            actions_buf.append(act_np)
            log_probs_buf.append(old_log_prob)
            rewards_buf.append(reward)
            values_buf.append(val.item())
            dones_buf.append(done)

            obs = next_obs
            if done:
                obs, _ = self.env.reset()

        # Cálculo de Vantagens Generalizadas (GAE)
        advantages = np.zeros(len(rewards_buf), dtype=np.float32)
        last_gae = 0.0
        for t in reversed(range(len(rewards_buf))):
            next_val = values_buf[t + 1] if t < len(rewards_buf) - 1 and not dones_buf[t] else 0.0
            delta = rewards_buf[t] + self.gamma * next_val - values_buf[t]
            last_gae = delta + self.gamma * self.gae_lambda * (1.0 - float(dones_buf[t])) * last_gae
            advantages[t] = last_gae

        returns = advantages + np.array(values_buf, dtype=np.float32)

        return (
            torch.as_tensor(np.array(obs_buf), dtype=torch.float32, device=self.device),
            torch.as_tensor(np.array(actions_buf), dtype=torch.float32, device=self.device),
            torch.as_tensor(np.array(log_probs_buf), dtype=torch.float32, device=self.device),
            torch.as_tensor(advantages, dtype=torch.float32, device=self.device),
            torch.as_tensor(returns, dtype=torch.float32, device=self.device),
        )

    def train_step(self, obs, actions, old_log_probs, advantages, returns, ppo_epochs: int = 4, batch_size: int = 64):
        """Aplica atualização PPO com clipping de ratio e ancoragem na política de referência."""
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        dataset_size = len(obs)

        for _ in range(ppo_epochs):
            indices = np.random.permutation(dataset_size)
            for start in range(0, dataset_size, batch_size):
                batch_idx = indices[start : start + batch_size]
                b_obs = obs[batch_idx]
                b_acts = actions[batch_idx]
                b_old_log_p = old_log_probs[batch_idx]
                b_adv = advantages[batch_idx]
                b_ret = returns[batch_idx]

                pred_angle, pred_boost_logits, val = self.model(b_obs)
                curr_log_p = self._get_log_prob(pred_angle, pred_boost_logits, b_acts)

                # 1. Ratio PPO e Surrogate Loss com Clipping
                ratio = torch.exp(curr_log_p - b_old_log_p)
                surr1 = ratio * b_adv
                surr2 = torch.clamp(ratio, 1.0 - self.clip_epsilon, 1.0 + self.clip_epsilon) * b_adv
                policy_loss = -torch.min(surr1, surr2).mean()

                # 2. Loss do Critic (Ajuste de Valor)
                val_loss = F.mse_loss(val.squeeze(), b_ret)

                # 3. Ancoragem de Estabilidade: penaliza desvios drásticos da base do APK
                with torch.no_grad():
                    ref_angle, ref_boost_logits, _ = self.ref_model(b_obs)
                anchor_loss = F.mse_loss(pred_angle, ref_angle) + 0.3 * F.mse_loss(pred_boost_logits, ref_boost_logits)

                total_loss = policy_loss + self.value_coef * val_loss + self.anchor_coef * anchor_loss

                self.optimizer.zero_grad()
                total_loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
                self.optimizer.step()

    def train(self, total_iterations: int = 15, steps_per_rollout: int = 1024, save_path: str = "checkpoints/best_ppo_model.pt"):
        """Loop principal de treino por reforço estável."""
        print(f"[*] Iniciando treino por Reforço (PPO Estável com Ancoragem) por {total_iterations} iterações...")
        os.makedirs(Path(save_path).parent, exist_ok=True)

        for it in range(1, total_iterations + 1):
            obs, actions, old_log_probs, advantages, returns = self.collect_rollout(steps_per_rollout)
            self.train_step(obs, actions, old_log_probs, advantages, returns)
            print(f"    [PPO Iteração {it:02d}/{total_iterations:02d}] Rollout completado | Retorno Médio: {returns.mean():.2f}")
            self.model.save_model(save_path)

        print(f"[+] Treinamento PPO finalizado! Modelo salvo em: {save_path}")
        return self.model
