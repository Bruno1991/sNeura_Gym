"""Script de inicialização da Arena do Espectador Web (Live Web Viewer)."""

import argparse
import sys
from pathlib import Path

# Adiciona a raiz do projeto ao sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_ai.viewer.server import start_spectator_server


def main():
    parser = argparse.ArgumentParser(
        description="Inicia o servidor da Arena do Espectador para assistir a IA jogando Slither.io."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host do servidor HTTP/WebSocket (padrão: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Porta do servidor HTTP/WebSocket (padrão: 8080)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Caminho para o checkpoint (.pt) da rede neural (opcional, padrão: best_ppo_model.pt ou best_imitation_model.pt)",
    )

    args = parser.parse_args()

    start_spectator_server(
        host=args.host,
        port=args.port,
        model_path=args.model,
    )


if __name__ == "__main__":
    main()
