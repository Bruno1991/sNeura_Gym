"""Torneio Oficial Melhor de 3 na GymArena no Chromium Headless.

Executa séries Melhor de 3 entre o Neural_Bot 3200 (MCTS=200, Live Speed=100ms)
e todos os bots do catálogo oficial do Chess.com de todos os ratings Elo disponíveis.
Conecta via Playwright em Chromium Headless, intercepta e audita erros de console,
erros de página e requisições HTTP, gerando relatório detalhado em /relatorios_avancos.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"
REPORTS_DIR = CURRENT_DIR / "relatorios_avancos"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORTS_DIR / "relatorio_torneio_melhor_de_3_mcts200.md"
BOTS_DATA_PATH = CURRENT_DIR / "bots_data.json"
if not BOTS_DATA_PATH.is_file():
    BOTS_DATA_PATH = Path(r"C:\dev\s_ADB_Tools\bots_data.json")


def is_server_alive() -> bool:
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/match/state", headers={"User-Agent": "TournamentRunner"})
        with urllib.request.urlopen(req, timeout=1.5) as res:
            return res.status == 200
    except Exception:
        return False


def ensure_server_running() -> Optional[subprocess.Popen]:
    if is_server_alive():
        print("[+] Servidor GymArena já está ativo na porta 8000.")
        return None

    print("[*] Iniciando servidor GymArena em background...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "arena.server:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(CURRENT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(40):
        time.sleep(0.5)
        if is_server_alive():
            print("[+] Servidor GymArena online e pronto para o torneio!")
            return proc

    raise RuntimeError("Falha ao inicializar servidor GymArena na porta 8000.")


def load_all_bots(mode: str = "all_elos") -> List[Dict[str, Any]]:
    """Carrega bots do catálogo oficial.
    
    mode="all_elos": Seleciona o bot representante de cada um dos 66 ratings Elo disponíveis (1 a 3200).
    mode="all": Retorna todos os 200 bots únicos do catálogo.
    """
    if not BOTS_DATA_PATH.is_file():
        raise FileNotFoundError(f"Arquivo de bots não encontrado: {BOTS_DATA_PATH}")

    with open(BOTS_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    seen = set()
    bot_list = []
    for g in data.get("botGroups", []):
        cat_name = g.get("name", "Geral")
        for b in g.get("botPersonalities", []):
            name = b.get("name")
            if name and name not in seen:
                seen.add(name)
                bot_list.append({
                    "name": name,
                    "rating": int(b.get("rating", 1500)),
                    "category": cat_name,
                    "book": b.get("book", "balanced"),
                    "bio": b.get("bio", b.get("description", "")),
                })

    bot_list.sort(key=lambda x: (x["rating"], x["name"]))

    if mode == "all_elos":
        by_elo = {}
        for b in bot_list:
            elo = b["rating"]
            if elo not in by_elo:
                by_elo[elo] = b
        return [by_elo[e] for e in sorted(by_elo.keys())]

    return bot_list


CHECKPOINT_FILE = REPORTS_DIR / "checkpoint_melhor_de_3.json"


class TournamentManager:
    def __init__(self, bots: List[Dict[str, Any]], resume: bool = True):
        self.bots = bots
        self.results_by_bot: List[Dict[str, Any]] = []
        self.console_errors: List[str] = []
        self.page_errors: List[str] = []
        self.failed_requests: List[str] = []
        self.start_time = datetime.datetime.now()

        if resume and CHECKPOINT_FILE.is_file():
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.results_by_bot = data.get("results", [])
                    print(f"[*] Checkpoint carregado: {len(self.results_by_bot)} séries já concluídas.")
            except Exception as e:
                print(f"[!] Erro ao carregar checkpoint: {e}")

    def update_markdown_report(self):
        """Gera e persiste o relatório atualizado em Markdown e salva checkpoint."""
        try:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump({"results": self.results_by_bot}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Erro ao salvar checkpoint: {e}")
        total_series = len(self.results_by_bot)
        total_games = sum(b.get("games_played", 0) for b in self.results_by_bot)
        neural_series_won = sum(1 for b in self.results_by_bot if b.get("winner") == "Neural_Bot")
        opp_series_won = sum(1 for b in self.results_by_bot if b.get("winner") != "Neural_Bot" and b.get("winner") != "Empate")
        draw_series = sum(1 for b in self.results_by_bot if b.get("winner") == "Empate")

        total_neural_game_wins = sum(b.get("neural_wins", 0) for b in self.results_by_bot)
        total_opp_game_wins = sum(b.get("opp_wins", 0) for b in self.results_by_bot)
        total_game_draws = sum(b.get("draws", 0) for b in self.results_by_bot)

        series_win_rate = (neural_series_won / total_series * 100.0) if total_series > 0 else 0.0
        game_win_rate = (total_neural_game_wins / total_games * 100.0) if total_games > 0 else 0.0

        elapsed = datetime.datetime.now() - self.start_time
        elapsed_str = str(elapsed).split(".")[0]

        lines = [
            "# ♛ Relatório Oficial de Torneio: GymArena Chromium Headless ♛",
            "",
            f"> **Data de Execução:** {self.start_time.strftime('%d/%m/%Y %H:%M:%S')} | **Tempo Decorrido:** {elapsed_str}",
            "> **Ambiente:** Chromium Headless (Google Chrome Oficial) via Playwright",
            "> **Motor Neural:** `Neural_Bot 3200 Elo` (ResNet 128ch + 4 Blocks, MCTS=200 nós, Escudo Tático & Endgame Finisher)",
            "> **Regras da Partida:** Melhor de 3 partidas (MD3), Cor Aleatória, Duelo ao Vivo 100ms, MCTS=ON",
            "",
            "---",
            "",
            "## 1. Resumo Executivo da Performance",
            "",
            "| Métrica Geral | Valor |",
            "| :--- | :--- |",
            f"| **Total de Bots Enfrentados** | `{total_series}` de `{len(self.bots)}` |",
            f"| **Total de Partidas Jogadas** | `{total_games}` partidas individuais |",
            f"| **Séries Vencidas pelo Neural_Bot** | `{neural_series_won}` ({series_win_rate:.1f}%) |",
            f"| **Séries Perdidas pelo Neural_Bot** | `{opp_series_won}` |",
            f"| **Séries Empatadas** | `{draw_series}` |",
            f"| **Placar Global de Partidas** | `{total_neural_game_wins} Vitórias` / `{total_opp_game_wins} Derrotas` / `{total_game_draws} Empates` ({game_win_rate:.1f}% Win Rate) |",
            f"| **Erros de Página (JavaScript)** | `{len(self.page_errors)}` |",
            f"| **Erros de Console (DevTools)** | `{len(self.console_errors)}` |",
            f"| **Falhas de Rede (HTTP >= 400)** | `{len(self.failed_requests)}` |",
            "",
            "---",
            "",
            "## 2. Tabela Detalhada das Séries Melhor de 3",
            "",
            "| # | Bot Oponente | Elo | Categoria | Placar MD3 | Vencedor da Série | Lances Totais | Duração Total | Detalhes das Partidas |",
            "| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
        ]

        for idx, res in enumerate(self.results_by_bot, 1):
            bot_name = res["name"]
            elo = res["rating"]
            cat = res["category"]
            score = f"{res['neural_wins']} - {res['opp_wins']}" + (f" ({res['draws']}E)" if res['draws'] > 0 else "")
            winner = res["winner"]
            winner_badge = f"**{winner}**" if winner == "Neural_Bot" else f"<span style='color:red;'>{winner}</span>"
            tot_moves = res.get("total_moves", 0)
            tot_dur = f"{res.get('total_duration', 0.0):.1f}s"

            games_summary = []
            for g in res.get("games", []):
                g_num = g["game"]
                g_color = g["color"]
                g_res = g["result"]
                g_moves = g["moves"]
                games_summary.append(f"G{g_num}: {g_res} ({g_color[0].upper()}, {g_moves}l)")
            games_str = " | ".join(games_summary)

            lines.append(f"| {idx:02d} | **{bot_name}** | {elo} | {cat} | `{score}` | {winner_badge} | {tot_moves} | {tot_dur} | {games_str} |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. Auditoria de Confiabilidade & Integridade do Frontend / Backend",
            "",
            f"- **Exceções de Página não Tratadas:** {len(self.page_errors)}",
            f"- **Erros no Console do Chromium:** {len(self.console_errors)}",
            f"- **Erros de Rede / WebSocket / HTTP:** {len(self.failed_requests)}",
            "",
        ])

        if self.console_errors:
            lines.append("### Detalhes dos Erros de Console:")
            for err in self.console_errors[:15]:
                lines.append(f"- `{err}`")

        REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
        print(f"[+] Relatório de torneio atualizado em: {REPORT_FILE.name}")


def run_tournament(max_bots: Optional[int] = None, mode: str = "all_elos"):
    server_proc = ensure_server_running()
    all_bots = load_all_bots(mode=mode)
    if max_bots:
        selected_bots = all_bots[:max_bots]
    else:
        selected_bots = all_bots

    print("\n" + "=" * 70)
    print("      ♛ TORNEIO GYMARENA: MELHOR DE 3 COM TODOS OS BOTS (CHROMIUM) ♛")
    print("=" * 70)
    print(f" [*] Total de Bots Selecionados : {len(selected_bots)} bots")
    print(f" [*] Faixa de Elo Coberta        : {selected_bots[0]['rating']} até {selected_bots[-1]['rating']} Elo")
    print(" [*] Motor Neural IA            : Neural_Bot (MCTS x200 nós, 100ms duelo ao vivo)")
    print(" [*] Navegador                   : Chromium Headless (Google Chrome Oficial)")
    print(" [*] Modo de Combate             : Neural vs Bot (Melhor de 3, Cor Aleatória)\n")

    manager = TournamentManager(selected_bots)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu-shader-disk-cache"]
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        def on_console(msg):
            if msg.type == "error":
                manager.console_errors.append(msg.text)
                print(f" [!] BROWSER CONSOLE ERROR: {msg.text}")

        def on_page_error(err):
            manager.page_errors.append(str(err))
            print(f" [!!!] UNHANDLED PAGE ERROR: {err}")

        def on_request_failed(req):
            manager.failed_requests.append(f"{req.method} {req.url} -> {req.failure}")
            print(f" [!] REQUEST FAILED: {req.method} {req.url}")

        def on_response(res):
            if res.status >= 400:
                manager.failed_requests.append(f"HTTP {res.status} {res.request.method} {res.url}")
                print(f" [!] HTTP ERROR {res.status}: {res.url}")

        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("requestfailed", on_request_failed)
        page.on("response", on_response)

        print("[*] Carregando a GymArena no Chromium...")
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_selector("#botsListContainer", timeout=20000)

        completed_names = {b["name"] for b in manager.results_by_bot}

        for bot_idx, bot in enumerate(selected_bots, 1):
            bot_name = bot["name"]
            bot_elo = bot["rating"]
            bot_cat = bot["category"]

            if bot_name in completed_names:
                print(f"[*] Pulando {bot_name} ({bot_elo} Elo) - já concluído no checkpoint.")
                continue

            print("\n" + "=" * 65)
            print(f" [SÉRIE {bot_idx}/{len(selected_bots)}] Neural_Bot 3200 vs {bot_name} ({bot_elo} Elo - {bot_cat})")
            print("=" * 65)

            neural_wins = 0
            opp_wins = 0
            draws = 0
            games_data = []
            total_series_duration = 0.0
            total_series_moves = 0

            # Cores para as partidas: J1 aleatório, J2 invertido, J3 aleatório
            first_color = random.choice(["white", "black"])
            colors_sequence = [first_color, "black" if first_color == "white" else "white", random.choice(["white", "black"])]

            for game_num in range(1, 4):
                game_color = colors_sequence[game_num - 1]
                print(f"\n--- Partida {game_num}/3 | Neural jogando de {game_color.upper()} vs {bot_name} ({bot_elo}) ---")

                # Disparar partida via evaluate garantindo configuração nativa
                start_payload = {
                    "mode": "neural_vs_bot",
                    "player_color": game_color,
                    "bot_name": bot_name,
                    "bot_elo": bot_elo,
                    "neural_mode": "mcts",
                    "mcts_sims": 200,
                    "step_delay": 0.01,
                    "auto_play": True,
                }

                start_res = page.evaluate(f"""async () => {{
                    const res = await fetch('/api/match/start', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({json.dumps(start_payload)})
                    }});
                    const data = await res.json();
                    if (window.gymArena) {{
                        window.gymArena.gameState = data.state;
                        window.gymArena.selectedMode = 'neural_vs_bot';
                        window.gymArena.selectedColor = '{game_color}';
                        window.gymArena.selectedSims = 200;
                        window.gymArena.duelSpeed = 10;
                        window.gymArena.setupMatchLayout();
                        window.gymArena.renderBoard();
                        window.gymArena.updateHUD();
                        window.gymArena.startAutoPlay();
                    }}
                    return data;
                }}""")

                if not start_res.get("success"):
                    print(f"[!] Falha ao iniciar partida {game_num}: {start_res}")
                    break

                t0 = time.time()
                game_over = False
                last_move_count = 0
                max_game_duration = 360.0  # 6 minutos de limite por partida

                while time.time() - t0 < max_game_duration:
                    time.sleep(0.5)
                    state = page.evaluate("() => window.gymArena ? window.gymArena.gameState : null")
                    if not state:
                        continue

                    moves = len(state.get("move_history", []))
                    is_over = state.get("is_game_over", False)
                    eval_val = state.get("eval_score", 0.0)

                    if moves != last_move_count and (moves % 5 == 0 or is_over):
                        last_move_count = moves
                        print(f"  [Lance {moves:02d}] Aval: {eval_val:+.2f} | Turno: {state.get('turn')} | Over: {is_over}")

                    if is_over:
                        game_over = True
                        dur = round(time.time() - t0, 1)
                        total_series_duration += dur
                        total_series_moves += moves
                        result = state.get("result", "*")
                        result_desc = state.get("result_desc", "")
                        white = state.get("white_player", {}).get("name", "")
                        black = state.get("black_player", {}).get("name", "")

                        # Determinar vencedor da partida
                        game_winner = None
                        if result == "1-0":
                            game_winner = "Neural_Bot" if game_color == "white" else bot_name
                        elif result == "0-1":
                            game_winner = "Neural_Bot" if game_color == "black" else bot_name
                        else:
                            game_winner = "Empate"

                        if game_winner == "Neural_Bot":
                            neural_wins += 1
                        elif game_winner == "Empate":
                            draws += 1
                        else:
                            opp_wins += 1

                        print(f"  [+] Fim da Partida {game_num}: {result} ({result_desc}) | Vencedor: {game_winner} ({dur}s, {moves} lances)")

                        games_data.append({
                            "game": game_num,
                            "color": game_color,
                            "result": result,
                            "desc": result_desc,
                            "moves": moves,
                            "duration": dur,
                            "winner": game_winner,
                        })
                        break

                if not game_over:
                    print(f"  [!] Partida {game_num} atingiu tempo limite ({max_game_duration}s). Declarando empate técnico.")
                    draws += 1
                    games_data.append({
                        "game": game_num,
                        "color": game_color,
                        "result": "1/2-1/2",
                        "desc": "Limite de tempo excedido",
                        "moves": last_move_count,
                        "duration": max_game_duration,
                        "winner": "Empate",
                    })

                # Verificar se a série Melhor de 3 já está matematicamente decidida
                print(f"  [*] Placar Parcial da Série: Neural_Bot {neural_wins} x {opp_wins} {bot_name} ({draws} Empates)")
                if neural_wins >= 2 or opp_wins >= 2:
                    print(f"  [+] Série MD3 decidida antecipadamente ({neural_wins}x{opp_wins})!")
                    break

            series_winner = "Neural_Bot" if neural_wins > opp_wins else (bot_name if opp_wins > neural_wins else "Empate")
            series_result_entry = {
                "name": bot_name,
                "rating": bot_elo,
                "category": bot_cat,
                "neural_wins": neural_wins,
                "opp_wins": opp_wins,
                "draws": draws,
                "winner": series_winner,
                "games_played": len(games_data),
                "total_moves": total_series_moves,
                "total_duration": total_series_duration,
                "games": games_data,
            }
            manager.results_by_bot.append(series_result_entry)
            manager.update_markdown_report()

        browser.close()

    print("\n" + "=" * 70)
    print("      ♛ TORNEIO GYMARENA CONCLUÍDO COM SUCESSO NO CHROMIUM ♛")
    print("=" * 70)
    print(f" [*] Séries Disputadas         : {len(manager.results_by_bot)}")
    print(f" [*] Total de Partidas         : {sum(b['games_played'] for b in manager.results_by_bot)}")
    print(f" [*] Erros de Console Capturados: {len(manager.console_errors)}")
    print(f" [*] Erros de Página           : {len(manager.page_errors)}")
    print(f" [*] Falhas de Rede HTTP       : {len(manager.failed_requests)}")
    print(f" [*] Relatório Salvo em        : {REPORT_FILE.resolve()}")
    print("=" * 70 + "\n")

    if server_proc:
        server_proc.terminate()


if __name__ == "__main__":
    max_count = None
    tourney_mode = "all_elos"
    for arg in sys.argv[1:]:
        if arg == "--all":
            tourney_mode = "all"
        elif arg == "--fresh":
            if CHECKPOINT_FILE.is_file():
                CHECKPOINT_FILE.unlink()
        elif arg.isdigit():
            max_count = int(arg)
    run_tournament(max_bots=max_count, mode=tourney_mode)
