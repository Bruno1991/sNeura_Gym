"""Script de inicialização do Treinamento por Destilação Ativa DAgger."""

import argparse
import sys
from pathlib import Path

# Adiciona a raiz do projeto ao sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_ai.training.dagger_trainer import DAggerTrainer


def main():
    parser = argparse.ArgumentParser(
        description="Treina a rede neural via DAgger (destilação ativa da IA do Slither APK)."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Número total de ciclos DAgger (padrão: 5)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=15000,
        help="Número de passos simulados coletados por ciclo (padrão: 15.000)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=6,
        help="Épocas de treino na GPU por ciclo DAgger (padrão: 6)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Tamanho do lote de processamento na GPU (padrão: 256)",
    )

    args = parser.parse_args()

    trainer = DAggerTrainer(batch_size=args.batch_size)
    trainer.train_dagger(
        total_iterations=args.iterations,
        steps_per_iteration=args.steps,
        epochs_per_iteration=args.epochs,
    )


if __name__ == "__main__":
    main()
