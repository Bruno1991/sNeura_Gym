"""Bateria Massiva de 50.000 Partidas com 64 Workers e AMP FP16.

Executa simulação paralela de 50.000 confrontos entre o Neural_Bot e todos os 217 bots oficiais
do Chess.com na GPU NVIDIA RTX 3060, com auto-treinamento contínuo, salvamento de checkpoints
e geração de relatório final de métricas.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch

# Configurar caminhos do projeto
ROOT_DIR = Path(__file__).resolve().parent
NEURAL_DIR = ROOT_DIR / "Neural_Bot"
SCRIPTED_DIR = ROOT_DIR / "Scripted_Bot"
CHECKPOINTS_DIR = NEURAL_DIR / "checkpoints"
REPORTS_DIR = ROOT_DIR / "relatorios_avancos"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(NEURAL_DIR))
sys.path.insert(0, str(SCRIPTED_DIR))

# Suporte a UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except Exception:
        pass

from chess_bot import ChessBot
from chess_ai.model import ChessPolicyValueNet
from chess_ai.batched_rl_trainer import BatchedRLTrainer
from chess_ai.report_generator import generate_tournament_markdown_report

WEIGHTS_PATH = CHECKPOINTS_DIR / "chess_policy_weights.pt"
ONNX_PATH = CHECKPOINTS_DIR / "chess_policy_weights.onnx"
BATTERY_HISTORY_PATH = CHECKPOINTS_DIR / "bateria_50k_history.json"
REPORT_MD_PATH = REPORTS_DIR / "relatorio_bateria_50000_partidas_64_workers.md"
BOTS_DATA_FILE = ROOT_DIR / "bots_data.json"
if not BOTS_DATA_FILE.is_file():
    BOTS_DATA_FILE = Path("C:/dev/s_ADB_Tools/bots_data.json")


def load_all_bots() -> list[ChessBot]:
    """Carrega todos os bots oficiais de bots_data.json cobrindo todo o espectro do Chess.com."""
    pool = []
    if BOTS_DATA_FILE.is_file():
        try:
            with open(BOTS_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for g in data.get("botGroups", []):
                for b in g.get("botPersonalities", []):
                    name = b.get("name")
                    rating = int(b.get("rating", 1500))
                    pool.append(ChessBot(rate=rating, bot_name=name))
            print(f"[*] Pool completo de oponentes carregado: {len(pool)} bots oficiais do Chess.com")
            return pool
        except Exception as e:
            print(f"[!] Erro ao carregar bots_data.json: {e}")

    # Fallback representativo cobrindo todos os tiers
    sample_ratings = [250, 400, 700, 1000, 1300, 1500, 1800, 2000, 2500, 2820, 3200]
    return [ChessBot(rate=r) for r in sample_ratings]


def main():
    parser = argparse.ArgumentParser(description="Bateria de 50.000 Partidas com Workers Paralelos")
    parser.add_argument("--games", type=int, default=50000, help="Total de partidas a simular (padrão: 50.000)")
    parser.add_argument("--workers", type=int, default=64, help="Número de workers paralelos simultâneos (padrão: 64)")
    parser.add_argument("--cycle-games", type=int, default=250, help="Partidas por ciclo de otimização (padrão: 250)")
    parser.add_argument("--max-plies", type=int, default=80, help="Máximo de plies por partida (padrão: 80)")
    parser.add_argument("--engine-workers", type=int, default=8, help="Processos para bots oponentes na CPU (padrão: 8)")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 80)
    print("      ♛ S_NEURA_GYM: BATERIA TURBO DE 50.000 PARTIDAS (GPU + CPU MULTIPROC) ♛")
    print("=" * 80)
    print(f" [*] Dispositivo Hardware : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    print(f" [*] Workers Paralelos    : {args.workers} instâncias simultâneas")
    print(f" [*] CPU Engine Workers   : {args.engine_workers} processos paralelos")
    print(f" [*] Meta de Partidas     : {args.games:,} partidas")
    print(f" [*] Limite de Plies      : {args.max_plies} plies ({args.max_plies//2} lances)")
    print(f" [*] Otimização AMP FP16  : ATIVA (NVIDIA Tensor Cores)")
    print("=" * 80)

    # 1. Carregar Rede Neural
    if WEIGHTS_PATH.is_file():
        print(f"[*] Carregando pesos pré-treinados: {WEIGHTS_PATH.name}")
        model = ChessPolicyValueNet.load_weights(WEIGHTS_PATH, device=str(device))
    else:
        print("[*] Inicializando nova arquitetura ResNet (128 canais x 4 blocos)")
        model = ChessPolicyValueNet(in_channels=18, num_channels=128, num_blocks=4).to(device)

    # 2. Carregar Pool de Bots
    bot_pool = load_all_bots()

    # 3. Inicializar BatchedRLTrainer
    trainer = BatchedRLTrainer(
        model=model,
        num_workers=args.workers,
        device=str(device),
        use_amp=True,
        bot_pool=bot_pool,
        max_plies=args.max_plies,
        engine_pool_workers=args.engine_workers,
    )

    start_time = time.time()

    # 4. Iniciar Bateria Paralela
    try:
        trainer.run_batched_training(
            total_games=args.games,
            games_per_cycle=args.cycle_games,
            epochs_per_cycle=2,
            batch_size=256,
            save_weights_path=WEIGHTS_PATH,
            save_onnx_path=ONNX_PATH,
            history_path=BATTERY_HISTORY_PATH,
        )
    except KeyboardInterrupt:
        print("\n[!] Bateria interrompida pelo operador. Salvando checkpoint e gerando relatório...")

    total_elapsed = time.time() - start_time
    total_played = trainer.env.total_completed_games

    # 5. Salvar Modelo Final e Exportar para ONNX
    try:
        model.save_weights(WEIGHTS_PATH)
        print(f"[+] Pesos finais salvos com sucesso em: {WEIGHTS_PATH}")
        model.export_onnx(ONNX_PATH)
        print(f"[+] Modelo ONNX exportado para: {ONNX_PATH}")
    except Exception as e:
        print(f"[!] Erro ao salvar pesos finais: {e}")

    # 6. Gerar Relatório Markdown
    try:
        if BATTERY_HISTORY_PATH.is_file():
            with open(BATTERY_HISTORY_PATH, "r", encoding="utf-8") as f:
                history_data = json.load(f)
            generate_tournament_markdown_report(history_data, REPORT_MD_PATH)
            print(f"[+] Relatório Markdown gerado com sucesso em: {REPORT_MD_PATH}")
    except Exception as e:
        print(f"[!] Erro ao gerar relatório markdown: {e}")

    print("=" * 80)
    print(f" [✔] BATERIA CONCLUÍDA: {total_played:,} partidas jogadas")
    print(f" [✔] Vitórias: {trainer.env.neural_wins} | Empates: {trainer.env.draws} | Derrotas: {trainer.env.engine_wins}")
    win_rate = (trainer.env.neural_wins / max(1, total_played)) * 100
    print(f" [✔] Taxa de Vitória Global: {win_rate:.2f}%")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
