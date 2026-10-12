"""Conecta o bot neural a um servidor do Slither.io (local ou oficial)."""

import argparse
import asyncio
import sys
from pathlib import Path

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_ai.online.client import SlitherOnlineClient


def main():
    parser = argparse.ArgumentParser(description="Cliente Online de Slither.io com Bot Neural.")
    parser.add_argument("--host", default="127.0.0.1", help="IP do servidor Slither")
    parser.add_argument("--port", type=int, default=444, help="Porta WebSocket")
    parser.add_argument("--nick", default="NeuraBot_AI", help="Apelido da cobra no jogo")
    parser.add_argument("--model", default="checkpoints/best_imitation_model.pt", help="Caminho do modelo neural")
    parser.add_argument("--duration", type=float, default=60.0, help="Duração máxima em segundos")
    args = parser.parse_args()

    client = SlitherOnlineClient(
        server_ip=args.host,
        server_port=args.port,
        nickname=args.nick,
        model_path=args.model if Path(args.model).is_file() else None,
    )

    asyncio.run(client.connect_and_play(max_seconds=args.duration))


if __name__ == "__main__":
    main()
