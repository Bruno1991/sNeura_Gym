"""Script Autônomo de Treinamento por Reforço: 1000 Partidas contra Maximum 3200.

Executa o loop completo de 1000 partidas, coletando dados de jogo, aplicando
iteração de especialista (DAgger) e atualizando os pesos da rede na GPU (RTX 3060).
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

from chess_ai.model import ChessPolicyValueNet
from chess_ai.rl_trainer import RLChessTrainer
from bot_3200 import ChessBot3200

# Forçar suporte UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Treinamento de 1000 Partidas Neural vs 3200 Elo")
    parser.add_argument("--games", type=int, default=1000, help="Total de partidas a disputar (padrão: 1000)")
    parser.add_argument("--cycle-games", type=int, default=50, help="Partidas por ciclo de treino na GPU (padrão: 50)")
    parser.add_argument("--epochs", type=int, default=3, help="Épocas na GPU por ciclo (padrão: 3)")
    parser.add_argument("--batch-size", type=int, default=256, help="Tamanho do lote na GPU (padrão: 256)")
    parser.add_argument("--lr", type=float, default=5e-4, help="Taxa de aprendizado AdamW (padrão: 0.0005)")
    parser.add_argument("--device", type=str, default=None, help="Dispositivo ('cuda' ou 'cpu')")

    args = parser.parse_args()

    checkpoints_dir = current_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    weights_path = checkpoints_dir / "chess_policy_weights.pt"
    onnx_path = checkpoints_dir / "chess_policy_weights.onnx"
    history_path = checkpoints_dir / "rl_training_1000_history.json"

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Inicializando ambiente no dispositivo: {device.upper()}")

    # 1. Carregar modelo existente pré-treinado
    if weights_path.is_file():
        print(f"[*] Carregando pesos pré-treinados de: {weights_path.name}")
        model = ChessPolicyValueNet.load_weights(weights_path, device=device)
    else:
        print("[*] Criando nova arquitetura ChessPolicyValueNet...")
        model = ChessPolicyValueNet(num_channels=128, num_blocks=4).to(device)

    # 2. Inicializar oponente (Bot de 3200 Elo)
    bot_3200 = ChessBot3200()

    # 3. Inicializar treinador de reforço
    trainer = RLChessTrainer(
        model=model,
        bot_3200=bot_3200,
        device=device,
        lr=args.lr,
        checkpoints_dir=checkpoints_dir,
    )

    # 4. Executar o ciclo de 1000 partidas
    trainer.run_1000_games_training(
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
