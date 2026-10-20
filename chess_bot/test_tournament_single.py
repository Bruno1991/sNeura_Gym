"""Teste de validação de 1 série Melhor de 3 no Chromium headless com GymArena."""

import asyncio
import os
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

CURRENT_DIR = Path(__file__).resolve().parent
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000"

def is_server_alive() -> bool:
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/match/state", headers={"User-Agent": "TestRunner"})
        with urllib.request.urlopen(req, timeout=1.5) as res:
            return res.status == 200
    except Exception:
        return False

def test_single_series():
    import subprocess
    server_proc = None
    if not is_server_alive():
        print("[*] Iniciando GymArena server...")
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "arena.server:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(CURRENT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        for _ in range(30):
            time.sleep(0.5)
            if is_server_alive():
                print("[+] Servidor GymArena online!")
                break

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu-shader-disk-cache"]
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        console_errors = []
        page_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        print("[*] Conectando na GymArena...")
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_selector("#botsListContainer", timeout=15000)

        # Configurar parâmetros via API da janela
        page.evaluate("""() => {
            if (window.gymArena) {
                window.gymArena.selectedMode = 'neural_vs_bot';
                window.gymArena.selectedSims = 200;
                window.gymArena.mctsActive = true;
                window.gymArena.duelSpeed = 100;
            }
        }""")

        bot_name = "Martin"
        bot_elo = 250
        print(f"[*] Testando Melhor de 3 contra {bot_name} ({bot_elo} Elo)...")

        series_results = []
        for game_num in range(1, 4):
            # Escolher cor aleatória
            import random
            color = random.choice(["white", "black"])
            print(f"\n--- Partida {game_num}/3 (Neural jogando de {color.upper()}) ---")

            start_res = page.evaluate(f"""async () => {{
                const res = await fetch('/api/match/start', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        mode: 'neural_vs_bot',
                        player_color: '{color}',
                        bot_name: '{bot_name}',
                        bot_elo: {bot_elo},
                        neural_mode: 'mcts',
                        mcts_sims: 200,
                        step_delay: 0.1,
                        auto_play: true
                    }})
                }});
                const data = await res.json();
                if (window.gymArena) {{
                    window.gymArena.gameState = data.state;
                    window.gymArena.selectedMode = 'neural_vs_bot';
                    window.gymArena.selectedColor = '{color}';
                    window.gymArena.selectedSims = 200;
                    window.gymArena.duelSpeed = 100;
                    window.gymArena.setupMatchLayout();
                    window.gymArena.renderBoard();
                    window.gymArena.updateHUD();
                    window.gymArena.startAutoPlay();
                }}
                return data;
            }}""")

            print(f"[*] Partida iniciada: success={start_res.get('success')}")

            # Acompanhar até o fim da partida
            t0 = time.time()
            game_over = False
            last_move_count = 0
            
            while time.time() - t0 < 180:  # timeout 3 minutos por partida
                time.sleep(1.0)
                state = page.evaluate("() => window.gymArena ? window.gymArena.gameState : null")
                if not state:
                    continue

                moves = len(state.get("move_history", []))
                is_over = state.get("is_game_over", False)
                eval_val = state.get("eval_score", 0.0)

                if moves != last_move_count:
                    last_move_count = moves
                    print(f"  [Lance {moves:02d}] Aval: {eval_val:+.2f} | Turno: {state.get('turn')} | Over: {is_over}")

                if is_over:
                    game_over = True
                    result = state.get("result", "*")
                    result_desc = state.get("result_desc", "")
                    white = state.get("white_player", {}).get("name", "")
                    black = state.get("black_player", {}).get("name", "")
                    print(f"[+] Partida {game_num} Finalizada! Resultado: {result} ({result_desc}) | {white} vs {black}")
                    series_results.append({
                        "game": game_num,
                        "color": color,
                        "moves": moves,
                        "result": result,
                        "desc": result_desc,
                        "duration": round(time.time() - t0, 1)
                    })
                    break

            if not game_over:
                print(f"[!] Partida {game_num} atingiu timeout.")
                break

            # Se um jogador já ganhou 2 partidas, série decidida!
            neural_wins = sum(1 for r in series_results if (r["color"] == "white" and r["result"] == "1-0") or (r["color"] == "black" and r["result"] == "0-1"))
            opp_wins = sum(1 for r in series_results if (r["color"] == "white" and r["result"] == "0-1") or (r["color"] == "black" and r["result"] == "1-0"))
            print(f"[*] Placar da Série: Neural {neural_wins} x {opp_wins} {bot_name}")
            if neural_wins >= 2 or opp_wins >= 2:
                print(f"[+] Série Melhor de 3 concluída antecipadamente ({neural_wins}x{opp_wins})!")
                break

        browser.close()
        print("\n" + "="*50)
        print(f"Console Errors: {len(console_errors)}")
        print(f"Page Errors: {len(page_errors)}")
        print("="*50)

    if server_proc:
        server_proc.terminate()

if __name__ == "__main__":
    test_single_series()
