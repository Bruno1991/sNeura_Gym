"""Script de Treinamento Paralelo em Lote com 64 Workers e AMP FP16.

Executa partidas simultâneas aceleradas na GPU NVIDIA RTX 3060,
com vetorização de inferência e treinamento em precisão mista automática (FP16).
"""

import argparse
import sys
import time
from pathlib import Path

import torch

# Adicionar caminhos ao sys.path
current_dir = Path(__file__).resolve().parent.parent
scripted_bot_dir = current_dir.parent / "Scripted_Bot"

sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(scripted_bot_dir))

from chess_ai.batched_rl_trainer import BatchedRLTrainer
from chess_ai.model import ChessPolicyValueNet
from bot_3200 import ChessBot3200

# Forçar suporte UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Treinamento Paralelo BatchedRLTrainer (64 Workers + AMP FP16)")
    parser.add_argument("--workers", type=int, default=64, help="Número de partidas simultâneas (padrão: 64)")
    parser.add_argument("--games", type=int, default=1000, help="Total de partidas a disputar (padrão: 1000)")
    parser.add_argument("--cycle-games", type=int, default=100, help="Partidas por ciclo de aprendizado (padrão: 100)")
    parser.add_argument("--epochs", type=int, default=3, help="Épocas de treino na GPU por ciclo (padrão: 3)")
    parser.add_argument("--batch-size", type=int, default=512, help="Tamanho do batch de treino na GPU (padrão: 512)")
    parser.add_argument("--lr", type=float, default=4e-4, help="Taxa de aprendizado AdamW (padrão: 0.0004)")
    parser.add_argument("--device", type=str, default=None, help="Dispositivo ('cuda' ou 'cpu')")
    parser.add_argument("--no-amp", action="store_true", help="Desativa AMP FP16")

    args = parser.parse_args()

    checkpoints_dir = current_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    weights_path = checkpoints_dir / "chess_policy_weights.pt"
    onnx_path = checkpoints_dir / "chess_policy_weights.onnx"
    history_path = checkpoints_dir / "batched_rl_history.json"

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Dispositivo Selecionado : {device.upper()}")

    # 1. Carregar modelo existente
    if weights_path.is_file():
        print(f"[*] Carregando pesos da rede neural de: {weights_path.name}")
        model = ChessPolicyValueNet.load_weights(weights_path, device=device)
    else:
        print("[*] Criando nova arquitetura ChessPolicyValueNet...")
        model = ChessPolicyValueNet(num_channels=128, num_blocks=4).to(device)

    # 2. Inicializar bot especialista (3200 Elo)
    bot_3200 = ChessBot3200()

    # 3. Inicializar treinador paralelo
    trainer = BatchedRLTrainer(
        model=model,
        bot_3200=bot_3200,
        num_workers=args.workers,
        device=device,
        lr=args.lr,
        checkpoints_dir=checkpoints_dir,
        use_amp=not args.no_amp,
    )

    # 4. Executar treinamento paralelo
    trainer.run_batched_training(
        total_games=args.games,
        games_per_cycle=args.cycle_games,
        epochs_per_cycle=args.epochs,
        batch_size=args.batch_size,
        save_weights_path=weights_path,
        save_onnx_path=onnx_path,
        history_path=history_path,
    )


if __name__ == "__main__":
    main()
