"""Canivete Suíço Universal do Xadrez (s_Neura_Gym - chess_bot).

Interface unificada e centralizada de controle com terminal Rich para:
- [1] Iniciar servidor local da GymArena Mobile Web (FastAPI + WebSocket na porta 8000)
- [2] Executar Torneio MD3 Oficial contra os 217 bots do Chess.com (Modo 30x Acelerado)
- [3] Executar Bateria de 1.000 partidas de Self-Play (Neura Bot vs Neura Bot com PGN)
- [4] Treinamento e Ajuste Fino Neural da SE-ResNet na GPU RTX 3060 com AMP FP16
- [5] Executar Pipeline Master Completo Automatizado com sincronização Git
- [6] Jogar Duelo Interativo no terminal contra qualquer bot oficial com livro Polyglot
- [7] Consultar e filtrar o catálogo completo dos 217 bots oficiais do Chess.com
- [8] Acompanhar status, telemetria, checkpoints e relatórios em tempo real
- [9] Avaliação neural profunda de posição FEN com SE-ResNet e MCTS
- [10] Executar suíte de testes automatizados com pytest
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Suporte UTF-8 no terminal Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
NEURAL_DIR = CURRENT_DIR / "Neural_Bot"
SCRIPTED_DIR = CURRENT_DIR / "Scripted_Bot"
REPORTS_DIR = CURRENT_DIR / "relatorios_avancos"
CHECKPOINTS_DIR = NEURAL_DIR / "checkpoints"
BOOKS_DIR = CURRENT_DIR / "books"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(NEURAL_DIR))
sys.path.insert(0, str(SCRIPTED_DIR))

WEIGHTS_PATH = CHECKPOINTS_DIR / "chess_policy_weights.pt"
ONNX_PATH = CHECKPOINTS_DIR / "chess_policy_weights.onnx"
BOTS_DATA_FILE = CURRENT_DIR / "bots_data.json"
CHECKPOINT_TOURNAMENT = REPORTS_DIR / "checkpoint_melhor_de_3.json"
CHECKPOINT_SELFPLAY = REPORTS_DIR / "checkpoint_bateria_1000_selfplay.json"

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from runners.catalog import ChessBotsManager, play_interactive_game, print_bot_detail
from runners.pipeline import run_full_pipeline
from runners.selfplay import run_selfplay
from runners.tournament import run_tournament
from runners.train import train_pipeline

console = Console()


# ==============================================================================
# BANNERS & APRESENTAÇÃO
# ==============================================================================
def print_banner():
    """Exibe o cabeçalho Rich estilizado do Canivete Suíço."""
    title_text = Text()
    title_text.append("♚ ♛ ♜ ♝ ♞ ♟   ", style="bold gold1")
    title_text.append("S_NEURA_GYM: CANIVETE SUÍÇO DO CHESS_BOT", style="bold bright_white")
    title_text.append("   ♟ ♞ ♝ ♜ ♛ ♚\n", style="bold gold1")
    title_text.append(
        "Motor Neural SE-ResNet (128c x 4b) • MCTS Híbrido • PVS Blunder Guard • Catálogo 217 Bots Oficiais\n",
        style="italic cyan",
    )
    title_text.append("Aceleração NVIDIA GeForce RTX 3060 (PyTorch AMP FP16) • GymArena Mobile Web", style="dim white")

    p = Panel(
        Align.center(title_text),
        box=box.DOUBLE,
        border_style="bright_blue",
        padding=(0, 2),
    )
    console.print(p)


# ==============================================================================
# 1. GYMARENA WEB SERVER
# ==============================================================================
def start_arena(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Inicia o servidor web da GymArena Mobile."""
    console.print("\n[bold green]>>> INICIANDO SERVIDOR WEB LOCAL GYMARENA MOBILE <<<[/bold green]")
    t = Table(box=box.ROUNDED, border_style="cyan")
    t.add_column("Parâmetro", style="bold white")
    t.add_column("Configuração", style="yellow")
    t.add_row("Endereço Local", f"http://localhost:{port}")
    t.add_row("Endereço da Rede", f"http://{host}:{port}")
    t.add_row("Peças Vetoriais", "cburnett SVG (Oficiais do Lichess)")
    t.add_row("Bots Integrados", "217 Bots Oficiais Chess.com + Neura Bot")
    t.add_row("Encerrar Servidor", "Pressione CTRL+C no terminal")
    console.print(t)

    import uvicorn
    if reload:
        uvicorn.run("arena.server:app", host=host, port=port, reload=True, reload_dirs=[str(CURRENT_DIR / "arena")], app_dir=str(CURRENT_DIR))
    else:
        uvicorn.run("arena.server:app", host=host, port=port, reload=False, app_dir=str(CURRENT_DIR))


# ==============================================================================
# 2. STATUS & DASHBOARD
# ==============================================================================
def show_dashboard():
    """Exibe painel consolidado com status do modelo, torneio, selfplay e relatórios."""
    console.print("\n[bold gold1]═══════════════════════════════════════════════════════════════════════[/bold gold1]")
    console.print("[bold bright_white]                📊 DASHBOARD E TELEMETRIA DO SISTEMA 📊[/bold bright_white]")
    console.print("[bold gold1]═══════════════════════════════════════════════════════════════════════[/bold gold1]\n")

    # 1. Status do Modelo Neural
    model_table = Table(title="🧠 Modelo Neural & Pesos", box=box.ROUNDED, border_style="magenta")
    model_table.add_column("Arquivo", style="bold white")
    model_table.add_column("Status", style="cyan")
    model_table.add_column("Tamanho", style="yellow")
    model_table.add_column("Última Modificação", style="green")

    if WEIGHTS_PATH.is_file():
        stat = WEIGHTS_PATH.stat()
        mod_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        model_table.add_row("chess_policy_weights.pt", "✓ Pronto / Atualizado", f"{stat.st_size/(1024*1024):.2f} MB", mod_time)
    else:
        model_table.add_row("chess_policy_weights.pt", "✗ Não encontrado", "-", "-")

    if ONNX_PATH.is_file():
        stat = ONNX_PATH.stat()
        mod_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        model_table.add_row("chess_policy_weights.onnx", "✓ Exportado", f"{stat.st_size/(1024*1024):.2f} MB", mod_time)
    else:
        model_table.add_row("chess_policy_weights.onnx", "✗ Não exportado", "-", "-")

    dataset_p = CHECKPOINTS_DIR / "dataset_selfplay_1000_combined.pt"
    if dataset_p.is_file():
        stat = dataset_p.stat()
        mod_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        model_table.add_row("dataset_selfplay_1000_combined.pt", "✓ Cache de Tensores", f"{stat.st_size/(1024*1024):.2f} MB", mod_time)

    console.print(model_table)

    # 2. Status do Torneio MD3 (217 Bots)
    tourn_table = Table(title="🏆 Torneio MD3 Oficial (GymArena vs 217 Bots)", box=box.ROUNDED, border_style="blue")
    tourn_table.add_column("Métrica", style="bold white")
    tourn_table.add_column("Valor", style="bright_yellow")
    tourn_table.add_column("Detalhes", style="cyan")

    if CHECKPOINT_TOURNAMENT.is_file():
        try:
            with open(CHECKPOINT_TOURNAMENT, "r", encoding="utf-8") as f:
                data = json.load(f)
            res = data.get("results", [])
            total_done = len(res)
            w_series = sum(1 for r in res if r.get("winner") == "Neural_Bot")
            l_series = sum(1 for r in res if r.get("winner") not in ("Neural_Bot", "Empate"))
            d_series = sum(1 for r in res if r.get("winner") == "Empate")

            w_games = sum(r.get("neural_wins", 0) for r in res)
            l_games = sum(r.get("opp_wins", 0) for r in res)
            d_games = sum(r.get("draws", 0) for r in res)
            tot_games = w_games + l_games + d_games

            tourn_table.add_row("Séries Disputadas", f"{total_done} / 217", f"{(total_done/217)*100:.1f}% concluído")
            tourn_table.add_row("Vitórias em Séries MD3", f"{w_series} vitórias", f"Taxa de Vitória: {(w_series/max(1,total_done))*100:.1f}%")
            tourn_table.add_row("Derrotas em Séries MD3", f"{l_series} derrotas", f"Taxa de Derrota: {(l_series/max(1,total_done))*100:.1f}%")
            tourn_table.add_row("Séries Empatadas", f"{d_series} empates", f"Taxa de Empate: {(d_series/max(1,total_done))*100:.1f}%")
            tourn_table.add_row("Total de Partidas Jogadas", f"{tot_games} partidas", f"{w_games}V - {d_games}E - {l_games}D")
        except Exception as e:
            tourn_table.add_row("Erro de Leitura", str(e), "-")
    else:
        tourn_table.add_row("Status", "Nenhum torneio registrado", "Execute a opção 2 para iniciar")

    console.print(tourn_table)

    # 3. Status da Bateria Self-Play
    sp_table = Table(title="♟️ Bateria de Self-Play (Neura Bot vs Neura Bot)", box=box.ROUNDED, border_style="green")
    sp_table.add_column("Métrica", style="bold white")
    sp_table.add_column("Valor", style="bright_yellow")
    sp_table.add_column("Detalhes", style="cyan")

    if CHECKPOINT_SELFPLAY.is_file():
        try:
            with open(CHECKPOINT_SELFPLAY, "r", encoding="utf-8") as f:
                data = json.load(f)
            sp_res = data.get("results", [])
            sp_tot = len(sp_res)
            w_w = sum(1 for r in sp_res if r.get("result") == "1-0")
            b_w = sum(1 for r in sp_res if r.get("result") == "0-1")
            dr = sum(1 for r in sp_res if r.get("result") in ("1/2-1/2", "*"))

            sp_table.add_row("Partidas Concluídas", f"{sp_tot:,} partidas", f"100% da bateria oficial" if sp_tot >= 1000 else f"Meta: 1000")
            sp_table.add_row("Vitórias das Brancas", f"{w_w} ({(w_w/max(1,sp_tot))*100:.1f}%)", "Vantagem de saída")
            sp_table.add_row("Vitórias das Pretas", f"{b_w} ({(b_w/max(1,sp_tot))*100:.1f}%)", "Contra-ataques decisivos")
            sp_table.add_row("Empates", f"{dr} ({(dr/max(1,sp_tot))*100:.1f}%)", "Regras oficiais / 50 lances")

            pgn_file = REPORTS_DIR / "selfplay_1000_games.pgn"
            if pgn_file.is_file():
                pgn_mb = pgn_file.stat().st_size / (1024 * 1024)
                sp_table.add_row("Arquivo PGN", pgn_file.name, f"{pgn_mb:.2f} MB armazenados")
        except Exception as e:
            sp_table.add_row("Erro de Leitura", str(e), "-")
    else:
        sp_table.add_row("Status", "Nenhuma bateria registrada", "Execute a opção 3 para iniciar")

    console.print(sp_table)

    # 4. Documentos e Relatórios
    doc_table = Table(title="📜 Relatórios Oficiais Gerados em relatorios_avancos/", box=box.ROUNDED, border_style="yellow")
    doc_table.add_column("Arquivo Markdown", style="bold white")
    doc_table.add_column("Tamanho", style="yellow")
    doc_table.add_column("Data", style="cyan")

    reports = sorted(list(REPORTS_DIR.glob("*.md")))
    if reports:
        for rp in reports:
            st = rp.stat()
            dt = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            doc_table.add_row(rp.name, f"{st.st_size/1024:.1f} KB", dt)
    else:
        doc_table.add_row("Nenhum relatório encontrado", "-", "-")

    console.print(doc_table)
    console.print()


# ==============================================================================
# 3. CATÁLOGO DOS 217 BOTS OFICIAIS DO CHESS.COM
# ==============================================================================
def show_bots_catalog(query: Optional[str] = None, category_filter: Optional[str] = None):
    """Consulta os 217 bots oficiais com busca e formatação Rich."""
    mgr = ChessBotsManager(CURRENT_DIR)
    groups = mgr.get_all_groups()

    console.print(f"\n[bold green]>>> CATÁLOGO OFICIAL DE BOTS DO CHESS.COM ({len(groups)} Categorias) <<<[/bold green]")

    table = Table(box=box.ROUNDED, border_style="cyan")
    table.add_column("#", style="dim white", width=4)
    table.add_column("Nome", style="bold bright_white", width=18)
    table.add_column("Categoria", style="cyan", width=18)
    table.add_column("Rating", style="bold yellow", justify="right", width=8)
    table.add_column("Livro Polyglot", style="magenta", width=16)
    table.add_column("Acesso", style="green", width=12)

    total_listed = 0
    idx = 1
    for g in groups:
        cat_name = g.get("name", "Geral")
        if category_filter and category_filter.lower() not in cat_name.lower():
            continue
        bots = g.get("botPersonalities", [])
        for b in bots:
            name = b.get("name", "Bot")
            rating = str(b.get("rating", "?"))
            book = b.get("book", "balanced")
            can_play = "✓ Grátis" if b.get("canPlay") else "★ Premium"

            if query:
                q = query.lower()
                if q not in name.lower() and q not in rating and q not in cat_name.lower() and q not in book.lower():
                    continue

            table.add_row(str(idx), name, cat_name, rating, book, can_play)
            total_listed += 1
            idx += 1

    console.print(table)
    console.print(f"[bold cyan]Total de bots encontrados: {total_listed}[/bold cyan]\n")


# ==============================================================================
# 4. DUELO NO TERMINAL
# ==============================================================================
def start_terminal_duel(bot_name: str = "Nelson", player_color: str = "white"):
    """Inicia duelo interativo no terminal."""
    mgr = ChessBotsManager(CURRENT_DIR)
    is_white = (player_color.lower() != "black")
    mgr.play_game(bot_name=bot_name, player_is_white=is_white)


# ==============================================================================
# 5. AVALIAÇÃO NEURAL DE FEN
# ==============================================================================
def evaluate_position(fen: str, sims: int = 50):
    """Avalia posição com SE-ResNet e MCTS."""
    import chess
    import torch
    from chess_ai.agent import NeuralChessBot
    from chess_ai.model import ChessPolicyValueNet

    console.print("\n[bold green]>>> AVALIANDO POSIÇÃO COM REDE NEURAL SE-RESNET + MCTS <<<[/bold green]")
    try:
        board = chess.Board(fen)
    except Exception as e:
        console.print(f"[bold red][!] FEN inválida: {e}[/bold red]")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if WEIGHTS_PATH.is_file():
        model = ChessPolicyValueNet.load_weights(WEIGHTS_PATH, device=str(device))
    else:
        model = ChessPolicyValueNet().to(device)

    agent = NeuralChessBot(model=model, device=device, use_mcts=True, mcts_sims=sims)
    move, info = agent.get_best_move(board, use_mcts=True, num_simulations=sims)

    san = board.san(move) if move else "Nenhum"
    val = info.get("value", 0.0)
    prob = info.get("probability", 0.0) * 100.0
    src = info.get("source", "mcts_neural")

    t = Table(box=box.ROUNDED, border_style="gold1")
    t.add_column("Métrica", style="bold white")
    t.add_column("Avaliação", style="bright_yellow")
    t.add_row("FEN Analisada", fen)
    t.add_row("Melhor Lance Recomendado", f"{move} ({san})")
    t.add_row("Fonte de Decisão", src)
    t.add_row("Valor Posicional [-1.0 a +1.0]", f"{val:+.3f}")
    t.add_row("Confiança Política", f"{prob:.1f}%")
    t.add_row("Simulações MCTS Executadas", str(sims))
    t.add_row("Dispositivo de Inferência", f"{device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    console.print(t)
    console.print()


# ==============================================================================
# 6. TESTES AUTOMATIZADOS (PYTEST)
# ==============================================================================
def run_pytest_suite():
    """Executa a suíte de testes do projeto."""
    console.print("\n[bold green]>>> EXECUTANDO SUÍTE DE TESTES AUTOMATIZADOS (PYTEST) <<<[/bold green]\n")
    cmd = [sys.executable, "-m", "pytest", "-v"]
    subprocess.run(cmd, cwd=str(CURRENT_DIR))


# ==============================================================================
# MENU INTERATIVO RICH
# ==============================================================================
def interactive_menu():
    """Loop do menu principal Rich."""
    while True:
        print_banner()

        menu_table = Table(box=box.ROUNDED, border_style="bright_blue", show_header=True)
        menu_table.add_column("Opção", style="bold yellow", justify="center", width=7)
        menu_table.add_column("Utilitário / Funcionalidade", style="bold white", width=38)
        menu_table.add_column("Descrição Detalhada", style="dim cyan")

        menu_table.add_row("1", "🌐 GymArena Mobile Server", "Inicia servidor web local (FastAPI + WebSocket) na porta 8000")
        menu_table.add_row("2", "🏆 Torneio MD3 Oficial", "Executa torneio 30x acelerado contra os 217 bots do Chess.com")
        menu_table.add_row("3", "♟️ Bateria de Self-Play", "Gera 1.000 partidas aceleradas Neura vs Neura com PGN")
        menu_table.add_row("4", "🧠 Treinar Rede Neural", "Ajuste fino da SE-ResNet com AMP FP16 na GPU RTX 3060")
        menu_table.add_row("5", "🚀 Pipeline Master Completo", "Encadeia Torneio + Self-Play + Treino + Relatórios + Git Sync")
        menu_table.add_row("6", "⚔️ Duelo Interativo no Terminal", "Jogue contra qualquer bot oficial com abertura Polyglot real")
        menu_table.add_row("7", "📖 Catálogo dos 217 Bots", "Pesquise e inspecione ratings, livros, estilo e falas dos bots")
        menu_table.add_row("8", "📊 Dashboard & Status", "Painel de telemetria, checkpoints, vitórias e relatórios")
        menu_table.add_row("9", "🎯 Avaliar Posição FEN", "Inferência com a SE-ResNet e busca MCTS profunda")
        menu_table.add_row("10", "🧪 Suíte de Testes (pytest)", "Executa os 50 testes automatizados da arquitetura")
        menu_table.add_row("0", "🚪 Sair", "Encerra o Canivete Suíço")

        console.print(menu_table)
        choice = Prompt.ask("\n[bold yellow]Escolha uma opção (0-10)[/bold yellow]", default="8").strip()

        if choice == "1":
            port = IntPrompt.ask("[cyan]Porta do servidor web[/cyan]", default=8000)
            start_arena(port=port)
        elif choice == "2":
            workers = IntPrompt.ask("[cyan]Workers paralelos (threads in-memory)[/cyan]", default=4)
            fresh = Confirm.ask("[cyan]Deseja reiniciar do zero descartando checkpoint?[/cyan]", default=False)
            run_tournament(workers=workers, fresh=fresh)
        elif choice == "3":
            games = IntPrompt.ask("[cyan]Total de partidas de auto-jogo[/cyan]", default=1000)
            workers = IntPrompt.ask("[cyan]Workers paralelos[/cyan]", default=4)
            fresh = Confirm.ask("[cyan]Deseja reiniciar do zero descartando PGN e checkpoint?[/cyan]", default=False)
            run_selfplay(target_games=games, workers=workers, fresh=fresh)
        elif choice == "4":
            epochs = IntPrompt.ask("[cyan]Quantidade de épocas de treino[/cyan]", default=15)
            batch = IntPrompt.ask("[cyan]Tamanho do lote (batch size)[/cyan]", default=512)
            train_pipeline(epochs=epochs, batch_size=batch)
        elif choice == "5":
            confirm_pipe = Confirm.ask("[cyan]Deseja iniciar o Pipeline Master completo agora?[/cyan]", default=True)
            if confirm_pipe:
                run_full_pipeline()
        elif choice == "6":
            bot = Prompt.ask("[cyan]Nome do bot adversário[/cyan]", default="Nelson").strip()
            color = Prompt.ask("[cyan]Sua cor (white/black)[/cyan]", default="white").strip()
            start_terminal_duel(bot_name=bot, player_color=color)
        elif choice == "7":
            q = Prompt.ask("[cyan]Filtro por nome, Elo ou categoria (Enter para todos)[/cyan]", default="").strip()
            show_bots_catalog(query=q if q else None)
        elif choice == "8":
            show_dashboard()
        elif choice == "9":
            fen = Prompt.ask("[cyan]Cole a string FEN[/cyan]", default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1").strip()
            sims = IntPrompt.ask("[cyan]Número de simulações MCTS[/cyan]", default=50)
            evaluate_position(fen, sims=sims)
        elif choice == "10":
            run_pytest_suite()
        elif choice == "0":
            console.print("\n[bold cyan]Até logo e boas partidas! ♟️[/bold cyan]\n")
            break
        else:
            console.print("[bold red][!] Opção inválida.[/bold red]")

        Prompt.ask("\n[dim]Pressione Enter para voltar ao menu...[/dim]")


# ==============================================================================
# SUBCOMANDOS DE LINHA DE COMANDO (ARGPARSE)
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Canivete Suíço Universal do Chess_Bot (s_Neura_Gym)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Comando a executar")

    # arena
    p_arena = subparsers.add_parser("arena", help="Inicia o servidor web da GymArena Mobile")
    p_arena.add_argument("--host", type=str, default="0.0.0.0", help="Host de escuta (padrão: 0.0.0.0)")
    p_arena.add_argument("--port", type=int, default=8000, help="Porta TCP (padrão: 8000)")
    p_arena.add_argument("--reload", action="store_true", help="Auto-reload em modificações")

    # torneio
    p_tourn = subparsers.add_parser("torneio", help="Executa torneio MD3 contra os 217 bots")
    p_tourn.add_argument("--workers", type=int, default=4, help="Workers simultâneos (padrão: 4)")
    p_tourn.add_argument("--fresh", action="store_true", help="Reinicia descartando checkpoint")
    p_tourn.add_argument("--resume", action="store_true", help="Continua de checkpoint prévio")
    p_tourn.add_argument("--max-bots", type=int, default=None, help="Limite de bots a disputar")

    # selfplay
    p_sp = subparsers.add_parser("selfplay", help="Executa bateria de partidas de auto-jogo com PGN")
    p_sp.add_argument("--games", type=int, default=1000, help="Meta de partidas (padrão: 1000)")
    p_sp.add_argument("--workers", type=int, default=4, help="Workers paralelos (padrão: 4)")
    p_sp.add_argument("--fresh", action="store_true", help="Reinicia descartando PGN e checkpoint")
    p_sp.add_argument("--resume", action="store_true", help="Continua do checkpoint anterior")

    # treinar
    p_tr = subparsers.add_parser("treinar", help="Ajuste fino neural da SE-ResNet na GPU RTX 3060")
    p_tr.add_argument("--epochs", type=int, default=15, help="Quantidade de épocas (padrão: 15)")
    p_tr.add_argument("--batch-size", type=int, default=512, help="Tamanho do lote (padrão: 512)")
    p_tr.add_argument("--lr", type=float, default=1e-3, help="Taxa de aprendizado inicial")
    p_tr.add_argument("--rebuild", action="store_true", help="Reconstrói tensores sem usar cache")
    p_tr.add_argument("--no-validation", action="store_true", help="Pula duelos de validação pós-treino")

    # pipeline
    p_pipe = subparsers.add_parser("pipeline", help="Executa pipeline completo automatizado")
    p_pipe.add_argument("--skip-tournament", action="store_true", help="Pula a fase de torneio")
    p_pipe.add_argument("--skip-selfplay", action="store_true", help="Pula a fase de self-play")
    p_pipe.add_argument("--skip-train", action="store_true", help="Pula a fase de treino neural")
    p_pipe.add_argument("--tournament-workers", type=int, default=4, help="Workers no torneio")
    p_pipe.add_argument("--selfplay-games", type=int, default=1000, help="Partidas de self-play")
    p_pipe.add_argument("--selfplay-workers", type=int, default=4, help="Workers no self-play")
    p_pipe.add_argument("--epochs", type=int, default=15, help="Épocas de treino")
    p_pipe.add_argument("--no-git", action="store_true", help="Não sincroniza com Git ao final")

    # duelo
    p_duel = subparsers.add_parser("duelo", help="Inicia duelo interativo no terminal")
    p_duel.add_argument("--bot", type=str, default="Nelson", help="Nome do bot adversário")
    p_duel.add_argument("--color", type=str, default="white", choices=["white", "black"], help="Sua cor")

    # bots
    p_bots = subparsers.add_parser("bots", help="Lista e consulta catálogo dos 217 bots")
    p_bots.add_argument("--query", type=str, default=None, help="Filtro de busca por nome ou Elo")
    p_bots.add_argument("--category", type=str, default=None, help="Filtro por categoria")

    # status
    subparsers.add_parser("status", help="Exibe dashboard de status, checkpoints e telemetria")

    # avaliar
    p_eval = subparsers.add_parser("avaliar", help="Avalia posição FEN com a rede neural e MCTS")
    p_eval.add_argument("fen", type=str, help="Posição FEN a ser avaliada")
    p_eval.add_argument("--sims", type=int, default=50, help="Simulações MCTS (padrão: 50)")

    # test
    subparsers.add_parser("test", help="Executa a suíte de testes com pytest")

    args = parser.parse_args()

    if args.command == "arena":
        start_arena(host=args.host, port=args.port, reload=args.reload)
    elif args.command == "torneio":
        fresh = args.fresh or (not args.resume and not CHECKPOINT_TOURNAMENT.is_file())
        run_tournament(workers=args.workers, fresh=fresh, max_bots=args.max_bots)
    elif args.command == "selfplay":
        fresh = args.fresh or (not args.resume and not CHECKPOINT_SELFPLAY.is_file())
        run_selfplay(target_games=args.games, workers=args.workers, fresh=fresh)
    elif args.command == "treinar":
        train_pipeline(
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            force_rebuild_dataset=args.rebuild,
            run_validation_duels=not args.no_validation,
        )
    elif args.command == "pipeline":
        run_full_pipeline(
            run_tournament_phase=not args.skip_tournament,
            run_selfplay_phase=not args.skip_selfplay,
            run_training_phase=not args.skip_train,
            tournament_workers=args.tournament_workers,
            selfplay_games=args.selfplay_games,
            selfplay_workers=args.selfplay_workers,
            train_epochs=args.epochs,
            sync_git=not args.no_git,
        )
    elif args.command == "duelo":
        start_terminal_duel(bot_name=args.bot, player_color=args.color)
    elif args.command == "bots":
        show_bots_catalog(query=args.query, category_filter=args.category)
    elif args.command == "status":
        show_dashboard()
    elif args.command == "avaliar":
        evaluate_position(args.fen, sims=args.sims)
    elif args.command == "test":
        run_pytest_suite()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
