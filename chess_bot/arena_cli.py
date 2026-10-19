"""CLI Unificado da GymArena & Chess Hub (s_Neura_Gym).

Ponto de entrada central para:
- Servidor Web GymArena Mobile (FastAPI + WebSocket na porta 8000)
- Bateria de Torneio (10.000 ou 50.000 partidas com 64 workers)
- Catálogo e consulta dos 217 bots oficiais do Chess.com
- Partida interativa no terminal
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Suporte UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent


def start_arena_server(host: str = "0.0.0.0", port: int = 8000):
    """Inicia o servidor web da GymArena."""
    print("\n" + "=" * 70)
    print("      ♛ GYMARENA: SERVIDOR WEB INICIADO ♛")
    print("=" * 70)
    print(f" [*] Interface Web Mobile: http://localhost:{port}")
    print(" [*] Pressione CTRL+C para encerrar o servidor.\n")
    import uvicorn
    uvicorn.run("arena.server:app", host=host, port=port, reload=False, app_dir=str(CURRENT_DIR))


def run_battery(games: int = 10000, workers: int = 64):
    """Executa a bateria de torneio."""
    script = CURRENT_DIR / "run_10k_battery.py"
    cmd = [sys.executable, str(script), "--games", str(games), "--workers", str(workers)]
    subprocess.run(cmd)


def list_bots():
    """Consulta catálogo de bots."""
    from chess_bots import ChessBotsManager
    mgr = ChessBotsManager(CURRENT_DIR)
    groups = mgr.list_groups()
    print(f"\n[*] Total de Categorias: {len(groups)}")
    for g in groups:
        bots = mgr.get_bots_in_group(g)
        print(f"\n--- {g} ({len(bots)} bots) ---")
        for b in bots:
            print(f"  • {b.get('name', 'Bot'):<18} | Elo: {b.get('rating', '?'):<5} | Livro: {b.get('book', 'balanced')}")


def play_terminal():
    """Partida no terminal."""
    from chess_bots import ChessBotsManager
    mgr = ChessBotsManager(CURRENT_DIR)
    mgr.play_game(bot_name="Nelson", player_is_white=True)


def interactive_menu():
    while True:
        print("\n" + "=" * 70)
        print("      ♛ S_NEURA_GYM: ARENA & CHESS HUB UNIFICADO ♛")
        print("=" * 70)
        print(" [1] Iniciar Servidor Web da GymArena (Mobile UI na porta 8000)")
        print(" [2] Rodar Bateria de 10.000 Partidas (64 Workers AMP FP16)")
        print(" [3] Consultar Catálogo Completo dos 217 Bots Oficiais")
        print(" [4] Jogar Partida no Terminal contra um Bot")
        print(" [0] Sair")
        print("=" * 70)
        choice = input("Escolha uma opção (0-4): ").strip()

        if choice == "1":
            start_arena_server()
        elif choice == "2":
            run_battery(10000, 64)
        elif choice == "3":
            list_bots()
        elif choice == "4":
            play_terminal()
        elif choice == "0":
            print("\nAté logo!")
            break
        else:
            print("\n[!] Opção inválida.")


def main():
    parser = argparse.ArgumentParser(description="GymArena & Chess Hub CLI")
    parser.add_argument("--server", action="store_true", help="Inicia o servidor web da GymArena")
    parser.add_argument("--port", type=int, default=8000, help="Porta do servidor (padrão: 8000)")
    parser.add_argument("--battery", action="store_true", help="Roda bateria de 10.000 partidas")
    parser.add_argument("--games", type=int, default=10000, help="Partidas da bateria")
    parser.add_argument("--workers", type=int, default=64, help="Workers paralelos")
    parser.add_argument("--list-bots", action="store_true", help="Lista catálogo de bots")
    parser.add_argument("--play", action="store_true", help="Joga no terminal contra Nelson")
    args = parser.parse_args()

    if args.server:
        start_arena_server(port=args.port)
    elif args.battery:
        run_battery(args.games, args.workers)
    elif args.list_bots:
        list_bots()
    elif args.play:
        play_terminal()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
