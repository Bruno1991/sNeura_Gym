"""Runner de Bateria de Partidas Self-Play Ultra-Acelerado (30x) e Baixa RAM (runners.selfplay).

Executa confrontos completos de auto-jogo entre instâncias do Neura Bot,
utilizando workers paralelos em memória (In-Memory Thread Pool),
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
from typing import Any, Callable, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import chess
import chess.pgn
import torch

CHESS_BOT_DIR = Path(__file__).resolve().parent.parent
NEURAL_DIR = CHESS_BOT_DIR / "Neural_Bot"
REPORTS_DIR = CHESS_BOT_DIR / "relatorios_avancos"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(NEURAL_DIR))
from chess_ai.agent import NeuralChessBot

CHECKPOINT_SELFPLAY = REPORTS_DIR / "checkpoint_bateria_1000_selfplay.json"
REPORT_SELFPLAY_MD = REPORTS_DIR / "relatorio_bateria_1000_selfplay.md"
PGN_SELFPLAY_FILE = REPORTS_DIR / "selfplay_1000_games.pgn"


class SelfPlayManager:
    """Gerencia a coleta, checkpoints, exportação PGN e relatório da bateria de auto-jogo."""

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
            f"# ♟️ RELATÓRIO DA BATERIA DE {self.target_games:,} PARTIDAS SELF-PLAY (MODO ACELERADO 30X)",
            "",
            f"> **Data/Hora de Conclusão:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  ",
            f"> **Progresso Atual:** `{total} / {self.target_games} partidas ({(total/self.target_games)*100:.1f}%)`  ",
            f"> **Tempo de Execução:** `{elapsed_str}`  ",
            f"> **Arquivo PGN Consolidado:** [`selfplay_1000_games.pgn`](file:///{PGN_SELFPLAY_FILE.as_posix()})  ",
            f"> **Mecanismo:** `Neura Bot vs Neura Bot (SE-ResNet + PVS Blunder Guard + Syzygy Solver)`  ",
            "",
            "---",
            "",
            "## 1. Resumo Executivo dos Resultados",
            "",
            "| Resultado | Quantidade Absoluta | Percentual |",
            "| :--- | :---: | :---: |",
            f"| ⚪ **Vitórias das Brancas (1-0)** | **{white_wins}** | **{white_win_pct:.1f}%** |",
            f"| ⚫ **Vitórias das Pretas (0-1)** | **{black_wins}** | **{black_win_pct:.1f}%** |",
            f"| ⚖️ **Empates (1/2 - 1/2)** | **{draws}** | **{draw_pct:.1f}%** |",
            f"| 🏆 **Taxa Decisiva Global** | **{white_wins + black_wins}** | **{((white_wins + black_wins)/total)*100:.1f}%** |",
            "",
            "---",
            "",
            "## 2. Métricas de Eficiência e Partidas",
            "",
            f"- **Média de Lances por Partida:** `{avg_moves:.1f} lances`",
            f"- **Partida Mais Curta:** `{min_moves} lances`",
            f"- **Partida Mais Longa:** `{max_moves} lances`",
            f"- **Refutações Táticas PVS Registradas:** `{pvs_refutations_count} lances`",
            f"- **Finais Syzygy Tablebase Acionados:** `{tablebase_finishes} partidas`",
            "",
            "---",
            "",
            "## 3. Motivos de Término",
            "",
            "| Tipo de Término | Partidas | Percentual |",
            "| :--- | :---: | :---: |",
        ]

        for term, count in sorted(term_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {term} | {count} | {(count/total)*100:.1f}% |")

        lines.extend([
            "",
            "---",
            "",
            "## 4. Últimas 20 Partidas Registradas",
            "",
            "| # | Resultado | Lances | Término | Duração (s) | Abertura (ECO) |",
            "| :-: | :---: | :-: | :--- | :-: | :--- |",
        ])

        recent = self.results[-20:]
        for r in recent:
            lines.append(
                f"| {r['game_id']} | **{r['result']}** | {r['moves']} | {r['termination']} | {r['duration']:.2f}s | {r.get('eco', 'N/A')} |"
            )

        try:
            REPORT_SELFPLAY_MD.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[!] Erro ao salvar relatório self-play Markdown: {e}")


def play_one_selfplay_game(
    game_id: int,
    bot_white: NeuralChessBot,
    bot_black: NeuralChessBot,
    max_plies: int = 150,
) -> Tuple[Dict[str, Any], chess.pgn.Game]:
    """Executa uma única partida de auto-jogo entre duas instâncias neurais."""
    board = chess.Board()
    t0 = time.time()

    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = f"Neura Gym Self-Play Battery"
    pgn_game.headers["Site"] = "C:\\dev\\s_Neura_Gym"
    pgn_game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
    pgn_game.headers["Round"] = str(game_id)
    pgn_game.headers["White"] = "Neura_Bot (White)"
    pgn_game.headers["Black"] = "Neura_Bot (Black)"

    node = pgn_game
    pvs_count = 0
    tb_count = 0

    while not board.is_game_over(claim_draw=True) and board.ply() < max_plies:
        agent = bot_white if board.turn == chess.WHITE else bot_black
        move, info = agent.get_best_move(board, temperature=0.1, use_mcts=False)

        if move is None or move not in board.legal_moves:
            legal = list(board.legal_moves)
            if not legal:
                break
            move = legal[0]

        if info.get("source") == "pvs_blunder_guard":
            pvs_count += 1
        elif info.get("source") == "syzygy_tablebase":
            tb_count += 1

        node = node.add_variation(move)
        board.push(move)

    dur = time.time() - t0
    res = board.result(claim_draw=True)
    pgn_game.headers["Result"] = res

    term = "Limite de Lances"
    if board.is_checkmate():
        term = "Xeque-Mate"
    elif board.is_stalemate():
        term = "Afogamento (Stalemate)"
    elif board.is_insufficient_material():
        term = "Material Insuficiente"
    elif board.is_seventyfive_moves() or board.can_claim_fifty_moves():
        term = "Regra dos 50 Lances"
    elif board.is_fivefold_repetition() or board.can_claim_threefold_repetition():
        term = "Repetição Tripla"

    game_info = {
        "game_id": game_id,
        "result": res,
        "moves": board.fullmove_number,
        "plies": board.ply(),
        "termination": term,
        "duration": round(dur, 2),
        "pvs_refutations": pvs_count,
        "tablebase_finishes": tb_count,
        "fen": board.fen(),
    }
    return game_info, pgn_game


def run_selfplay(
    target_games: int = 1000,
    workers: int = 4,
    fresh: bool = False,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Inicia a bateria acelerada de partidas de auto-jogo."""
    print("=" * 75)
    print(f"      ♟️ BATERIA DE {target_games:,} PARTIDAS SELF-PLAY (MODO 30X) ♟️")
    print("=" * 75)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f" [*] Dispositivo de Aceleração : {device} (RTX 3060)")

    weights_p = NEURAL_DIR / "checkpoints" / "chess_policy_weights.pt"

    bot_w = NeuralChessBot(
        weights_path=weights_p,
        device=device,
        use_book=True,
        adaptive_mcts=False,
        use_pvs_blunder_guard=True,
        pvs_depth=3,
    )
    bot_b = NeuralChessBot(
        weights_path=weights_p,
        device=device,
        use_book=True,
        adaptive_mcts=False,
        use_pvs_blunder_guard=True,
        pvs_depth=3,
    )

    if fresh:
        if CHECKPOINT_SELFPLAY.is_file():
            CHECKPOINT_SELFPLAY.unlink()
        if REPORT_SELFPLAY_MD.is_file():
            REPORT_SELFPLAY_MD.unlink()
        if PGN_SELFPLAY_FILE.is_file():
            PGN_SELFPLAY_FILE.unlink()

    manager = SelfPlayManager(target_games=target_games, resume=not fresh)
    completed_count = len(manager.results)
    remaining_games = target_games - completed_count

    print(f" [*] Meta Total de Partidas     : {target_games:,}")
    print(f" [*] Partidas Já Concluídas     : {completed_count:,}")
    print(f" [*] Partidas a Realizar        : {max(0, remaining_games):,}")
    print(f" [*] Workers Paralelos          : {workers} Threads In-Memory")
    print(f" [*] Destino PGN                : {PGN_SELFPLAY_FILE.name}")
    print("=" * 75 + "\n")

    if remaining_games <= 0:
        print("[✓] A bateria já atingiu a meta total no checkpoint!")
        return {
            "target_games": target_games,
            "completed": completed_count,
            "results": manager.results,
        }

    t_start = time.time()
    next_id = completed_count + 1

    def task(g_id: int):
        return play_one_selfplay_game(g_id, bot_w, bot_b)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(task, next_id + i): (next_id + i) for i in range(remaining_games)}

        for f in concurrent.futures.as_completed(futures):
            try:
                g_info, pgn_obj = f.result()
                manager.save_game(g_info, pgn_obj)
                cur_total = len(manager.results)
                pct = (cur_total / target_games) * 100.0

                if progress_callback:
                    progress_callback(g_info)

                print(
                    f"[{cur_total:04d}/{target_games}] Partida #{g_info['game_id']:04d} ➔ "
                    f"Placar: {g_info['result']:<7} | {g_info['moves']:2d} lances ({g_info['termination']:<18}) | "
                    f"{g_info['duration']:.2f}s | Progresso: {pct:.1f}%",
                    flush=True,
                )
            except Exception as e:
                print(f"[!] Erro em partida self-play: {e}", flush=True)

    dur = time.time() - t_start
    dur_str = str(datetime.timedelta(seconds=int(dur)))
    print("\n" + "=" * 75)
    print(f"      ♟️ BATERIA DE {target_games:,} PARTIDAS CONCLUÍDA EM {dur_str} ♟️")
    print("=" * 75 + "\n")

    return {
        "target_games": target_games,
        "completed": len(manager.results),
        "results": manager.results,
        "elapsed": dur_str,
    }


def main():
    parser = argparse.ArgumentParser(description="Runner de Bateria Self-Play Neura Bot (30x Acelerado)")
    parser.add_argument("--games", type=int, default=1000, help="Total de partidas a simular (padrão: 1000)")
    parser.add_argument("--workers", type=int, default=4, help="Número de workers paralelos (padrão: 4)")
    parser.add_argument("--fresh", action="store_true", help="Reinicia do zero descartando checkpoint e PGN")
    parser.add_argument("--resume", action="store_true", help="Continua do checkpoint anterior (padrão)")
    args = parser.parse_args()

    fresh = args.fresh or (not args.resume and not CHECKPOINT_SELFPLAY.is_file())
    run_selfplay(target_games=args.games, workers=args.workers, fresh=fresh)


if __name__ == "__main__":
    main()
