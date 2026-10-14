"""Script de Treinamento da Destilação de Aberturas (balanced.bin -> Pesos Neurais).

Converte as 80.601 posições de abertura do bot oficial de 3200 Elo em
pesos de rede neural (checkpoints/chess_policy_weights.pt e .onnx).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch

# Adicionar raiz do pacote ao PYTHONPATH
current_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(current_dir))

from chess_ai.dataset import ChessOpeningDataset
from chess_ai.model import ChessPolicyValueNet
from chess_ai.trainer import PolicyDistillationTrainer

# Forçar suporte UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Treinamento de Destilação Polyglot -> Pesos Neurais")
    parser.add_argument("--epochs", type=int, default=8, help="Número de épocas de treinamento (padrão: 8)")
    parser.add_argument("--batch-size", type=int, default=256, help="Tamanho do lote de dados (padrão: 256)")
    parser.add_argument("--lr", type=float, default=1e-3, help="Taxa de aprendizado inicial (padrão: 0.001)")
    parser.add_argument("--max-positions", type=int, default=None, help="Limite opcional de posições para teste rápido")
    parser.add_argument("--rebuild-dataset", action="store_true", help="Força re-extração do arquivo balanced.bin")
    parser.add_argument("--device", type=str, default=None, help="Dispositivo de execução ('cuda' ou 'cpu')")

    args = parser.parse_args()

    # Caminhos oficiais
    workspace_root = current_dir.parent
    book_path = workspace_root / "Scripted_Bot" / "assets" / "balanced.bin"
    checkpoints_dir = current_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    cache_path = checkpoints_dir / "polyglot_dataset.pt"
    weights_path = checkpoints_dir / "chess_policy_weights.pt"
    onnx_path = checkpoints_dir / "chess_policy_weights.onnx"
    history_path = checkpoints_dir / "training_history.json"

    if not book_path.is_file():
        print(f"[!] Erro: Arquivo {book_path} não encontrado.")
        sys.exit(1)

    print("=" * 70)
    print("  DESTILAÇÃO NEURAL DO LIVRO DE ABERTURAS (BALANCED.BIN -> PESOS)")
    print("=" * 70)
    print(f"[*] Livro Polyglot Fonte : {book_path}")
    print(f"[*] Arquivo de Pesos Alvo: {weights_path}")
    print(f"[*] Dispositivo          : {args.device or ('CUDA (GPU)' if torch.cuda.is_available() else 'CPU')}")
    print("-" * 70)

    # 1. Carregar ou extrair dataset
    t0 = time.time()
    dataset = ChessOpeningDataset.load_or_extract(
        book_path=book_path,
        cache_path=cache_path,
        max_positions=args.max_positions,
        force_rebuild=args.rebuild_dataset,
    )
    print(f"[+] Dataset pronto com {len(dataset)} posições em {time.time() - t0:.2f}s\n")

    # 2. Inicializar Rede Neural ResNet
    model = ChessPolicyValueNet(num_channels=128, num_blocks=4)
    param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[*] Modelo ChessPolicyValueNet inicializado ({param_count:,} parâmetros treináveis)")

    # 3. Treinar
    trainer = PolicyDistillationTrainer(
        model=model,
        dataset=dataset,
        device=args.device,
        batch_size=args.batch_size,
        lr=args.lr,
    )

    t_train = time.time()
    results = trainer.train(
        num_epochs=args.epochs,
        save_path=weights_path,
        onnx_path=onnx_path,
    )
    train_duration = time.time() - t_train

    # 4. Salvar histórico de métricas
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "train_duration_seconds": train_duration,
                "best_val_in_book_acc": results["best_val_in_book_acc"],
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "param_count": param_count,
                "history": results["history"],
            },
            f,
            indent=2,
        )

    print("\n" + "=" * 70)
    print("  TREINAMENTO CONCLUÍDO COM SUCESSO!")
    print("=" * 70)
    print(f"[+] Duração total do treino: {train_duration:.1f}s ({train_duration / 60:.2f} min)")
    print(f"[+] Melhor Acurácia In-Book na Validação: {results['best_val_in_book_acc']:.2f}%")
    print(f"[+] Pesos salvos em: {weights_path}")
    print(f"[+] Modelo ONNX em:  {onnx_path}")
    print(f"[+] Histórico salvo: {history_path}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
