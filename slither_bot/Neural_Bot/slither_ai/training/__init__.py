"""Módulos de treinamento (Imitation Learning, DAgger Distillation, PPO e Maestria 24/7)."""

from .dataset import ExpertDataset
from .dagger_trainer import DAggerTrainer
from .imitation_trainer import ImitationTrainer
from .ppo_trainer import PPOTrainer
from .mastery_trainer import MasteryCurriculumEngine

__all__ = ["ExpertDataset", "DAggerTrainer", "ImitationTrainer", "PPOTrainer", "MasteryCurriculumEngine"]
