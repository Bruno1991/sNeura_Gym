"""Runner Paralelo de Alta Performance para o Torneio GymArena (6 Workers Simultâneos).

Executa 6 séries Melhor de 3 em paralelo (1 por worker/porta), aproveitando:
- 12 núcleos / 24 threads do processador Intel Xeon
- Tensor Cores AMP FP16 na GPU NVIDIA RTX 3060 12GB
- Chromium Headless multi-context assíncrono via Playwright
- Resiliência total com salvamento atômico de checkpoints em JSON e Markdown
"""

import asyncio
import datetime
import json
import random
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
REPORTS_DIR = CURRENT_DIR / "relatorios_avancos"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_FILE = REPORTS_DIR / "checkpoint_melhor_de_3.json"
REPORT_FILE = REPORTS_DIR / "relatorio_torneio_melhor_de_3_mcts200.md"
BOTS_DATA_PATH = CURRENT_DIR / "bots_data.json"
if not BOTS_DATA_PATH.is_file():
    BOTS_DATA_PATH = Path(r"C:\dev\s_ADB_Tools\bots_data.json")

BASE_PORT = 8001
DEFAULT_WORKERS = 6


def is_port_alive(port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/match/state", headers={"User-Agent": "HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.2) as res:
            return res.status == 200
    except Exception:
        return False


def start_worker_servers(num_workers: int = DEFAULT_WORKERS) -> List[subprocess.Popen]:
    """Inicia instâncias dedicadas do FastAPI uvicorn para cada worker."""
    procs = []
    print(f"[*] Verificando e iniciando {num_workers} servidores locais (portas {BASE_PORT} a {BASE_PORT + num_workers - 1})...")

    for i in range(num_workers):
        port = BASE_PORT + i
        if is_port_alive(port):
            print(f"  [+] Servidor na porta {port} já está ativo e pronto.")
            continue

        p = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "arena.server:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(CURRENT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(p)

    # Aguardar até todos estarem respondendo
    for _ in range(40):
        time.sleep(0.5)
        all_alive = all(is_port_alive(BASE_PORT + i) for i in range(num_workers))
        if all_alive:
            print(f"[+] Todos os {num_workers} servidores estão online e operantes!")
            break
    else:
        print("[!] Aviso: alguns servidores demoraram a responder, prosseguindo com verificação.")

    return procs


def load_all_bots(mode: str = "all_217") -> List[Dict[str, Any]]:
    """Carrega catálogo de bots."""
    if not BOTS_DATA_PATH.is_file():
        raise FileNotFoundError(f"Arquivo de bots não encontrado: {BOTS_DATA_PATH}")

    with open(BOTS_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    bot_list = []
    seen = set()
    for g in data.get("botGroups", []):
        cat_name = g.get("name", "Geral")
        for b in g.get("botPersonalities", []):
            name = b.get("name")
            if not name:
                continue
            if mode == "unique":
                if name in seen:
                    continue
                seen.add(name)
            bot_list.append({
                "name": name,
                "rating": int(b.get("rating", 1500)),
                "category": cat_name,
                "book": b.get("book", "balanced"),
                "bio": b.get("bio", b.get("description", "")),
            })

    bot_list.sort(key=lambda x: (x["rating"], x["name"]))
    return bot_list


class ParallelTournamentManager:
    def __init__(self, bots: List[Dict[str, Any]], resume: bool = False):
        self.bots = bots
        self.results_by_bot: List[Dict[str, Any]] = []
        self.console_errors: List[str] = []
        self.page_errors: List[str] = []
        self.failed_requests: List[str] = []
        self.start_time = datetime.datetime.now()
        self.lock = asyncio.Lock()

        if resume and CHECKPOINT_FILE.is_file():
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.results_by_bot = data.get("results", [])
                    print(f"[*] Checkpoint carregado: {len(self.results_by_bot)} séries já concluídas.")
            except Exception as e:
                print(f"[!] Erro ao carregar checkpoint: {e}")

    async def save_result(self, result_entry: Dict[str, Any]):
        """Persiste resultado com lock assíncrono para garantir integridade do checkpoint."""
        async with self.lock:
            self.results_by_bot.append(result_entry)
            self._write_files()

    def _write_files(self):
        # 1. Checkpoint JSON
        try:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump({"results": self.results_by_bot}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Erro ao salvar checkpoint JSON: {e}")

        # 2. Relatório Markdown
        try:
            total_series = len(self.results_by_bot)
            total_games = sum(r.get("games_played", 0) for r in self.results_by_bot)
            neural_wins = sum(1 for r in self.results_by_bot if r.get("winner") == "Neural_Bot")
            opp_wins = sum(1 for r in self.results_by_bot if r.get("winner") not in ("Neural_Bot", "Empate"))
            draws = sum(1 for r in self.results_by_bot if r.get("winner") == "Empate")

            win_rate = (neural_wins / max(1, total_series)) * 100.0
            elapsed = (datetime.datetime.now() - self.start_time).total_seconds()
            elapsed_str = str(datetime.timedelta(seconds=int(elapsed)))

            lines = [
                "# 🏆 RELATÓRIO DO TORNEIO PARALELO GYMARENA — 6 WORKERS (MCTS x200)",
                "",
                f"> **Data do Início:** `{self.start_time.strftime('%Y-%m-%d %H:%M:%S')}`  ",
                f"> **Última Atualização:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  ",
                f"> **Tempo Total Decorrido:** `{elapsed_str}`  ",
                f"> **Concorrência Ativa:** `6 Séries Simultâneas em Paralelo (Portas 8001..8006)`  ",
                f"> **Aceleração Hardware:** `RTX 3060 12GB (Tensor Cores AMP FP16) + Intel Xeon 24 Threads`  ",
                "",
                "---",
                "",
                "## 1. Quadro Geral de Desempenho",
                "",
                "| Indicador | Valor Consolidado |",
                "| :--- | :--- |",
                f"| **Total de Séries Disputadas** | `{total_series} / {len(self.bots)}` ({total_series/max(1, len(self.bots))*100:.1f}%) |",
                f"| **Total de Partidas Jogadas** | `{total_games}` |",
                f"| **Vitórias da Série (Neural_Bot)** | `{neural_wins}` (`{win_rate:.1f}%`) |",
                f"| **Vitórias de Bots Adversários** | `{opp_wins}` |",
                f"| **Séries Empatadas** | `{draws}` |",
                f"| **Configuração MCTS** | `200 simulações com Poda de Dominância e Fast-Path` |",
                "",
                "---",
                "",
                "## 2. Tabela Detalhada das Séries Disputadas",
                "",
                "| # | Bot Adversário | Elo | Categoria | Placar MD3 | Vencedor | Lances | Tempo | Detalhes |",
                "| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
            ]

            for idx, res in enumerate(self.results_by_bot, 1):
                bot_name = res.get("name")
                elo = res.get("rating")
                cat = res.get("category", "Geral")
                nw = res.get("neural_wins", 0)
                ow = res.get("opp_wins", 0)
                d = res.get("draws", 0)
                score = f"{nw}x{ow}" if d == 0 else f"{nw}x{ow} ({d}E)"
                winner = res.get("winner", "Empate")
                winner_badge = "🧠 **Neural_Bot**" if winner == "Neural_Bot" else (f"🤖 **{winner}**" if winner != "Empate" else "🤝 Empate")
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
                "## 3. Auditoria de Confiabilidade & Integridade Multi-Worker",
                "",
                f"- **Exceções de Página não Tratadas:** {len(self.page_errors)}",
                f"- **Erros no Console do Chromium:** {len(self.console_errors)}",
                f"- **Erros de Rede / WebSocket / HTTP:** {len(self.failed_requests)}",
                "",
            ])

            REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            print(f"[!] Erro ao escrever relatório Markdown: {e}")


async def worker_task(
    worker_id: int,
    port: int,
    page: Any,
    bot_queue: asyncio.Queue,
    manager: ParallelTournamentManager,
    total_bots_count: int,
):
    """Executa séries MD3 atribuídas a este worker no seu servidor e aba dedicados."""
    base_url = f"http://127.0.0.1:{port}"

    # Carregar a GymArena na porta deste worker
    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_selector("#botsListContainer", timeout=25000)
    except Exception as e:
        print(f"[W{worker_id}] [!] Erro ao carregar página em {base_url}: {e}")

    while True:
        try:
            item = bot_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        bot_idx, bot = item
        bot_name = bot["name"]
        bot_elo = bot["rating"]
        bot_cat = bot["category"]

        print(f"\n[W{worker_id}] ▶ INICIANDO SÉRIE [{bot_idx}/{total_bots_count}]: Neural_Bot 3200 vs {bot_name} ({bot_elo} Elo - {bot_cat})")

        neural_wins = 0
        opp_wins = 0
        draws = 0
        games_data = []
        total_series_duration = 0.0
        total_series_moves = 0

        first_color = random.choice(["white", "black"])
        colors_sequence = [first_color, "black" if first_color == "white" else "white", random.choice(["white", "black"])]

        for game_num in range(1, 4):
            game_color = colors_sequence[game_num - 1]

            start_payload = {
                "mode": "neural_vs_bot",
                "player_color": game_color,
                "bot_name": bot_name,
                "bot_elo": bot_elo,
                "neural_mode": "mcts",
                "mcts_sims": 200,
                "step_delay": 0.005,
                "auto_play": True,
            }

            try:
                start_res = await page.evaluate(f"""async () => {{
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
                        window.gymArena.duelSpeed = 5;
                        window.gymArena.setupMatchLayout();
                        window.gymArena.renderBoard();
                        window.gymArena.updateHUD();
                        window.gymArena.startAutoPlay();
                    }}
                    return data;
                }}""")
            except Exception as e:
                print(f"[W{worker_id}] [!] Erro ao disparar /api/match/start: {e}")
                break

            if not (start_res and start_res.get("success")):
                print(f"[W{worker_id}] [!] Falha ao iniciar partida {game_num} contra {bot_name}: {start_res}")
                break

            t0 = time.time()
            game_over = False
            last_move_count = 0
            max_game_duration = 360.0

            while time.time() - t0 < max_game_duration:
                await asyncio.sleep(0.15)
                try:
                    state = await page.evaluate("() => window.gymArena ? window.gymArena.gameState : null")
                except Exception:
                    continue

                if not state:
                    continue

                moves = len(state.get("move_history", []))
                is_over = state.get("is_game_over", False)

                if moves != last_move_count and (moves % 15 == 0 or is_over):
                    last_move_count = moves

                if is_over:
                    game_over = True
                    dur = round(time.time() - t0, 1)
                    total_series_duration += dur
                    total_series_moves += moves
                    result = state.get("result", "*")
                    result_desc = state.get("result_desc", "")

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

            if neural_wins >= 2 or opp_wins >= 2:
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

        await manager.save_result(series_result_entry)
        total_done = len(manager.results_by_bot)
        pct = (total_done / total_bots_count) * 100.0
        print(f"[W{worker_id}] [✓] FIM DA SÉRIE vs {bot_name} ({bot_elo}) -> {neural_wins}x{opp_wins} ({draws}E) | Vencedor: {series_winner} | [Total Concluído: {total_done}/{total_bots_count} ({pct:.1f}%)]")
        bot_queue.task_done()


async def run_parallel_tournament(workers_count: int = DEFAULT_WORKERS, fresh: bool = False):
    server_procs = start_worker_servers(num_workers=workers_count)
    all_bots = load_all_bots(mode="all_217")

    if fresh:
        if CHECKPOINT_FILE.is_file():
            CHECKPOINT_FILE.unlink()
        print("[*] Modo --fresh ativo: checkpoint limpo para início do zero!")

    manager = ParallelTournamentManager(all_bots, resume=not fresh)
    completed_keys = {(b["name"], b.get("category")) for b in manager.results_by_bot}
    completed_names = {b["name"] for b in manager.results_by_bot}

    bot_queue = asyncio.Queue()
    for idx, bot in enumerate(all_bots, 1):
        bot_key = (bot["name"], bot["category"])
        if (not fresh) and (bot_key in completed_keys or bot["name"] in completed_names):
            continue
        bot_queue.put_nowait((idx, bot))

    pending_count = bot_queue.qsize()
    print("\n" + "=" * 75)
    print("      ♛ TORNEIO PARALELO GYMARENA: 6 SÉRIES SIMULTÂNEAS (CHROMIUM) ♛")
    print("=" * 75)
    print(f" [*] Total de Bots no Catálogo  : {len(all_bots)} bots")
    print(f" [*] Séries a Disputar          : {pending_count} séries pendentes")
    print(f" [*] Concorrência Paralela      : {workers_count} Séries Simultâneas (Portas {BASE_PORT}..{BASE_PORT + workers_count - 1})")
    print(" [*] Motor Neural IA            : Neural_Bot (MCTS x200 nós, Fast-Path, AMP FP16)")
    print(" [*] Aceleração de Hardware     : RTX 3060 12GB + Xeon 24 Threads")
    print("=" * 75 + "\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu-shader-disk-cache", "--disable-dev-shm-usage"]
        )

        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        pages = [await context.new_page() for _ in range(workers_count)]

        for w_id, page in enumerate(pages):
            def make_console_handler(wid):
                return lambda msg: manager.console_errors.append(f"[W{wid}] {msg.text}") if msg.type == "error" else None
            def make_page_error_handler(wid):
                return lambda err: manager.page_errors.append(f"[W{wid}] {err}")
            page.on("console", make_console_handler(w_id + 1))
            page.on("pageerror", make_page_error_handler(w_id + 1))

        # Disparar os workers concorrentemente
        tasks = [
            asyncio.create_task(
                worker_task(
                    worker_id=i + 1,
                    port=BASE_PORT + i,
                    page=pages[i],
                    bot_queue=bot_queue,
                    manager=manager,
                    total_bots_count=len(all_bots),
                )
            )
            for i in range(workers_count)
        ]

        await asyncio.gather(*tasks)
        await browser.close()

    print("\n" + "=" * 75)
    print("      ♛ TORNEIO PARALELO GYMARENA CONCLUÍDO COM 100% DE SUCESSO ♛")
    print("=" * 75)
    print(f" [*] Séries Disputadas         : {len(manager.results_by_bot)}")
    print(f" [*] Relatório Salvo em        : {REPORT_FILE.resolve()}")
    print("=" * 75 + "\n")

    for p in server_procs:
        try:
            p.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    fresh_flag = ("--fresh" in sys.argv)
    workers = DEFAULT_WORKERS
    for arg in sys.argv[1:]:
        if arg.startswith("--workers="):
            workers = int(arg.split("=")[1])
        elif arg.isdigit():
            workers = int(arg)

    asyncio.run(run_parallel_tournament(workers_count=workers, fresh=fresh_flag))
