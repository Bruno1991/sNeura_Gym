"""Módulos de treinamento (Imitation Learning e PPO)."""

from .dataset import ExpertDataset
from .imitation_trainer import ImitationTrainer
from .ppo_trainer import PPOTrainer

__all__ = ["ExpertDataset", "ImitationTrainer", "PPOTrainer"]
