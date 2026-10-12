"""Arquitetura de Rede Neural Actor-Critic em PyTorch para Slither.io."""

from typing import Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..env.sensors import SlitherSensors


class SlitherPolicyNet(nn.Module):
    """Rede Neural Actor-Critic para predição de direção e ativação de turbo."""

    def __init__(self, input_dim: int = SlitherSensors.OBSERVATION_DIM, hidden_dim: int = 128):
        super().__init__()
        self.input_dim = input_dim

        # 1. Extrator Compartilhado de Features
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )

        # 2. Cabeça do Actor (Políticas de Ação)
        # Saída de ângulo: delta angular relativo [-1.0, 1.0] mapeado para [-pi, pi]
        self.actor_angle = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Tanh(),
        )

        # Saída de boost: probabilidade de ativação do turbo [0.0, 1.0]
        self.actor_boost = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

        # 3. Cabeça do Critic (Estimativa de Valor / V-Value)
        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Forward pass.
        
        Retorna:
          angle: tensor [-1.0, 1.0]
          boost_logits: tensor (logits não normalizados para BCE)
          value: tensor estimativa de recompensa acumulada
        """
        features = self.feature_extractor(x)
        angle = self.actor_angle(features)
        boost_logits = self.actor_boost(features)
        value = self.critic(features)
        return angle, boost_logits, value

    @torch.no_grad()
    def get_action(self, obs_np, deterministic: bool = True) -> Tuple[float, bool]:
        """Método de inferência rápida para uso em simulação ou servidor online."""
        self.eval()
        device = next(self.parameters()).device
        tensor_obs = torch.as_tensor(obs_np, dtype=torch.float32, device=device)
        if tensor_obs.ndim == 1:
            tensor_obs = tensor_obs.unsqueeze(0)

        angle, boost_logits, _ = self.forward(tensor_obs)
        boost_prob = torch.sigmoid(boost_logits).item()

        angle_val = float(angle.squeeze().cpu().item())
        if deterministic:
            boost_val = boost_prob > 0.5
        else:
            boost_val = torch.bernoulli(torch.tensor(boost_prob)).item() > 0.5

        return angle_val, boost_val

    def save_model(self, path: str):
        """Salva os pesos do modelo em disco."""
        torch.save(self.state_dict(), path)

    def load_model(self, path: str, map_location=None):
        """Carrega os pesos do modelo a partir do arquivo."""
        state = torch.load(path, map_location=map_location, weights_only=True)
        self.load_state_dict(state)
