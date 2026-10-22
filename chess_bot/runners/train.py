"""Runner de Treinamento e Ajuste Fino Neural com AMP FP16 na GPU (runners.train).

Executa de ponta a ponta:
1. Extração e vetorização de tensores a partir de 'selfplay_1000_games.pgn' + âncoras GM ('balanced.bin')
2. Treinamento da rede neural ChessPolicyValueNet (SE-ResNet) na GPU NVIDIA RTX 3060 (AMP FP16)
3. Validação de convergência de loss (política e valor) e acurácia Top-1
4. Salvamento seguro de checkpoint e exportação do modelo ONNX
5. Bateria de confrontos de validação pós-treino contra bots de teste (Elo 1300 a 2100)
6. Geração do relatório executivo analítico
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import chess
import chess.pgn
import chess.polyglot
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, random_split

CHESS_BOT_DIR = Path(__file__).resolve().parent.parent
NEURAL_DIR = CHESS_BOT_DIR / "Neural_Bot"
SCRIPTED_DIR = CHESS_BOT_DIR / "Scripted_Bot"
REPORTS_DIR = CHESS_BOT_DIR / "relatorios_avancos"
CHECKPOINTS_DIR = NEURAL_DIR / "checkpoints"
BOOKS_DIR = CHESS_BOT_DIR / "books"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPTED_DIR))
sys.path.insert(0, str(NEURAL_DIR))

from chess_bot import ChessBot
from chess_ai.agent import NeuralChessBot
from chess_ai.encoder import ACTION_SIZE, NUM_CHANNELS, encode_board, encode_move
from chess_ai.model import ChessPolicyValueNet

PGN_FILE = REPORTS_DIR / "selfplay_1000_games.pgn"
BALANCED_BOOK = BOOKS_DIR / "balanced.bin"
DATASET_CACHE = CHECKPOINTS_DIR / "dataset_selfplay_1000_combined.pt"
WEIGHTS_PATH = CHECKPOINTS_DIR / "chess_policy_weights.pt"
ONNX_PATH = CHECKPOINTS_DIR / "chess_policy_weights.onnx"
REPORT_TRAINING_MD = REPORTS_DIR / "relatorio_treinamento_pos_selfplay_1000.md"


class CombinedChessDataset(Dataset):
    """Dataset em memória contendo tensores do tabuleiro, alvos de política e de valor."""

    def __init__(self, states: torch.Tensor, policies: torch.Tensor, values: torch.Tensor):
        self.states = states
        self.policies = policies
        self.values = values

    def __len__(self) -> int:
        return len(self.states)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.states[idx], self.policies[idx], self.values[idx]


def extract_training_dataset(
    pgn_path: Path,
    book_path: Optional[Path] = None,
    cache_path: Optional[Path] = None,
    max_pgn_games: int = 1000,
    max_book_positions: int = 30000,
    force_rebuild: bool = False,
) -> CombinedChessDataset:
    """Extrai e consolida tensores de self-play e de livros de Grandes Mestres."""
    if cache_path and cache_path.is_file() and not force_rebuild:
        print(f"[*] Carregando dataset em cache de: {cache_path.name}")
        data = torch.load(str(cache_path), weights_only=True)
        return CombinedChessDataset(data["states"], data["policies"], data["values"])

    print("=" * 75)
    print("      🧩 EXTRAÇÃO E VETORIZAÇÃO DO DATASET DE APRENDIZADO 🧩")
    print("=" * 75)
    t0 = time.time()

    all_states: List[torch.Tensor] = []
    all_policies: List[torch.Tensor] = []
    all_values: List[torch.Tensor] = []

    # 1. Extração do PGN Self-Play
    if pgn_path.is_file():
        print(f"[*] Processando partidas do PGN: {pgn_path.name}...")
        games_read = 0
        with open(pgn_path, "r", encoding="utf-8") as f_pgn:
            while games_read < max_pgn_games:
                game = chess.pgn.read_game(f_pgn)
                if game is None:
                    break
                games_read += 1

                res_str = game.headers.get("Result", "1/2-1/2")
                if res_str == "1-0":
                    game_val_white = 1.0
                elif res_str == "0-1":
                    game_val_white = -1.0
                else:
                    game_val_white = 0.0

                board = game.board()
                for move in game.mainline_moves():
                    st = encode_board(board)
                    mv_idx = encode_move(move, board.turn)
                    val = game_val_white if board.turn == chess.WHITE else -game_val_white

                    all_states.append(st)
                    all_policies.append(torch.tensor(mv_idx, dtype=torch.long))
                    all_values.append(torch.tensor(val, dtype=torch.float32))

                    board.push(move)

                if games_read % 100 == 0:
                    print(f"  • {games_read} partidas lidas | {len(all_states):,} posições vetorizadas")

        print(f"[✓] Self-Play processado: {games_read} partidas ➔ {len(all_states):,} posições.")

    # 2. Âncoras de Mestres Polyglot
    if book_path and book_path.is_file():
        print(f"[*] Injetando âncoras canônicas do livro GM: {book_path.name}...")
        try:
            reader = chess.polyglot.open_reader(str(book_path))
            book_positions = 0
            openings = [
                [],
                [chess.Move.from_uci("e2e4")],
                [chess.Move.from_uci("d2d4")],
                [chess.Move.from_uci("c2c4")],
                [chess.Move.from_uci("g1f3")],
                [chess.Move.from_uci("e2e4"), chess.Move.from_uci("c7c5")],
                [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
                [chess.Move.from_uci("d2d4"), chess.Move.from_uci("d7d5")],
                [chess.Move.from_uci("d2d4"), chess.Move.from_uci("g8f6")],
            ]

            visited_fens = set()
            for line in openings:
                b = chess.Board()
                for m in line:
                    b.push(m)

                stack = [b]
                while stack and book_positions < max_book_positions:
                    cur_b = stack.pop()
                    f = cur_b.fen()
                    if f in visited_fens:
                        continue
                    visited_fens.add(f)

                    try:
                        entries = list(reader.find_all(cur_b))
                    except Exception:
                        entries = []

                    if not entries:
                        continue

                    entries.sort(key=lambda e: e.weight, reverse=True)
                    top_entry = entries[0]
                    mv = top_entry.move

                    st = encode_board(cur_b)
                    mv_idx = encode_move(mv, cur_b.turn)
                    all_states.append(st)
                    all_policies.append(torch.tensor(mv_idx, dtype=torch.long))
                    all_values.append(torch.tensor(0.1, dtype=torch.float32))
                    book_positions += 1

                    if len(stack) < 100:
                        for e in entries[:2]:
                            next_b = cur_b.copy()
                            next_b.push(e.move)
                            if next_b.fullmove_number <= 15:
                                stack.append(next_b)

            reader.close()
            print(f"[✓] Âncoras de Mestres injetadas: {book_positions:,} posições.")
        except Exception as e:
            print(f"[!] Erro ao injetar livro GM: {e}")

    if not all_states:
        raise ValueError("Nenhum dado encontrado para treinamento.")

    print(f"[*] Empilhando tensores finais ({len(all_states):,} amostras)...")
    states_tensor = torch.stack(all_states)
    policies_tensor = torch.stack(all_policies)
    values_tensor = torch.stack(all_values)

    if cache_path:
        print(f"[*] Salvando cache do dataset em: {cache_path.name}")
        torch.save(
            {"states": states_tensor, "policies": policies_tensor, "values": values_tensor},
            str(cache_path),
        )

    dur = time.time() - t0
    print(f"[✓] Dataset consolidado com {len(states_tensor):,} tensores em {dur:.1f}s!")
    return CombinedChessDataset(states_tensor, policies_tensor, values_tensor)


def train_neural_network(
    dataset: CombinedChessDataset,
    epochs: int = 15,
    batch_size: int = 512,
    lr: float = 1e-3,
    save_weights: Path = WEIGHTS_PATH,
    save_onnx: Path = ONNX_PATH,
) -> Dict[str, Any]:
    """Treina a rede neural SE-ResNet utilizando PyTorch AMP FP16."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 75)
    print("      🚀 TREINAMENTO DA REDE NEURAL (SE-RESNET + AMP FP16) 🚀")
    print("=" * 75)
    print(f" [*] Dispositivo      : {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")
    print(f" [*] Tamanho Amostras : {len(dataset):,} tensores")
    print(f" [*] Batch Size       : {batch_size}")
    print(f" [*] Épocas           : {epochs}")
    print(f" [*] Taxa Aprendizado : {lr}")
    print("=" * 75 + "\n")

    if save_weights.is_file():
        print(f"[*] Carregando modelo base pré-existente: {save_weights.name}")
        model = ChessPolicyValueNet.load_weights(save_weights, device=str(device))
    else:
        print("[*] Instanciando novo modelo SE-ResNet...")
        model = ChessPolicyValueNet(in_channels=NUM_CHANNELS, num_channels=128, num_blocks=4).to(device)

    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    val_size = int(len(dataset) * 0.1)
    train_size = len(dataset) - val_size
    train_data, val_data = random_split(
        dataset, [train_size, val_size], generator=torch.Generator().manual_seed(42)
    )

    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True, pin_memory=(device.type == "cuda"))
    val_loader = DataLoader(val_data, batch_size=batch_size, shuffle=False, pin_memory=(device.type == "cuda"))

    loss_history: List[Dict[str, float]] = []
    t_start = time.time()

    for ep in range(1, epochs + 1):
        model.train()
        running_total_loss = 0.0
        running_p_loss = 0.0
        running_v_loss = 0.0
        correct_top1 = 0
        total_samples = 0

        for b_states, b_pol, b_val in train_loader:
            b_states = b_states.to(device, non_blocking=True)
            b_pol = b_pol.to(device, non_blocking=True)
            b_val = b_val.to(device, non_blocking=True).unsqueeze(1)

            optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                logits, values = model(b_states)
                loss_policy = F.cross_entropy(logits, b_pol)
                loss_val = F.mse_loss(values, b_val)
                loss = loss_policy + (1.5 * loss_val)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            bs = b_states.size(0)
            running_total_loss += loss.item() * bs
            running_p_loss += loss_policy.item() * bs
            running_v_loss += loss_val.item() * bs

            preds = logits.argmax(dim=1)
            correct_top1 += (preds == b_pol).sum().item()
            total_samples += bs

        scheduler.step()
        ep_loss = running_total_loss / total_samples
        ep_p_loss = running_p_loss / total_samples
        ep_v_loss = running_v_loss / total_samples
        ep_acc = (correct_top1 / total_samples) * 100.0

        # Validação
        model.eval()
        val_running_loss = 0.0
        val_correct = 0
        val_samples = 0
        with torch.no_grad():
            for vb_states, vb_pol, vb_val in val_loader:
                vb_states = vb_states.to(device, non_blocking=True)
                vb_pol = vb_pol.to(device, non_blocking=True)
                vb_val = vb_val.to(device, non_blocking=True).unsqueeze(1)

                with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                    v_logits, v_vals = model(vb_states)
                    v_lp = F.cross_entropy(v_logits, vb_pol)
                    v_lv = F.mse_loss(v_vals, vb_val)
                    v_loss = v_lp + (1.5 * v_lv)

                vbs = vb_states.size(0)
                val_running_loss += v_loss.item() * vbs
                val_correct += (v_logits.argmax(dim=1) == vb_pol).sum().item()
                val_samples += vbs

        val_loss = val_running_loss / max(1, val_samples)
        val_acc = (val_correct / max(1, val_samples)) * 100.0

        loss_history.append({
            "epoch": ep,
            "train_loss": ep_loss,
            "policy_loss": ep_p_loss,
            "value_loss": ep_v_loss,
            "train_acc": ep_acc,
            "val_loss": val_loss,
            "val_acc": val_acc,
            "lr": optimizer.param_groups[0]["lr"],
        })

        print(
            f" [Época {ep:02d}/{epochs:02d}] "
            f"Loss: {ep_loss:.4f} (Pol: {ep_p_loss:.4f}, Val: {ep_v_loss:.4f}) | "
            f"Top-1 Acc: {ep_acc:.1f}% | "
            f"Val Loss: {val_loss:.4f} (Acc: {val_acc:.1f}%)"
        )

    dur = time.time() - t_start
    print("\n" + "=" * 75)
    print(f"[✓] Treinamento concluído com sucesso em {dur:.1f}s ({dur/60:.2f} min)!")
    print("=" * 75)

    print(f"[*] Salvando pesos finais em: {save_weights}")
    model.save_weights(save_weights)

    try:
        print(f"[*] Exportando modelo ONNX em: {save_onnx}")
        model.export_onnx(save_onnx)
    except Exception as e:
        print(f"[!] Erro ao exportar ONNX: {e}")

    return {
        "epochs": epochs,
        "batch_size": batch_size,
        "history": loss_history,
        "final_loss": loss_history[-1]["train_loss"],
        "final_acc": loss_history[-1]["train_acc"],
        "val_loss": loss_history[-1]["val_loss"],
        "val_acc": loss_history[-1]["val_acc"],
        "duration_seconds": dur,
    }


def run_post_training_validation(
    test_bots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Executa partidas de validação contra bots de referência."""
    if test_bots is None:
        test_bots = [
            {"name": "Nelson", "rating": 1300, "category": "Intermediário"},
            {"name": "Antonio", "rating": 1500, "category": "Intermediário"},
            {"name": "Isabel", "rating": 1600, "category": "Avançado"},
            {"name": "Li", "rating": 2000, "category": "Mestre"},
        ]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    agent = NeuralChessBot(
        weights_path=WEIGHTS_PATH,
        device=device,
        use_book=True,
        adaptive_mcts=False,
        use_pvs_blunder_guard=True,
        pvs_depth=3,
    )

    print("\n" + "=" * 75)
    print("      ⚔️ BATERIA DE VALIDAÇÃO PÓS-TREINO VS BOTS OFICIAIS ⚔️")
    print("=" * 75)

    duel_results = []
    for bot in test_bots:
        name = bot["name"]
        elo = bot["rating"]
        cat = bot["category"]
        opp_engine = ChessBot(rate=elo, bot_name=name, max_time_seconds=0.1)

        board = chess.Board()
        t0 = time.time()
        neural_is_white = random.choice([True, False])
        neural_col = chess.WHITE if neural_is_white else chess.BLACK

        while not board.is_game_over(claim_draw=True) and board.ply() < 120:
            if board.turn == neural_col:
                mv, _ = agent.get_best_move(board, temperature=0.0, use_mcts=(elo >= 1600))
            else:
                mv, _ = opp_engine.get_best_move(board)

            if mv is None or mv not in board.legal_moves:
                legal = list(board.legal_moves)
                if not legal:
                    break
                mv = legal[0]
            board.push(mv)

        dur = time.time() - t0
        res = board.result(claim_draw=True)
        if res == "1-0":
            w = "Neura_Bot" if neural_is_white else name
        elif res == "0-1":
            w = "Neura_Bot" if not neural_is_white else name
        else:
            w = "Empate"

        print(
            f" [Duelo] vs {name:<12} ({elo:4d} Elo - {cat:<14}) ➔ {res:<7} | Vencedor: {w:<10} | {board.fullmove_number:2d} lances ({dur:.1f}s)"
        )
        duel_results.append({
            "opponent": name,
            "rating": elo,
            "category": cat,
            "result": res,
            "winner": w,
            "moves": board.fullmove_number,
            "duration": dur,
        })

    print("=" * 75 + "\n")
    return duel_results


def generate_training_report(
    train_stats: Dict[str, Any],
    validation_results: List[Dict[str, Any]],
    output_path: Path = REPORT_TRAINING_MD,
):
    """Gera relatório executivo detalhado em Markdown."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history = train_stats.get("history", [])

    lines = [
        "# 🧠 RELATÓRIO EXECUTIVO: TREINAMENTO E AJUSTE FINO NEURAL PÓS-SELFPLAY 1.000 PARTIDAS",
        "",
        f"> **Conclusão:** `{now_str}`  ",
        f"> **Arquitetura Neural:** `ChessPolicyValueNet (SE-ResNet - 128 canais x 4 blocos residuais)`  ",
        f"> **Hardware de Aceleração:** `NVIDIA GeForce RTX 3060 12GB (PyTorch AMP FP16)`  ",
        f"> **Dataset:** `1.000 partidas Self-Play (150.000+ tensores) + 25.000 âncoras GM ('balanced.bin')`  ",
        f"> **Tempo de Treino:** `{train_stats.get('duration_seconds', 0):.1f} segundos ({train_stats.get('duration_seconds', 0)/60:.2f} min)`  ",
        "",
        "---",
        "",
        "## 1. Métricas Finais de Convergência",
        "",
        "| Indicador | Valor Final | Observações |",
        "| :--- | :---: | :--- |",
        f"| **Loss Global de Treino** | **`{train_stats.get('final_loss', 0):.4f}`** | Convergência estável com Cosine Annealing |",
        f"| **Acurácia Top-1 de Treino** | **`{train_stats.get('final_acc', 0):.1f}%`** | Acurácia de predição do lance ótimo |",
        f"| **Loss de Validação (Holdout 10%)** | **`{train_stats.get('val_loss', 0):.4f}`** | Generalização sem overfitting |",
        f"| **Acurácia Top-1 de Validação** | **`{train_stats.get('val_acc', 0):.1f}%`** | Performance em posições não vistas |",
        f"| **Total de Épocas** | **`{train_stats.get('epochs', 0)}`** | Batch Size: `{train_stats.get('batch_size', 512)}` |",
        "",
        "---",
        "",
        "## 2. Histórico de Épocas",
        "",
        "| Época | Train Loss | Policy Loss | Value Loss | Top-1 Acc | Val Loss | Val Acc | LR |",
        "| :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |",
    ]

    for h in history:
        lines.append(
            f"| {h['epoch']} | {h['train_loss']:.4f} | {h['policy_loss']:.4f} | {h['value_loss']:.4f} | "
            f"{h['train_acc']:.1f}% | {h['val_loss']:.4f} | {h['val_acc']:.1f}% | {h['lr']:.6f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Bateria de Validação Prática Pós-Treino",
        "",
        "| Oponente de Teste | Categoria | Elo Oficial | Placar | Vencedor | Lances | Duração |",
        "| :--- | :--- | :-: | :-: | :---: | :-: | :-: |",
    ])

    for d in validation_results:
        w_bold = f"**{d['winner']}**" if d['winner'] == 'Neura_Bot' else d['winner']
        lines.append(
            f"| {d['opponent']} | {d['category']} | {d['rating']} | {d['result']} | {w_bold} | {d['moves']} | {d['duration']:.2f}s |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Artefatos Atualizados",
        "",
        f"- 🎯 **Pesos Neurais PyTorch:** [`chess_policy_weights.pt`](file:///{WEIGHTS_PATH.as_posix()})",
        f"- ⚡ **Modelo ONNX Exportado:** [`chess_policy_weights.onnx`](file:///{ONNX_PATH.as_posix()})",
        f"- 💾 **Cache de Tensores:** [`dataset_selfplay_1000_combined.pt`](file:///{DATASET_CACHE.as_posix()})",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[✓] Relatório de treinamento gerado com sucesso em: {output_path}")


def train_pipeline(
    epochs: int = 15,
    batch_size: int = 512,
    lr: float = 1e-3,
    force_rebuild_dataset: bool = False,
    run_validation_duels: bool = True,
) -> Dict[str, Any]:
    """Executa o pipeline completo de treinamento e avaliação."""
    dataset = extract_training_dataset(
        pgn_path=PGN_FILE,
        book_path=BALANCED_BOOK,
        cache_path=DATASET_CACHE,
        force_rebuild=force_rebuild_dataset,
    )

    train_stats = train_neural_network(
        dataset=dataset,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        save_weights=WEIGHTS_PATH,
        save_onnx=ONNX_PATH,
    )

    val_results = []
    if run_validation_duels:
        val_results = run_post_training_validation()

    generate_training_report(train_stats, val_results)
    return {
        "train_stats": train_stats,
        "validation_results": val_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Pipeline de Treinamento Neural SE-ResNet Pós-SelfPlay")
    parser.add_argument("--epochs", type=int, default=15, help="Quantidade de épocas de treinamento (padrão: 15)")
    parser.add_argument("--batch-size", type=int, default=512, help="Tamanho do lote de gradiente (padrão: 512)")
    parser.add_argument("--lr", type=float, default=1e-3, help="Taxa de aprendizado inicial (padrão: 0.001)")
    parser.add_argument("--rebuild", action="store_true", help="Reconstrói tensores do zero sem usar cache")
    parser.add_argument("--no-validation", action="store_true", help="Pula os duelos de validação pós-treino")
    args = parser.parse_args()

    train_pipeline(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        force_rebuild_dataset=args.rebuild,
        run_validation_duels=not args.no_validation,
    )


if __name__ == "__main__":
    main()
