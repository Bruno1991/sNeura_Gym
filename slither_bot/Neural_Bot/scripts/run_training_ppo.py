"""Treina a rede neural por Aprendizado por Reforço (PPO) no SlitherEnv."""

import os
import sys
from pathlib import Path

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_ai.env.slither_env import SlitherEnv
from slither_ai.models.policy_net import SlitherPolicyNet
from slither_ai.training.ppo_trainer import PPOTrainer


def main():
    print("=============================================================")
    print("    Slither AI - Treinamento por Reforço (PPO Self-Play)")
    print("=============================================================")

    env = SlitherEnv()
    model = SlitherPolicyNet()

    # Se já existir o modelo pré-treinado por imitação, usa como Warm Start
    imitation_ckpt = "checkpoints/best_imitation_model.pt"
    if os.path.isfile(imitation_ckpt):
        print(f"[*] Carregando pesos pré-treinados por imitação (Warm Start): {imitation_ckpt}")
        model.load_model(imitation_ckpt)

    trainer = PPOTrainer(
        env=env,
        model=model,
        lr=3e-4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_epsilon=0.2,
    )

    ppo_path = "checkpoints/best_ppo_model.pt"
    trainer.train(total_iterations=10, steps_per_rollout=1024, save_path=ppo_path)

    print("=============================================================")
    print("    Treinamento PPO Concluído com Sucesso!")
    print("=============================================================\n")


if __name__ == "__main__":
    main()
