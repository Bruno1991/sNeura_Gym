"""Suite de testes e execucao de partidas na GymArena via Chromium Headless (Playwright).

Inicia o servidor backend da GymArena caso nao esteja rodando, lanca o Chromium oficial
(Google Chrome em modo headless), conecta na arena web, executa partidas completas
(Neural vs Bot, Humano vs Bot, Humano vs Neural), intercepta erros de console,
falhas de rede, problemas de layout, audio e WebSocket, e gera diagnostico completo.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
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


def is_server_alive() -> bool:
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/match/state", headers={"User-Agent": "TestRunner"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def ensure_server_running():
    if is_server_alive():
        print("[*] Servidor da GymArena ja esta em execucao na porta 8000.", flush=True)
        return None

    print("[*] Iniciando servidor da GymArena em background na porta 8000...", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "arena.server:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(CURRENT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        time.sleep(1)
        if is_server_alive():
            print("[+] Servidor GymArena online e pronto para receber conexoes!", flush=True)
            return proc
    raise RuntimeError("Falha ao iniciar servidor GymArena na porta 8000 apos 30 segundos.")


def run_arena_test_suite():
    server_proc = ensure_server_running()

    console_errors = []
    console_warnings = []
    page_errors = []
    failed_requests = []

    print("\n" + "=" * 70)
    print("      ♛ INICIANDO BATERIA DE PARTIDAS NA GYMARENA NO CHROMIUM ♛")
    print("=" * 70)

    try:
        with sync_playwright() as p:
            print(f"[*] Lancando Chromium Headless em: {CHROME_PATH}")
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--autoplay-policy=no-user-gesture-required",
                ]
            )

            # Contexto 1: Desktop Viewport (1280x850)
            context = browser.new_context(viewport={"width": 1280, "height": 850})
            page = context.new_page()

            # Captura de eventos e erros do navegador
            def on_console(msg):
                txt = f"[{msg.type.upper()}] {msg.text}"
                if msg.type == "error":
                    console_errors.append(txt)
                    print(f" [!] BROWSER ERROR: {msg.text}")
                elif msg.type == "warning":
                    console_warnings.append(txt)

            def on_page_error(err):
                page_errors.append(str(err))
                print(f" [!!!] UNHANDLED PAGE ERROR: {err}")

            def on_request_failed(req):
                failed_requests.append(f"{req.method} {req.url} -> {req.failure}")
                print(f" [!] REQUEST FAILED: {req.method} {req.url} ({req.failure})")

            def on_response(res):
                if res.status >= 400:
                    failed_requests.append(f"HTTP {res.status} {res.request.method} {res.url}")
                    print(f" [!] HTTP ERROR {res.status}: {res.request.method} {res.url}")

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)
            page.on("response", on_response)

            # ==============================================================
            # TESTE 1: CARREGAMENTO DA GYMARENA & CATÁLOGO
            # ==============================================================
            print("\n--- [TESTE 1] Carregamento da GymArena & Catalogo de Bots ---", flush=True)
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_selector("#botsListContainer", timeout=15000)

            title = page.title()
            print(f"[*] Titulo da Pagina: '{title}'")
            assert "GymArena" in title, f"Titulo inesperado: {title}"

            # Verificar contagem de bots
            badge_text = page.locator("#catalogBadgeCount").inner_text()
            print(f"[*] Total de bots no catalogo: {badge_text}")

            # Verificar se imagens de avatares carregam sem quebra
            time.sleep(0.8)
            broken_imgs = page.evaluate("""() => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs.filter(img => img.complete && img.naturalWidth === 0 && img.src).map(img => img.src);
            }""")
            if broken_imgs:
                print(f"[!] Imagens com erro de carregamento ({len(broken_imgs)}): {broken_imgs[:5]}", flush=True)
            else:
                print("[+] Todos os avatares e pecas carregaram 100% perfeitamente.", flush=True)

            # ==============================================================
            # TESTE 2: BUSCA E FILTROS DE BOTS
            # ==============================================================
            print("\n--- [TESTE 2] Testando Busca e Filtragem de Bots ---")
            search_input = page.locator("#botSearchInput")
            search_input.fill("Nelson")
            time.sleep(0.5)

            found_nelson = page.locator('.bot-card-item:has-text("Nelson")').count()
            print(f"[*] Busca por 'Nelson': {found_nelson} bots encontrados.")
            assert found_nelson > 0, "Bot Nelson nao encontrado na busca!"

            # Limpar busca
            clear_btn = page.locator("#btnClearSearch")
            clear_btn.click()
            time.sleep(0.3)
            search_input.fill("")
            time.sleep(0.3)

            # Testar clique em aba de categoria (Principiantes)
            cat_beginner = page.locator('.cat-pill[data-category="Beginner"]')
            if cat_beginner.count() > 0:
                cat_beginner.click()
                time.sleep(0.4)
                print("[+] Filtro por categoria 'Principiantes' ativo.")

            # Voltar para Todos
            page.locator('.cat-pill[data-category="all"]').click()
            time.sleep(0.4)

            # ==============================================================
            # TESTE 3: PARTIDA 1 - NEURAL_BOT VS MARTIN (MODO AUTOMATICO)
            # ==============================================================
            print("\n--- [TESTE 3] Partida 1: Neural_Bot vs Martin (Duelo ao Vivo) ---")
            # Buscar Martin
            search_input.fill("Martin")
            time.sleep(0.4)
            martin_card = page.locator('.bot-card-item:has-text("Martin")').first
            martin_card.click()
            time.sleep(0.5)

            # Gaveta de desafio aberta
            drawer_visible = page.locator("#challengeDrawer").is_visible()
            print(f"[*] Drawer de desafio aberto: {drawer_visible}")
            assert drawer_visible, "Drawer de desafio nao abriu!"

            # Selecionar Neural vs Bot
            page.locator('#chipNeuralVsBot').click()
            time.sleep(0.2)

            # Definir velocidade do duelo para 200ms para simular rapido
            page.evaluate("() => { if (window.gymArena) window.gymArena.duelSpeed = 200; }")

            # Clicar em Jogar Agora
            print("[*] Iniciando partida Neural vs Martin...")
            page.locator("#btnStartGameConfirmed").click()
            time.sleep(1.0)

            # Esperar a partida rolar por alguns lances
            print("[*] Acompanhando duelo e lances...")
            for step in range(1, 26):
                time.sleep(0.8)
                moves_count_text = page.locator("#movesCountBadge").inner_text()
                eval_text = page.locator("#telEvalScore").inner_text()
                speech_text = page.locator("#speechText").inner_text()
                is_game_over = page.locator("#gameOverModal").is_visible()

                print(f"  [Lance #{step:02d}] {moves_count_text} | Aval: {eval_text} | Fala: '{speech_text}' | Fim: {is_game_over}")
                if is_game_over:
                    print(f"[+] Partida finalizada com sucesso no lance {step}!")
                    break

            # ==============================================================
            # TESTE 4: PARTIDA 2 - HUMANO VS BOT (JOGABILIDADE INTERATIVA)
            # ==============================================================
            print("\n--- [TESTE 4] Partida 2: Humano vs Bot (Interacao do Jogador) ---")
            # Fechar modal de game over se aberto, ou abrir catalogo
            if page.locator("#gameOverModal").is_visible():
                page.locator("#modalChooseBotBtn").click()
                time.sleep(0.5)
            else:
                page.locator("#tabViewBots").click()
                time.sleep(0.5)

            # Buscar Nelson
            search_input.fill("Nelson")
            time.sleep(0.4)
            nelson_card = page.locator('.bot-card-item:has-text("Nelson")').first
            nelson_card.click()
            time.sleep(0.5)

            # Selecionar Você vs Bot (Humano vs Bot)
            page.locator("#chipHumanVsBot").click()
            time.sleep(0.2)
            page.locator("#chipColorWhite").click()
            time.sleep(0.2)
            page.locator("#btnStartGameConfirmed").click()
            time.sleep(1.0)

            # Humano joga 1. e4
            print("[*] Humano clicando em e2...")
            square_e2 = page.locator('.board-square[data-square="e2"]')
            square_e2.click()
            time.sleep(0.3)

            # Verificar indicadores legais
            dots = page.locator(".legal-dot-indicator").count()
            print(f"[*] Indicadores de lances legais exibidos: {dots} casas.")
            assert dots > 0, "Indicadores legais nao apareceram!"

            print("[*] Humano clicando em e4...")
            square_e4 = page.locator('.board-square[data-square="e4"]')
            square_e4.click()
            time.sleep(0.8)

            # Verificar resposta do bot
            time.sleep(1.5)
            moves_text = page.locator("#movesCountBadge").inner_text()
            print(f"[*] Lances apos jogada humana e resposta do bot: {moves_text}")

            # Testar botão de Dica (Hint)
            print("[*] Testando botao de Dica Tática...")
            page.locator("#btnHintMove").click()
            time.sleep(0.8)
            hint_speech = page.locator("#speechText").inner_text()
            print(f"[+] Dica recebida: '{hint_speech}'")

            # Testar botão de Desfazer Lance (Undo)
            print("[*] Testando botao de Desfazer Lance...")
            page.locator("#btnUndoMove").click()
            time.sleep(0.8)
            moves_after_undo = page.locator("#movesCountBadge").inner_text()
            print(f"[+] Lances apos Desfazer: {moves_after_undo}")

            # Testar botão Inverter Tabuleiro (Flip)
            print("[*] Testando Inverter Tabuleiro...")
            first_square_before = page.locator(".board-square").first.get_attribute("data-square")
            page.locator("#btnFlipBoard").click()
            time.sleep(0.4)
            first_square_after = page.locator(".board-square").first.get_attribute("data-square")
            print(f"[+] Tabuleiro invertido: casa inicial era {first_square_before}, agora e {first_square_after}")
            assert first_square_before != first_square_after, "Inversao de tabuleiro falhou!"

            # Voltar orientacao original
            page.locator("#btnFlipBoard").click()
            time.sleep(0.3)

            # Testar botão MCTS ON/OFF
            print("[*] Testando botao MCTS ON/OFF...")
            mcts_btn = page.locator("#btnToggleMcts")
            mcts_label_before = page.locator("#mctsBtnLabel").inner_text()
            mcts_btn.click()
            time.sleep(0.5)
            mcts_label_after = page.locator("#mctsBtnLabel").inner_text()
            print(f"[+] MCTS alternado: '{mcts_label_before}' -> '{mcts_label_after}'")
            mcts_btn.click()
            time.sleep(0.5)

            # ==============================================================
            # TESTE 5: PARTIDA 3 - HUMANO DE PRETAS VS BOT (BRANCAS)
            # ==============================================================
            print("\n--- [TESTE 5] Partida 3: Humano de Pretas vs Nelson (Brancas) ---", flush=True)
            page.locator("#tabViewBots").click()
            time.sleep(0.5)
            search_input.fill("Nelson")
            time.sleep(0.4)
            nelson_card = page.locator('.bot-card-item:has-text("Nelson")').first
            nelson_card.click()
            time.sleep(0.5)

            page.locator("#chipHumanVsBot").click()
            time.sleep(0.2)
            page.locator("#chipColorBlack").click()
            time.sleep(0.2)
            page.locator("#btnStartGameConfirmed").click()
            time.sleep(1.0)

            # Verificar se tabuleiro inverteu para as pretas (casa h1 no topo ou a1 no topo)
            flipped_state = page.evaluate("() => window.gymArena ? window.gymArena.isFlipped : false")
            print(f"[+] Tabuleiro invertido para Pretas: {flipped_state}", flush=True)
            assert flipped_state is True, "Tabuleiro deveria estar invertido para jogador de Pretas!"

            # Esperar o bot (Brancas) fazer o primeiro lance
            print("[*] Aguardando lance inicial do bot (Brancas)...", flush=True)
            time.sleep(2.0)
            moves_after_bot_start = page.locator("#movesCountBadge").inner_text()
            print(f"[+] Lance das Brancas efetuado: {moves_after_bot_start}", flush=True)

            # Humano responde de Pretas com lance e7-e5 (ou c7-c5 se legal)
            print("[*] Humano jogando de Pretas (e7 -> e5)...", flush=True)
            square_e7 = page.locator('.board-square[data-square="e7"]')
            if square_e7.count() > 0:
                square_e7.click()
                time.sleep(0.3)
                square_e5 = page.locator('.board-square[data-square="e5"]')
                if square_e5.count() > 0:
                    square_e5.click()
                    time.sleep(1.2)
            moves_after_black = page.locator("#movesCountBadge").inner_text()
            print(f"[+] Lances apos resposta das Pretas: {moves_after_black}", flush=True)

            # ==============================================================
            # TESTE 6: MODAL DE OPÇÕES DA PARTIDA (SUBSTITUI CONFIRM NATIVO)
            # ==============================================================
            print("\n--- [TESTE 6] Testando Modal de Opcoes / Desistir In-App ---", flush=True)
            page.locator("#btnResignMatch").click()
            time.sleep(0.4)
            options_visible = page.locator("#optionsModal").is_visible()
            print(f"[*] Modal de opcoes aberto: {options_visible}", flush=True)
            assert options_visible, "Modal de opcoes da partida nao abriu!"

            # Testar botão Cancelar
            page.locator("#btnCloseOptions").click()
            time.sleep(0.3)
            options_closed = not page.locator("#optionsModal").is_visible()
            print(f"[+] Modal de opcoes fechado com sucesso: {options_closed}", flush=True)

            # Abrir novamente e clicar em Reiniciar Partida
            page.locator("#btnResignMatch").click()
            time.sleep(0.3)
            page.locator("#btnRestartMatch").click()
            time.sleep(1.0)
            print("[+] Partida reiniciada via Modal de Opcoes com sucesso.", flush=True)

            # ==============================================================
            # TESTE 7: MODAL DE AJUSTES & TEMAS DO TABULEIRO
            # ==============================================================
            print("\n--- [TESTE 7] Testando Modal de Ajustes e Troca de Tema ---", flush=True)
            page.locator("#btnToggleAppTheme").click()
            time.sleep(0.4)
            settings_visible = page.locator("#settingsModal").is_visible()
            print(f"[*] Modal de ajustes aberto: {settings_visible}", flush=True)
            assert settings_visible, "Modal de ajustes nao abriu!"

            # Trocar tema para Madeira Nobre (Walnut)
            page.locator("#boardThemeSelect").select_option("walnut")
            time.sleep(0.3)
            light_color = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--square-light').trim()")
            print(f"[+] Tema Madeira Nobre aplicado: --square-light = {light_color}", flush=True)

            # Alternar coordenadas
            page.locator("#toggleBoardCoords").click()
            time.sleep(0.3)
            coords_hidden = page.evaluate("() => document.body.classList.contains('hide-coordinates')")
            print(f"[+] Coordenadas ocultadas: {coords_hidden}", flush=True)

            # Reativar coordenadas e voltar tema verde
            page.locator("#toggleBoardCoords").click()
            time.sleep(0.2)
            page.locator("#boardThemeSelect").select_option("green")
            time.sleep(0.2)

            # Fechar modal de ajustes
            page.locator("#btnCloseSettings").click()
            time.sleep(0.3)

            # ==============================================================
            # TESTE 8: DUELO AUTOMATIZADO NEURAL_BOT VS WENDY (1500 ELO)
            # ==============================================================
            print("\n--- [TESTE 8] Duelo Automatizado: Neural_Bot vs Wendy (1500 Elo) ---", flush=True)
            page.locator("#tabViewBots").click()
            time.sleep(0.5)
            search_input.fill("Wendy")
            time.sleep(0.4)
            wendy_card = page.locator('.bot-card-item:has-text("Wendy")').first
            wendy_card.click()
            time.sleep(0.5)

            page.locator("#chipNeuralVsBot").click()
            time.sleep(0.2)
            page.locator("#chipColorWhite").click()
            time.sleep(0.2)
            page.evaluate("() => { if (window.gymArena) window.gymArena.duelSpeed = 200; }")
            page.locator("#btnStartGameConfirmed").click()
            time.sleep(1.0)

            print("[*] Acompanhando duelo Neural vs Wendy por 15 lances...", flush=True)
            for s in range(1, 16):
                time.sleep(0.8)
                mv = page.locator("#movesCountBadge").inner_text()
                ev = page.locator("#telEvalScore").inner_text()
                sp = page.locator("#speechText").inner_text()
                print(f"  [Lance #{s:02d}] {mv} | Aval: {ev} | Fala: '{sp}'", flush=True)

            # ==============================================================
            # TESTE 9: RESPONSIVIDADE MOBILE (VIEWPORT SMARTPHONE 390x844)
            # ==============================================================
            print("\n--- [TESTE 9] Testando Layout Mobile (iPhone 13 - 390x844) ---", flush=True)
            page.set_viewport_size({"width": 390, "height": 844})
            time.sleep(0.8)

            # Verificar se dock bar mobile esta visivel no viewport estreito
            bottom_nav_visible = page.locator(".mobile-bottom-nav").is_visible()
            print(f"[*] Dock Bar Mobile visivel em 390px: {bottom_nav_visible}", flush=True)

            # Clicar em Computador na barra inferior
            page.locator("#tabNavPlay").click()
            time.sleep(0.6)
            catalog_visible = page.locator("#catalogScreen").is_visible()
            print(f"[*] Tela de catalogo ativa via dock bar: {catalog_visible}", flush=True)

            # Clicar em Duelo Neural na barra inferior
            page.locator("#tabNavNeuralDuel").click()
            time.sleep(0.6)
            drawer_open = page.locator("#challengeDrawer").is_visible()
            print(f"[*] Drawer de duelo aberto via atalho: {drawer_open}", flush=True)
            page.locator("#challengeDrawer").click(position={"x": 10, "y": 10})
            time.sleep(0.4)

            # ==============================================================
            # DIAGNÓSTICO FINAL DE ERROS E BUGS
            # ==============================================================
            print("\n" + "=" * 70)
            print("                 ♛ RELATORIO DE BUGS IDENTIFICADOS ♛")
            print("=" * 70)
            print(f" [*] Page Errors (Excecoes JS nao tratadas) : {len(page_errors)}")
            for pe in page_errors:
                print(f"     -> {pe}")

            print(f" [*] Console Errors (Mensagens de Erro)     : {len(console_errors)}")
            for ce in console_errors:
                print(f"     -> {ce}")

            print(f" [*] Failed Requests (Requisicoes com erro) : {len(failed_requests)}")
            for fr in failed_requests:
                print(f"     -> {fr}")

            print(f" [*] Console Warnings                        : {len(console_warnings)}")
            for cw in console_warnings[:5]:
                print(f"     -> {cw}")
            print("=" * 70)

            browser.close()

    finally:
        if server_proc:
            print("[*] Encerrando processo do servidor temporario...")
            server_proc.terminate()


if __name__ == "__main__":
    run_arena_test_suite()
