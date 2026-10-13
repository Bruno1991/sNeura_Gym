"""Script CLI para Iniciar o Treinamento Contínuo 24/7 até a Maestria Neural."""

import argparse
import sys
from pathlib import Path

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_ai.training.mastery_trainer import MasteryCurriculumEngine


def main():
    parser = argparse.ArgumentParser(
        description="Executa Treinamento Contínuo 24/7 do Slither Bot até Maestria Neural Completa."
    )
    parser.add_argument(
        "--target-mastery",
        type=float,
        default=95.0,
        help="Meta percentual do Índice de Maestria para conclusão (padrão: 95.0%)",
    )
    parser.add_argument(
        "--eval-interval",
        type=int,
        default=5,
        help="Intervalo de ciclos entre cada bateria de benchmark e atualização de telemetria (padrão: 5)",
    )
    parser.add_argument(
        "--max-hours",
        type=float,
        default=None,
        help="Limite opcional de tempo em horas (padrão: None = roda continuamente 24/7)",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=1e-4,
        help="Taxa de aprendizado AdamW para refinamento PPO (padrão: 1e-4)",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default="checkpoints",
        help="Diretório de salvamento dos modelos (padrão: checkpoints)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Dispositivo de treino ('cuda' ou 'cpu', padrão: detecção automática)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Quantidade de processos paralelos na CPU (padrão: 8 workers)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=4096,
        help="Passos de simulação coletados por ciclo (padrão: 4096)",
    )

    args = parser.parse_args()

    engine = MasteryCurriculumEngine(
        target_mastery=args.target_mastery,
        eval_interval=args.eval_interval,
        save_dir=args.save_dir,
        device=args.device,
        learning_rate=args.lr,
        num_workers=args.workers,
        rollout_steps=args.steps,
    )

    engine.run_continuous_training(max_hours=args.max_hours)


if __name__ == "__main__":
    main()
