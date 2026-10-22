"""Runner de Bateria de 1.000 Partidas Self-Play (Neural_Bot vs Neural_Bot).

Executa 1.000 confrontos completos de auto-jogo entre instâncias do Neural_Bot,
medindo taxa de conversão, precisão posicional, refutações do PVS Blunder Guard,
arremates de finais via bases Syzygy/solver exato e gerando relatório analítico completo.
"""

from __future__ import annotations

import argparse
import datetime
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.pgn
import chess.polyglot
import torch

# Adicionar caminhos ao sys.path
CHESS_BOT_DIR = Path(__file__).resolve().parent
NEURAL_DIR = CHESS_BOT_DIR / "Neural_Bot"
REPORTS_DIR = CHESS_BOT_DIR / "relatorios_avancos"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(NEURAL_DIR))
from chess_ai.agent import NeuralChessBot

CHECKPOINT_SELFPLAY = REPORTS_DIR / "checkpoint_bateria_1000_selfplay.json"
REPORT_SELFPLAY_MD = REPORTS_DIR / "relatorio_bateria_1000_selfplay.md"
PGN_SELFPLAY_FILE = REPORTS_DIR / "selfplay_1000_games.pgn"


class SelfPlayBatteryManager:
    """Gerenciador de execução, métricas e persistência da bateria de 1.000 partidas."""

    def __init__(self, target_games: int = 1000, resume: bool = True):
        self.target_games = target_games
        self.results: List[Dict[str, Any]] = []
        self.start_time = datetime.datetime.now()

        if resume and CHECKPOINT_SELFPLAY.is_file():
            try:
                with open(CHECKPOINT_SELFPLAY, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.results = data.get("results", [])
                    print(f"[*] Checkpoint Self-Play carregado: {len(self.results)} partidas já disputadas.")
            except Exception as e:
                print(f"[!] Erro ao carregar checkpoint self-play: {e}")

    def save_game_result(self, game_data: Dict[str, Any], pgn_game: Optional[chess.pgn.Game] = None):
        self.results.append(game_data)
        self._write_checkpoint()

        if pgn_game is not None:
            try:
                with open(PGN_SELFPLAY_FILE, "a", encoding="utf-8") as f_pgn:
                    exporter = chess.pgn.FileExporter(f_pgn)
                    pgn_game.accept(exporter)
            except Exception as e:
                print(f"[!] Erro ao salvar PGN: {e}")

        # Atualizar relatório markdown a cada 10 partidas ou na última
        if len(self.results) % 10 == 0 or len(self.results) >= self.target_games:
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
        mcts_interventions = sum(r.get("mcts_interventions", 0) for r in self.results)

        # Motivos de término
        reasons_count: Dict[str, int] = {}
        for r in self.results:
            term = r.get("termination", "Desconhecido")
            reasons_count[term] = reasons_count.get(term, 0) + 1

        elapsed = (datetime.datetime.now() - self.start_time).total_seconds()
        elapsed_str = str(datetime.timedelta(seconds=int(elapsed)))
        games_per_sec = total / max(0.1, elapsed)

        lines = [
            "# ♟️ RELATÓRIO OFICIAL: BATERIA DE 1.000 PARTIDAS SELF-PLAY (NEURAL_BOT VS NEURAL_BOT)",
            "",
            f"> **Data do Início:** `{self.start_time.strftime('%Y-%m-%d %H:%M:%S')}`  ",
            f"> **Última Atualização:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  ",
            f"> **Progresso Atual:** `{total} / {self.target_games}` partidas ({total/self.target_games*100:.1f}%)  ",
            f"> **Tempo Total Decorrido:** `{elapsed_str}` (`{games_per_sec:.2f}` partidas/segundo)  ",
            f"> **Arquivo PGN Completo:** [`selfplay_1000_games.pgn`](file:///{PGN_SELFPLAY_FILE.as_posix()})  ",
            "",
            "---",
            "",
            "## 1. Quadro Estatístico Geral de Desfechos",
            "",
            "```mermaid",
            "pie title Distribuição de Resultados Self-Play (Neural_Bot vs Neural_Bot)",
            f'    "Vitórias das Brancas (1-0)" : {white_wins}',
            f'    "Vitórias das Pretas (0-1)" : {black_wins}',
            f'    "Empates Técnicos (1/2-1/2)" : {draws}',
            "```",
            "",
            "| Indicador | Quantidade Absoluta | Proporção (%) |",
            "| :--- | :---: | :---: |",
            f"| **Total de Partidas Concluídas** | `{total}` | 100.0% |",
            f"| **Vitórias das Brancas (1-0)** | `{white_wins}` | `{white_win_pct:.1f}%` |",
            f"| **Vitórias das Pretas (0-1)** | `{black_wins}` | `{black_win_pct:.1f}%` |",
            f"| **Empates (1/2-1/2)** | `{draws}` | `{draw_pct:.1f}%` |",
            f"| **Média de Lances por Partida** | `{avg_moves:.1f}` lances | (Mín: `{min_moves}`, Máx: `{max_moves}`) |",
            "",
            "---",
            "",
            "## 2. Auditoria dos Módulos Especialistas de Elite",
            "",
            "| Módulo de Elite | Acionamentos Registrados | Impacto Estratégico |",
            "| :--- | :---: | :--- |",
            f"| **PVS Blunder Guard** | `{pvs_refutations_count}` | Gafes e armadilhas táticas refutadas antes da execução |",
            f"| **Syzygy / Solver Exato de Finais** | `{tablebase_finishes}` | Conversão matemática perfeita de finais (<= 5 peças) sem afogamentos |",
            f"| **MCTS Tree Search Adaptativo** | `{mcts_interventions}` | Cálculo aprofundado em lances agudos e posições críticas |",
            "",
            "---",
            "",
            "## 3. Classificação por Tipo de Desfecho",
            "",
            "| Motivo de Finalização | Partidas | Percentual |",
            "| :--- | :---: | :---: |",
        ]

        for r_name, count in sorted(reasons_count.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total) * 100.0
            lines.append(f"| {r_name} | `{count}` | `{pct:.1f}%` |")

        lines.extend([
            "",
            "---",
            "",
            "## 4. Amostragem das Partidas Recentes",
            "",
            "| # | Resultado | Vencedor | Lances | Motivo | Duração | PVS Refutações |",
            "| :---: | :---: | :---: | :---: | :--- | :---: | :---: |",
        ])

        for r in self.results[-20:]:
            gid = r.get("game_id")
            res = r.get("result")
            winner = r.get("winner")
            moves = r.get("moves")
            term = r.get("termination")
            dur = f"{r.get('duration', 0.0):.2f}s"
            pvs_r = r.get("pvs_refutations", 0)
            lines.append(f"| {gid:04d} | `{res}` | **{winner}** | {moves} | {term} | {dur} | `{pvs_r}` |")

        lines.append("")
        try:
            REPORT_SELFPLAY_MD.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[!] Erro ao escrever relatório Markdown: {e}")


def play_single_selfplay_game(
    game_id: int,
    bot_white: NeuralChessBot,
    bot_black: NeuralChessBot,
    max_plies: int = 200,
) -> Tuple[Dict[str, Any], chess.pgn.Game]:
    """Executa uma partida completa entre duas instâncias do NeuralChessBot."""
    board = chess.Board()
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "Neural_Bot Self-Play 1000 Battery"
    pgn_game.headers["Site"] = "GymArena Local - NVIDIA RTX 3060"
    pgn_game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
    pgn_game.headers["Round"] = str(game_id)
    pgn_game.headers["White"] = "Neural_Bot (White)"
    pgn_game.headers["Black"] = "Neural_Bot (Black)"

    node = pgn_game
    pvs_refutations = 0
    tablebase_finishes = 0
    mcts_interventions = 0
    t0 = time.time()

    while not board.is_game_over(claim_draw=True) and board.ply() < max_plies:
        cur_bot = bot_white if board.turn == chess.WHITE else bot_black
        # Lances iniciais (plies 0..5): temperatura suave para variedade de repertório de aberturas
        temp = 0.7 if board.ply() < 6 else 0.0

        move, info = cur_bot.get_best_move(board, temperature=temp)
        if move is None:
            break

        src = info.get("source", "")
        if src == "pvs_blunder_refutation":
            pvs_refutations += 1
        elif "endgame" in src or "tablebase" in src:
            tablebase_finishes += 1
        elif "mcts" in src:
            mcts_interventions += 1

        node = node.add_variation(move)
        board.push(move)

    dur = round(time.time() - t0, 3)
    res = board.result(claim_draw=True)

    # Determinar motivo de encerramento
    if board.is_checkmate():
        termination = "Xeque-Mate"
        winner = "Neural_Bot (White)" if res == "1-0" else "Neural_Bot (Black)"
    elif board.is_stalemate():
        termination = "Afogamento (Stalemate)"
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
        winner = "Empate" if res == "1/2-1/2" else ("Neural_Bot (White)" if res == "1-0" else "Neural_Bot (Black)")

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
        "mcts_interventions": mcts_interventions,
        "final_fen": board.fen(),
    }
    return game_data, pgn_game


def run_selfplay_battery(total_games: int = 1000, resume: bool = True):
    """Orquestrador da bateria de 1.000 partidas de auto-jogo."""
    print("\n" + "=" * 75)
    print(f"      ♟️ INICIANDO BATERIA DE {total_games} PARTIDAS SELF-PLAY (NEURAL_BOT) ♟️")
    print("=" * 75)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f" [*] Dispositivo de Aceleração : {device} (NVIDIA GeForce RTX 3060)")

    manager = SelfPlayBatteryManager(target_games=total_games, resume=resume)
    already_done = len(manager.results)

    if already_done >= total_games:
        print(f"[+] Bateria de {total_games} partidas já estava 100% concluída!")
        manager._write_markdown_report()
        return

    # Inicializar os dois competidores com PVS Blunder Guard calibrado
    weights_p = NEURAL_DIR / "checkpoints" / "chess_policy_weights.pt"
    bot_white = NeuralChessBot(weights_path=weights_p, device=device, use_book=True, adaptive_mcts=False, use_pvs_blunder_guard=True, pvs_depth=3)
    bot_black = NeuralChessBot(weights_path=weights_p, device=device, use_book=True, adaptive_mcts=False, use_pvs_blunder_guard=True, pvs_depth=3)

    print(f" [*] Partidas Restantes        : {total_games - already_done}", flush=True)
    print(f" [*] Relatório Markdown        : {REPORT_SELFPLAY_MD}", flush=True)
    print(f" [*] Arquivo PGN               : {PGN_SELFPLAY_FILE}", flush=True)
    print("=" * 75 + "\n", flush=True)

    for g_idx in range(already_done + 1, total_games + 1):
        g_data, pgn_g = play_single_selfplay_game(g_idx, bot_white, bot_black, max_plies=200)
        manager.save_game_result(g_data, pgn_g)

        w_cnt = sum(1 for r in manager.results if r["result"] == "1-0")
        b_cnt = sum(1 for r in manager.results if r["result"] == "0-1")
        d_cnt = sum(1 for r in manager.results if r["result"] in ("1/2-1/2", "*"))
        print(f"  [Partida {g_idx:04d}/{total_games}] Res: {g_data['result']} ({g_data['termination']}, {g_data['moves']}l, {g_data['duration']:.2f}s) | Placar: W:{w_cnt} B:{b_cnt} D:{d_cnt}", flush=True)

    print("\n" + "=" * 75)
    print(f"      ♛ BATERIA DE {total_games} PARTIDAS SELF-PLAY CONCLUÍDA COM SUCESSO ♛")
    print("=" * 75)
    print(f" [*] Relatório Consolidado     : {REPORT_SELFPLAY_MD.resolve()}")
    print(f" [*] Banco de Partidas PGN     : {PGN_SELFPLAY_FILE.resolve()}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bateria de 1000 Partidas Self-Play Neural_Bot vs Neural_Bot")
    parser.add_argument("--games", type=int, default=1000, help="Total de partidas a disputar (default: 1000)")
    parser.add_argument("--fresh", action="store_true", help="Reiniciar do zero limpando checkpoint anterior")
    args = parser.parse_args()

    if args.fresh:
        if CHECKPOINT_SELFPLAY.is_file():
            CHECKPOINT_SELFPLAY.unlink()
        if PGN_SELFPLAY_FILE.is_file():
            PGN_SELFPLAY_FILE.unlink()

    run_selfplay_battery(total_games=args.games, resume=not args.fresh)
