"""Módulos de treinamento (Imitation Learning, DAgger Distillation e PPO)."""

from .dataset import ExpertDataset
from .dagger_trainer import DAggerTrainer
from .imitation_trainer import ImitationTrainer
from .ppo_trainer import PPOTrainer

__all__ = ["ExpertDataset", "DAggerTrainer", "ImitationTrainer", "PPOTrainer"]
