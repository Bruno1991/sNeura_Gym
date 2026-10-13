"""Script de Avaliação de Desempenho e Telemetria no Terminal (Max Speed)."""

import argparse
import os
import sys
import time
from pathlib import Path
import numpy as np

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_ai.config import SlitherConfig
from slither_ai.core.engine import SlitherEngine
from slither_ai.core.expert_bot import SlitherNativeBot
from slither_ai.env.sensors import SlitherSensors
from slither_ai.models.inference import FastPyTorchInference
from tqdm import tqdm


def main():
    parser = argparse.ArgumentParser(
        description="Avalia o desempenho da rede neural ou bot nativo no terminal em velocidade máxima."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Caminho para o checkpoint (.pt) ou 'native' para o bot do APK (padrão: auto-seleção do melhor modelo)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=20,
        help="Quantidade de partidas completas de teste (padrão: 20)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=1200,
        help="Passos máximos por partida (~40s de jogo, padrão: 1200)",
    )

    args = parser.parse_args()

    # Identifica o modelo padrão caso não especificado
    target_model = args.model
    if target_model is None:
        candidates = [
            "checkpoints/master_bot_model.pt",
            "checkpoints/best_imitation_model.pt",
            "checkpoints/best_ppo_model.pt",
        ]
        for c in candidates:
            if os.path.isfile(c):
                target_model = c
                break
        if target_model is None:
            target_model = "native"

    is_native = str(target_model).lower() == "native"
    ai_brain = None
    model_name = "Bot Especialista Nativo (Slither APK)"

    if not is_native:
        if os.path.isfile(target_model):
            ai_brain = FastPyTorchInference(target_model, device="cuda" if os.environ.get("USE_CPU") != "1" else "cpu")
            model_name = Path(target_model).name
        else:
            print(f"[!] Checkpoint '{target_model}' não encontrado. Usando Bot Nativo.")
            is_native = True

    print("\n" + "=" * 65)
    print("   SLITHER AI - AVALIAÇÃO DE DESEMPENHO NO TERMINAL (HEADLESS)")
    print("=" * 65)
    print(f"[*] Modelo em Teste: {model_name}")
    print(f"[*] Total de Partidas: {args.episodes} | Limite por Partida: {args.max_steps} ticks")
    print(f"[*] Arena: Raio {SlitherConfig.ARENA_RADIUS_TRAIN} | Bots Inimigos: {SlitherConfig.NUM_BOTS_TRAIN}")
    print("=" * 65 + "\n")

    scores = []
    kills = []
    lifespans = []
    wall_deaths = 0
    snake_deaths = 0

    total_sim_steps = 0
    start_eval_time = time.time()

    pbar = tqdm(range(1, args.episodes + 1), desc="Executando Partidas", unit="jogos")
    for ep in pbar:
        engine = SlitherEngine(
            arena_radius=SlitherConfig.ARENA_RADIUS_TRAIN,
            num_bots=SlitherConfig.NUM_BOTS_TRAIN,
            num_foods=SlitherConfig.NUM_FOOD_TRAIN,
        )
        player = engine.add_player_snake("NeuraBot_Eval")
        native_bot = SlitherNativeBot(player) if is_native else None

        step = 0
        while player.is_alive and step < args.max_steps:
            if is_native:
                native_bot.update_decision(
                    all_snakes=engine.snakes,
                    foods=engine.foods,
                    current_time_sec=engine.current_time_sec,
                    arena_radius=engine.arena_radius,
                )
            else:
                obs = SlitherSensors.get_observation(
                    snake=player,
                    all_snakes=engine.snakes,
                    foods=engine.foods,
                    arena_radius=engine.arena_radius,
                )
                delta, boost = ai_brain.predict(obs)
                player.target_angle = player.angle + delta * 3.14159265
                player.is_boosting = boost

            engine.step(0.033)
            step += 1
            total_sim_steps += 1

        # Diagnóstico da morte
        if not player.is_alive:
            dist_center = (player.x * player.x + player.y * player.y) ** 0.5
            if dist_center >= (engine.arena_radius - player.radius - 10.0):
                wall_deaths += 1
            else:
                snake_deaths += 1

        scores.append(player.score)
        kills.append(player.kills)
        lifespans.append(step * 0.033)

        pbar.set_postfix({
            "Score Médio": f"{np.mean(scores):.1f}",
            "Max Score": f"{np.max(scores):.1f}",
            "Abates": f"{np.sum(kills)}",
        })

    elapsed_time = max(0.001, time.time() - start_eval_time)
    throughput_fps = total_sim_steps / elapsed_time

    # Relatório Final
    print("\n" + "=" * 65)
    print("                 RELATÓRIO DE DESEMPENHO")
    print("=" * 65)
    print(f"  Vazão de Simulação:       {throughput_fps:,.0f} FPS (Tempo total: {elapsed_time:.2f}s)")
    print(f"  Comprimento Médio:        {np.mean(scores):.1f} segmentos")
    print(f"  Comprimento Máximo:       {np.max(scores):.1f} segmentos")
    print(f"  Sobrevivência Média:      {np.mean(lifespans):.1f} segundos por vida")
    print(f"  Total de Inimigos Mortos: {np.sum(kills)} abates (Média: {np.mean(kills):.2f}/vida)")
    print(f"  Mortes por Outras Cobras: {snake_deaths} ({snake_deaths / max(1, len(scores)) * 100:.1f}%)")
    print(f"  Mortes por Borda do Mapa: {wall_deaths} ({wall_deaths / max(1, len(scores)) * 100:.1f}%)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
