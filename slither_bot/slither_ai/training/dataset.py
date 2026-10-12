"""Geração e gerenciamento de datasets de demonstração da IA especialista (Behavior Cloning)."""

import math
from typing import List, Tuple
import torch
from torch.utils.data import Dataset
import numpy as np

from ..config import SlitherConfig
from ..core.engine import SlitherEngine
from ..core.expert_bot import SlitherNativeBot
from ..env.sensors import SlitherSensors
from ..utils.math_helpers import shortest_angular_difference


class ExpertDataset(Dataset):
    """Dataset de observações e ações gravadas a partir do bot nativo do Slither.io."""

    def __init__(self, observations: np.ndarray, target_angles: np.ndarray, target_boosts: np.ndarray):
        self.observations = torch.as_tensor(observations, dtype=torch.float32)
        self.target_angles = torch.as_tensor(target_angles, dtype=torch.float32).unsqueeze(1)
        self.target_boosts = torch.as_tensor(target_boosts, dtype=torch.float32).unsqueeze(1)

    def __len__(self) -> int:
        return len(self.observations)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.observations[idx], self.target_angles[idx], self.target_boosts[idx]

    @classmethod
    def collect_from_simulation(cls, num_samples: int = 15000, dt: float = 0.033) -> "ExpertDataset":
        """Executa a engine com o bot especialista e grava demonstrações da IA."""
        engine = SlitherEngine(
            arena_radius=SlitherConfig.ARENA_RADIUS_TRAIN,
            num_bots=SlitherConfig.NUM_BOTS_TRAIN,
            num_foods=SlitherConfig.NUM_FOOD_TRAIN,
        )

        obs_list = []
        angle_list = []
        boost_list = []

        # Acompanha o primeiro bot como fonte principal de gravação
        tracked_bot_id = engine.snakes[0].id if engine.snakes else 1

        print(f"[*] Coletando {num_samples} passos de demonstração da IA nativa...")
        collected = 0

        while collected < num_samples:
            engine.step(dt)

            for snake in engine.snakes:
                if not snake.is_alive or not snake.is_bot:
                    continue

                # Extrai a percepção sensorial antes do bot tomar ação
                obs = SlitherSensors.get_observation(
                    snake=snake,
                    all_snakes=engine.snakes,
                    foods=engine.foods,
                    arena_radius=engine.arena_radius,
                )

                # Ação que o bot especialista determinou
                diff = shortest_angular_difference(snake.target_angle, snake.angle)
                norm_angle = float(np.clip(diff / math.pi, -1.0, 1.0))
                norm_boost = 1.0 if snake.is_boosting else 0.0

                obs_list.append(obs)
                angle_list.append(norm_angle)
                boost_list.append(norm_boost)
                collected += 1

                if collected >= num_samples:
                    break

        print(f"[+] Coleta concluída com sucesso! Total de amostras: {len(obs_list)}")
        return cls(
            observations=np.array(obs_list, dtype=np.float32),
            target_angles=np.array(angle_list, dtype=np.float32),
            target_boosts=np.array(boost_list, dtype=np.float32),
        )
