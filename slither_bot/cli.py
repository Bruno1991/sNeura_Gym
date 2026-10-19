"""Canivete Suíço Universal do Slither Bot (s_Neura_Gym - slither_bot).

Interface unificada e centralizada de controle para:
- Jogar em servidor com o bot neural (run_online_bot)
- Avaliar bot no terminal (run_eval_terminal)
- Executar benchmark de desempenho (run_benchmark)
- Treinamento contínuo 24/7 (run_training_247)
- Treinamento por Imitação / DAgger / PPO RL
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
NEURAL_DIR = CURRENT_DIR / "Neural_Bot"
SCRIPTS_DIR = NEURAL_DIR / "scripts"


def run_online(host: str = "127.0.0.1", port: int = 444):
    """Conecta bot ao servidor Slither."""
    script = SCRIPTS_DIR / "run_online_bot.py"
    cmd = [sys.executable, str(script), "--host", host, "--port", str(port)]
    subprocess.run(cmd, cwd=str(NEURAL_DIR))


def run_eval(episodes: int = 10):
    """Avalia o bot no terminal."""
    script = SCRIPTS_DIR / "run_eval_terminal.py"
    cmd = [sys.executable, str(script), "--episodes", str(episodes)]
    subprocess.run(cmd, cwd=str(NEURAL_DIR))


def run_bench():
    """Roda benchmark de FPS e inferência."""
    script = SCRIPTS_DIR / "run_benchmark.py"
    subprocess.run([sys.executable, str(script)], cwd=str(NEURAL_DIR))


def run_train(mode: str = "247"):
    """Inicia treinamento."""
    script_map = {
        "247": "run_training_247.py",
        "dagger": "run_training_dagger.py",
        "imitation": "run_training_imitation.py",
        "ppo": "run_training_ppo.py",
    }
    script_name = script_map.get(mode, "run_training_247.py")
    script = SCRIPTS_DIR / script_name
    subprocess.run([sys.executable, str(script)], cwd=str(NEURAL_DIR))


def interactive_menu():
    while True:
        print("\n" + "=" * 65)
        print("          🐍 S_NEURA_GYM: CANIVETE SUÍÇO DO SLITHER_BOT 🐍")
        print("=" * 65)
        print(" [1] Conectar Bot Neural ao Servidor (run_online_bot)")
        print(" [2] Avaliar Desempenho no Terminal (run_eval_terminal)")
        print(" [3] Executar Benchmark de Inferência e FPS")
        print(" [4] Treinamento Contínuo 24/7 (Maestria)")
        print(" [5] Treinamento por DAgger")
        print(" [6] Treinamento por Imitação (Behavioral Cloning)")
        print(" [7] Treinamento por Reforço (PPO RL)")
        print(" [0] Sair")
        print("=" * 65)
        choice = input("Escolha uma opção (0-7): ").strip()

        if choice == "1":
            h = input("IP do servidor (padrão 127.0.0.1): ").strip() or "127.0.0.1"
            p = input("Porta (padrão 444): ").strip() or "444"
            run_online(host=h, port=int(p))
        elif choice == "2":
            ep = input("Episódios para avaliar (padrão 10): ").strip() or "10"
            run_eval(episodes=int(ep))
        elif choice == "3":
            run_bench()
        elif choice == "4":
            run_train("247")
        elif choice == "5":
            run_train("dagger")
        elif choice == "6":
            run_train("imitation")
        elif choice == "7":
            run_train("ppo")
        elif choice == "0":
            print("\nAté logo!")
            break
        else:
            print("\n[!] Opção inválida.")


def main():
    parser = argparse.ArgumentParser(description="Canivete Suíço do Slither_Bot")
    parser.add_argument("--play", action="store_true", help="Conecta o bot online")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host do servidor")
    parser.add_argument("--port", type=int, default=444, help="Porta do servidor")
    parser.add_argument("--eval", action="store_true", help="Avalia o bot no terminal")
    parser.add_argument("--benchmark", action="store_true", help="Roda benchmark de FPS")
    parser.add_argument("--train", choices=["247", "dagger", "imitation", "ppo"], help="Modo de treinamento")
    args = parser.parse_args()

    if args.play:
        run_online(host=args.host, port=args.port)
    elif args.eval:
        run_eval()
    elif args.benchmark:
        run_bench()
    elif args.train:
        run_train(args.train)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
