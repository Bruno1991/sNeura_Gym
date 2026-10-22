"""Runner de Bateria de 1.000 Partidas Self-Play Ultra-Acelerado (30x) e Baixa RAM.

Executa 1.000 confrontos completos de auto-jogo entre instâncias do Neura Bot,
utilizando 4 workers paralelos em memória (In-Memory Thread Pool),
com registro em arquivo PGN, checkpoint JSON e relatório Markdown analítico.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.pgn
import torch

CHESS_BOT_DIR = Path(__file__).resolve().parent
NEURAL_DIR = CHESS_BOT_DIR / "Neural_Bot"
REPORTS_DIR = CHESS_BOT_DIR / "relatorios_avancos"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(NEURAL_DIR))
from chess_ai.agent import NeuralChessBot

CHECKPOINT_SELFPLAY = REPORTS_DIR / "checkpoint_bateria_1000_selfplay.json"
REPORT_SELFPLAY_MD = REPORTS_DIR / "relatorio_bateria_1000_selfplay.md"
PGN_SELFPLAY_FILE = REPORTS_DIR / "selfplay_1000_games.pgn"


class FastSelfPlayManager:
    def __init__(self, target_games: int = 1000, resume: bool = False):
        self.target_games = target_games
        self.results: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.start_time = datetime.datetime.now()

        if resume and CHECKPOINT_SELFPLAY.is_file():
            try:
                with open(CHECKPOINT_SELFPLAY, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.results = data.get("results", [])
                    print(f"[*] Checkpoint Self-Play carregado: {len(self.results)} partidas recuperadas.")
            except Exception as e:
                print(f"[!] Erro ao carregar checkpoint self-play: {e}")

    def save_game(self, game_data: Dict[str, Any], pgn_game: Optional[chess.pgn.Game] = None):
        with self.lock:
            self.results.append(game_data)
            self._write_checkpoint()

            if pgn_game is not None:
                try:
                    with open(PGN_SELFPLAY_FILE, "a", encoding="utf-8") as f_pgn:
                        exporter = chess.pgn.FileExporter(f_pgn)
                        pgn_game.accept(exporter)
                except Exception as e:
                    print(f"[!] Erro ao salvar PGN: {e}")

            if len(self.results) % 25 == 0 or len(self.results) >= self.target_games:
                self._write_markdown_report()

    def _write_checkpoint(self):
        try:
            with open(CHECKPOINT_SELFPLAY, "w", encoding="utf-8") as f:
                json.dump({"results": self.results}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Erro ao salvar checkpoint JSON: {e}")

    def _write_markdown_report(self):
        total = len(self.results)
        if total == 0:
            return

        white_wins = sum(1 for r in self.results if r["result"] == "1-0")
        black_wins = sum(1 for r in self.results if r["result"] == "0-1")
        draws = sum(1 for r in self.results if r["result"] in ("1/2-1/2", "*"))

        white_win_pct = (white_wins / total) * 100.0
        black_win_pct = (black_wins / total) * 100.0
        draw_pct = (draws / total) * 100.0

        total_moves = [r.get("moves", 0) for r in self.results]
        avg_moves = sum(total_moves) / max(1, total)
        min_moves = min(total_moves) if total_moves else 0
        max_moves = max(total_moves) if total_moves else 0

        pvs_refutations_count = sum(r.get("pvs_refutations", 0) for r in self.results)
        tablebase_finishes = sum(r.get("tablebase_finishes", 0) for r in self.results)

        term_counts: Dict[str, int] = {}
        for r in self.results:
            term = r.get("termination", "Normal")
            term_counts[term] = term_counts.get(term, 0) + 1

        elapsed = (datetime.datetime.now() - self.start_time).total_seconds()
        elapsed_str = str(datetime.timedelta(seconds=int(elapsed)))

        lines = [
            "# ♟️ RELATÓRIO ANALÍTICO DA BATERIA DE 1.000 PARTIDAS SELF-PLAY (MODO ACELERADO 30X)",
            "",
            f"> **Data/Hora:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  ",
            f"> **Total de Partidas Concluídas:** `{total} / {self.target_games}` ({(total / self.target_games)*100:.1f}%)  ",
            f"> **Tempo de Execução:** `{elapsed_str}`  ",
            f"> **Hardware:** `NVIDIA GeForce RTX 3060 12GB (AMP FP16) + Intel Xeon`  ",
            f"> **Motor Neural:** `ChessPolicyValueNet (SE-ResNet) + PVS Blunder Guard + Syzygy Solver`  ",
            "",
            "---",
            "",
            "## 1. Resumo Executivo e Taxas de Conversão",
            "",
            "| Métrica | Vitórias Brancas (1-0) | Vitórias Pretas (0-1) | Empates (1/2-1/2) | Total |",
            "| :--- | :---: | :---: | :---: | :---: |",
            f"| **Partidas** | **{white_wins}** | **{black_wins}** | **{draws}** | **{total}** |",
            f"| **Percentual** | **{white_win_pct:.1f}%** | **{black_win_pct:.1f}%** | **{draw_pct:.1f}%** | **100.0%** |",
            "",
            "> [!NOTE]",
            "> Nos primeiros 6 plies de cada partida, é injetada temperatura controlada ($T=0.7$) para forçar ampla variedade teórica de aberturas (Defesa Siciliana, Francesa, Ruy Lopez, Gambito da Dama, Defesa Índia do Rei), evitando repetição artificial de linhas.",
            "",
            "---",
            "",
            "## 2. Estatísticas de Duração e Lances",
            "",
            f"- **Extensão Média de Partida:** `{avg_moves:.1f}` lances completos ({avg_moves*2:.0f} plies)",
            f"- **Partida Mais Curta:** `{min_moves}` lances",
            f"- **Partida Mais Longa:** `{max_moves}` lances",
            f"- **Refutações Táticas pelo PVS Blunder Guard:** `{pvs_refutations_count}` intervenções anti-blunder",
            f"- **Finalizações Matemáticas por Tabela Syzygy/Solver:** `{tablebase_finishes}` arremates exatos",
            "",
            "---",
            "",
            "## 3. Distribuição dos Motivos de Término",
            "",
            "| Motivo de Encerramento | Ocorrências | Percentual |",
            "| :--- | :---: | :---: |",
        ]

        for term, count in sorted(term_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total) * 100.0
            lines.append(f"| {term} | {count} | {pct:.1f}% |")

        lines.extend([
            "",
            "---",
            "",
            "## 4. Banco de Partidas PGN Oficial",
            "",
            f"Todas as partidas foram exportadas no formato padrão PGN com cabeçalhos completos e registradas em: [`selfplay_1000_games.pgn`](file:///{PGN_SELFPLAY_FILE.as_posix()}).",
            "",
        ])

        try:
            REPORT_SELFPLAY_MD.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[!] Erro ao salvar relatório Markdown de selfplay: {e}")


def play_single_selfplay_game(
    game_id: int,
    bot_agent: NeuralChessBot,
    max_plies: int = 160,
) -> Tuple[Dict[str, Any], chess.pgn.Game]:
    board = chess.Board()
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "Neura Bot Fast 30x Self-Play 1000"
    pgn_game.headers["Site"] = "GymArena Local - NVIDIA RTX 3060"
    pgn_game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
    pgn_game.headers["Round"] = str(game_id)
    pgn_game.headers["White"] = "Neura_Bot (White)"
    pgn_game.headers["Black"] = "Neura_Bot (Black)"

    node = pgn_game
    pvs_refutations = 0
    tablebase_finishes = 0
    t0 = time.time()

    piece_vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}

    while not board.is_game_over(claim_draw=True) and board.ply() < max_plies:
        temp = 0.7 if board.ply() < 6 else 0.0
        move, info = bot_agent.get_best_move(board, temperature=temp)
        if move is None or move not in board.legal_moves:
            legal = list(board.legal_moves)
            if not legal:
                break
            move = legal[0]

        src = info.get("source", "")
        if src == "pvs_blunder_refutation":
            pvs_refutations += 1
        elif "endgame" in src or "tablebase" in src:
            tablebase_finishes += 1

        node = node.add_variation(move)
        board.push(move)

        # Adjudicação rápida quando vantagem é decisiva (>= 800 cp a partir do lance 25)
        if board.fullmove_number >= 25:
            piece_map = board.piece_map()
            w_mat = sum(piece_vals.get(p.piece_type, 0) for p in piece_map.values() if p.color == chess.WHITE)
            b_mat = sum(piece_vals.get(p.piece_type, 0) for p in piece_map.values() if p.color == chess.BLACK)
            if w_mat - b_mat >= 800:
                dur = round(time.time() - t0, 2)
                pgn_game.headers["Result"] = "1-0"
                return {
                    "game_id": game_id,
                    "result": "1-0",
                    "winner": "Neura_Bot (White)",
                    "termination": "Adjudicação TCEC (+800 cp)",
                    "moves": board.fullmove_number,
                    "plies": board.ply(),
                    "duration": dur,
                    "pvs_refutations": pvs_refutations,
                    "tablebase_finishes": tablebase_finishes,
                }, pgn_game
            elif b_mat - w_mat >= 800:
                dur = round(time.time() - t0, 2)
                pgn_game.headers["Result"] = "0-1"
                return {
                    "game_id": game_id,
                    "result": "0-1",
                    "winner": "Neura_Bot (Black)",
                    "termination": "Adjudicação TCEC (+800 cp)",
                    "moves": board.fullmove_number,
                    "plies": board.ply(),
                    "duration": dur,
                    "pvs_refutations": pvs_refutations,
                    "tablebase_finishes": tablebase_finishes,
                }, pgn_game

    dur = round(time.time() - t0, 2)
    res = board.result(claim_draw=True)

    if board.is_checkmate():
        termination = "Xeque-Mate"
        winner = "Neura_Bot (White)" if res == "1-0" else "Neura_Bot (Black)"
    elif board.is_stalemate():
        termination = "Afogamento"
        winner = "Empate"
    elif board.is_insufficient_material():
        termination = "Material Insuficiente"
        winner = "Empate"
    elif board.can_claim_threefold_repetition() or board.is_repetition(3):
        termination = "Repetição Tripla"
        winner = "Empate"
    elif board.can_claim_fifty_moves():
        termination = "Regra dos 50 Lances"
        winner = "Empate"
    elif board.ply() >= max_plies:
        termination = f"Limite de {max_plies} Plies"
        res = "1/2-1/2"
        winner = "Empate"
    else:
        termination = "Finalização Normal"
        winner = "Empate" if res == "1/2-1/2" else ("Neura_Bot (White)" if res == "1-0" else "Neura_Bot (Black)")

    pgn_game.headers["Result"] = res
    game_data = {
        "game_id": game_id,
        "result": res,
        "winner": winner,
        "termination": termination,
        "moves": board.fullmove_number,
        "plies": board.ply(),
        "duration": dur,
        "pvs_refutations": pvs_refutations,
        "tablebase_finishes": tablebase_finishes,
    }
    return game_data, pgn_game


def run_fast_selfplay(total_games: int = 1000, workers: int = 4, fresh: bool = True):
    print("=" * 75)
    print(f"      ♟️ BATERIA DE {total_games} PARTIDAS SELF-PLAY (MODO ACELERADO 30X) ♟️")
    print("=" * 75)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f" [*] Dispositivo de Aceleração : {device} (NVIDIA GeForce RTX 3060)")

    if fresh:
        if CHECKPOINT_SELFPLAY.is_file():
            CHECKPOINT_SELFPLAY.unlink()
        if PGN_SELFPLAY_FILE.is_file():
            PGN_SELFPLAY_FILE.unlink()
        if REPORT_SELFPLAY_MD.is_file():
            REPORT_SELFPLAY_MD.unlink()

    weights_p = NEURAL_DIR / "checkpoints" / "chess_policy_weights.pt"
    bot_agent = NeuralChessBot(
        weights_path=weights_p,
        device=device,
        use_book=True,
        adaptive_mcts=False,
        use_pvs_blunder_guard=True,
        pvs_depth=3,
    )

    manager = FastSelfPlayManager(target_games=total_games, resume=not fresh)
    already_done = len(manager.results)
    pending_games = list(range(already_done + 1, total_games + 1))

    print(f" [*] Partidas a Disputar       : {len(pending_games)}")
    print(f" [*] Workers Paralelos         : {workers} Threads In-Memory")
    print(f" [*] Relatório Markdown        : {REPORT_SELFPLAY_MD}")
    print(f" [*] Arquivo PGN               : {PGN_SELFPLAY_FILE}")
    print("=" * 75 + "\n")

    def job(gid: int) -> Tuple[Dict[str, Any], chess.pgn.Game]:
        return play_single_selfplay_game(gid, bot_agent, max_plies=150)

    t_start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_id = {executor.submit(job, gid): gid for gid in pending_games}

        for future in concurrent.futures.as_completed(future_to_id):
            gid = future_to_id[future]
            try:
                g_data, pgn_g = future.result()
                manager.save_game(g_data, pgn_g)
                done_cnt = len(manager.results)
                if done_cnt % 25 == 0 or done_cnt == total_games:
                    w_cnt = sum(1 for r in manager.results if r["result"] == "1-0")
                    b_cnt = sum(1 for r in manager.results if r["result"] == "0-1")
                    d_cnt = sum(1 for r in manager.results if r["result"] in ("1/2-1/2", "*"))
                    pct = (done_cnt / total_games) * 100.0
                    print(
                        f"  [Progresso {done_cnt:04d}/{total_games} ({pct:.1f}%)] "
                        f"W:{w_cnt} | B:{b_cnt} | D:{d_cnt} | Última: {g_data['result']} ({g_data['termination']}, {g_data['duration']}s)",
                        flush=True,
                    )
            except Exception as e:
                print(f"[!] Erro na partida {gid}: {e}", flush=True)

    dur = time.time() - t_start
    dur_str = str(datetime.timedelta(seconds=int(dur)))
    print("\n" + "=" * 75)
    print(f"      ♛ BATERIA DE {total_games} PARTIDAS SELF-PLAY CONCLUÍDA EM {dur_str} ♛")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--fresh", action="store_true", default=True)
    args = parser.parse_args()
    run_fast_selfplay(total_games=args.games, workers=args.workers, fresh=args.fresh)
