"""Benchmark de performance e FPS do SlitherEngine."""

import time
import sys
from pathlib import Path

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_ai.core.engine import SlitherEngine


def run_benchmark(duration_seconds: float = 3.0):
    print("=============================================================")
    print("    SlitherEngine - Benchmark de Performance de Física")
    print("=============================================================")
    
    engine = SlitherEngine(num_bots=15, num_foods=500)
    print(f"[*] Simulação com {len(engine.snakes)} cobras e {len(engine.foods)} orbs de comida...")

    ticks = 0
    start_time = time.perf_counter()

    while time.perf_counter() - start_time < duration_seconds:
        engine.step(dt=0.033)
        ticks += 1

    elapsed = time.perf_counter() - start_time
    tps = ticks / elapsed
    sim_speed_multiplier = (ticks * 0.033) / elapsed

    print(f"[+] Ticks executados:  {ticks}")
    print(f"[+] Tempo decorrido:   {elapsed:.2f}s")
    print(f"[+] Performance:       {tps:.1f} Ticks/Segundo (FPS de Simulação)")
    print(f"[+] Aceleração:        {sim_speed_multiplier:.1f}x em relação ao tempo real do jogo!")
    print("=============================================================\n")


if __name__ == "__main__":
    run_benchmark()
