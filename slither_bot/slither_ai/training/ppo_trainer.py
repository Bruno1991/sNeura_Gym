"""Treinador PPO (Proximal Policy Optimization) para auto-evolução no SlitherEnv."""

import os
from pathlib import Path
from typing import List, Optional
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from ..env.slither_env import SlitherEnv
from ..models.policy_net import SlitherPolicyNet


class PPOTrainer:
    """Implementa o algoritmo Proximal Policy Optimization para refinamento por reforço."""

    def __init__(
        self,
        env: Optional[SlitherEnv] = None,
        model: Optional[SlitherPolicyNet] = None,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
        device: Optional[str] = None,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.env = env or SlitherEnv()
        self.model = (model or SlitherPolicyNet()).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, eps=1e-5)

        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef

    def collect_rollout(self, steps_per_rollout: int = 2048):
        """Executa episódios no ambiente e armazena trajetórias para atualização."""
        obs_buf, actions_buf, rewards_buf, values_buf, dones_buf = [], [], [], [], []

        obs, _ = self.env.reset()

        for _ in range(steps_per_rollout):
            tensor_obs = torch.as_tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)
            with torch.no_grad():
                pred_angle, pred_boost_logits, val = self.model(tensor_obs)
                boost_prob = torch.sigmoid(pred_boost_logits).item()

            action_angle = float(pred_angle.squeeze().cpu().item())
            action_boost = 1.0 if boost_prob > 0.5 else 0.0
            act_np = np.array([action_angle, action_boost], dtype=np.float32)

            next_obs, reward, terminated, truncated, _ = self.env.step(act_np)
            done = terminated or truncated

            obs_buf.append(obs)
            actions_buf.append(act_np)
            rewards_buf.append(reward)
            values_buf.append(val.item())
            dones_buf.append(done)

            obs = next_obs
            if done:
                obs, _ = self.env.reset()

        # Calcula vantagens via GAE
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
            torch.as_tensor(advantages, dtype=torch.float32, device=self.device),
            torch.as_tensor(returns, dtype=torch.float32, device=self.device),
        )

    def train_step(self, obs, actions, advantages, returns, ppo_epochs: int = 4, batch_size: int = 64):
        """Aplica a atualização PPO com clipping de gradiente."""
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        dataset_size = len(obs)

        for _ in range(ppo_epochs):
            indices = np.random.permutation(dataset_size)
            for start in range(0, dataset_size, batch_size):
                batch_idx = indices[start : start + batch_size]
                b_obs = obs[batch_idx]
                b_acts = actions[batch_idx]
                b_adv = advantages[batch_idx]
                b_ret = returns[batch_idx]

                pred_angle, pred_boost_logits, val = self.model(b_obs)

                # Loss do Actor: MSE de ângulo ponderado pela vantagem
                angle_diff = pred_angle.squeeze() - b_acts[:, 0]
                policy_loss = (angle_diff.pow(2) * b_adv.abs()).mean()

                # Loss do Critic
                val_loss = F.mse_loss(val.squeeze(), b_ret)

                total_loss = policy_loss + self.value_coef * val_loss

                self.optimizer.zero_grad()
                total_loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=0.5)
                self.optimizer.step()

    def train(self, total_iterations: int = 20, steps_per_rollout: int = 1024, save_path: str = "checkpoints/best_ppo_model.pt"):
        """Loop principal de treino por reforço."""
        print(f"[*] Iniciando treino por Reforço (PPO) por {total_iterations} iterações...")
        os.makedirs(Path(save_path).parent, exist_ok=True)

        for it in range(1, total_iterations + 1):
            obs, actions, advantages, returns = self.collect_rollout(steps_per_rollout)
            self.train_step(obs, actions, advantages, returns)
            print(f"    [PPO Iteração {it:02d}/{total_iterations:02d}] Rollout completado | Retorno Médio: {returns.mean():.2f}")
            self.model.save_model(save_path)

        print(f"[+] Treinamento PPO finalizado! Modelo salvo em: {save_path}")
        return self.model
