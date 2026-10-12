"""Servidor Web e WebSocket assíncrono para a Arena do Espectador em tempo real."""

import asyncio
import json
import math
import os
from pathlib import Path
from typing import Optional
import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from ..config import SlitherConfig
from ..core.engine import SlitherEngine
from ..core.entities import Snake
from ..core.expert_bot import SlitherNativeBot
from ..env.sensors import SlitherSensors
from ..models.inference import FastPyTorchInference
from ..utils.math_helpers import normalize_angle_two_pi

# Cores vibrantes para cobras inimigas
BOT_COLORS = [
    "#a855f7", "#ec4899", "#f97316", "#eab308", 
    "#84cc16", "#06b6d4", "#6366f1", "#f43f5e"
]


def create_spectator_app(model_path: Optional[str] = None) -> FastAPI:
    """Cria e configura a aplicação FastAPI para o espectador."""
    app = FastAPI(title="Slither AI Spectator Arena")

    web_dir = Path(__file__).resolve().parent / "web"
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(web_dir / "index.html")

    @app.get("/viewer.css")
    async def serve_css():
        return FileResponse(web_dir / "viewer.css")

    @app.get("/viewer.js")
    async def serve_js():
        return FileResponse(web_dir / "viewer.js")

    # Inicializa o cérebro da IA para o bot principal
    ai_brain: Optional[FastPyTorchInference] = None
    model_name = "Bot Especialista Nativo"

    if model_path and os.path.isfile(model_path):
        try:
            ai_brain = FastPyTorchInference(model_path, device="cpu")
            model_name = Path(model_path).name
        except Exception as e:
            print(f"[!] Aviso ao carregar modelo neural ({e}). Usando Bot Nativo.")

    @app.websocket("/ws")
    async def websocket_spectator(websocket: WebSocket):
        await websocket.accept()
        print("[+] Espectador conectado via WebSocket!")

        # Inicializa a arena simulada para visualização (60 FPS / ~16ms tick)
        engine = SlitherEngine(
            arena_radius=SlitherConfig.ARENA_RADIUS_TRAIN,
            num_bots=SlitherConfig.NUM_BOTS_TRAIN,
            num_foods=SlitherConfig.NUM_FOOD_TRAIN,
        )
        player_snake = engine.add_player_snake("NeuraBot_AI (IA)")
        native_fallback_bot = SlitherNativeBot(player_snake)

        # Associa cores às cobras inimigas
        color_map = {}
        for idx, s in enumerate(engine.snakes):
            color_map[s.id] = BOT_COLORS[idx % len(BOT_COLORS)]

        fps_target = 60
        frame_interval = 1.0 / fps_target

        try:
            while True:
                frame_start = asyncio.get_event_loop().time()

                # Verifica se há comandos do espectador (ex: reset)
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=0.001)
                    msg = json.loads(data)
                    if msg.get("cmd") == "reset":
                        engine.reset()
                        player_snake = engine.add_player_snake("NeuraBot_AI (IA)")
                        native_fallback_bot = SlitherNativeBot(player_snake)
                except (asyncio.TimeoutError, json.JSONDecodeError):
                    pass

                # 1. Se a cobra do jogador morreu, faz respawn suave
                if not player_snake.is_alive:
                    player_snake = engine.add_player_snake("NeuraBot_AI (IA)")
                    native_fallback_bot = SlitherNativeBot(player_snake)

                # 2. Extrai a Percepção Sensorial (32 dimensões com LIDAR)
                obs = SlitherSensors.get_observation(
                    snake=player_snake,
                    all_snakes=engine.snakes,
                    foods=engine.foods,
                    arena_radius=engine.arena_radius,
                )

                # 3. Decisão da Rede Neural (ou Bot Nativo)
                if ai_brain is not None:
                    angle_delta, boost_active = ai_brain.predict(obs)
                    player_snake.target_angle = normalize_angle_two_pi(
                        player_snake.angle + angle_delta * math.pi
                    )
                    player_snake.is_boosting = boost_active
                else:
                    native_fallback_bot.update_decision(
                        all_snakes=engine.snakes,
                        foods=engine.foods,
                        current_time_sec=engine.current_time_sec,
                        arena_radius=engine.arena_radius,
                    )

                # 4. Avança a física do mundo
                engine.step(dt=0.025)

                # 5. Empacota dados da cena de forma compacta
                other_snakes_data = []
                for s in engine.snakes:
                    if s.id != player_snake.id and s.is_alive:
                        other_snakes_data.append({
                            "id": s.id,
                            "name": s.name,
                            "x": round(s.x, 1),
                            "y": round(s.y, 1),
                            "angle": round(s.angle, 2),
                            "radius": round(s.radius, 1),
                            "color": color_map.get(s.id, "#a855f7"),
                            "segments": [
                                {"x": round(seg.x, 1), "y": round(seg.y, 1), "radius": round(seg.radius, 1)}
                                for seg in s.segments
                            ],
                        })

                # Alimentos visíveis num raio de 1200px da câmera
                cam_x, cam_y = player_snake.x, player_snake.y
                visible_foods = []
                for fo in engine.foods:
                    if not fo.is_eaten:
                        dx = fo.x - cam_x
                        dy = fo.y - cam_y
                        if (dx * dx + dy * dy) < (1200 * 1200):
                            visible_foods.append({
                                "x": round(fo.x, 1),
                                "y": round(fo.y, 1),
                                "radius": round(fo.radius, 1),
                                "is_poop": fo.is_poop,
                            })

                state_payload = {
                    "model_name": model_name,
                    "arena_radius": engine.arena_radius,
                    "snakes_count": len([s for s in engine.snakes if s.is_alive]),
                    "foods_count": len(engine.foods),
                    "player_snake": {
                        "name": player_snake.name,
                        "x": round(player_snake.x, 1),
                        "y": round(player_snake.y, 1),
                        "angle": round(player_snake.angle, 2),
                        "speed": round(player_snake.speed, 1),
                        "score": round(player_snake.score, 1),
                        "kills": player_snake.kills,
                        "radius": round(player_snake.radius, 1),
                        "is_boosting": player_snake.is_boosting,
                        "is_alive": player_snake.is_alive,
                        "segments": [
                            {"x": round(seg.x, 1), "y": round(seg.y, 1), "radius": round(seg.radius, 1)}
                            for seg in player_snake.segments
                        ],
                    },
                    "lidar_readings": [round(float(v), 2) for v in obs[0:16]],
                    "other_snakes": other_snakes_data,
                    "foods": visible_foods,
                }

                await websocket.send_text(json.dumps(state_payload))

                # Mantém 60 FPS estáveis
                elapsed = asyncio.get_event_loop().time() - frame_start
                sleep_time = max(0.001, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)

        except WebSocketDisconnect:
            print("[*] Espectador desconectado do WebSocket.")
        except Exception as e:
            print(f"[!] Erro no loop do espectador: {e}")

    return app


def start_spectator_server(host: str = "127.0.0.1", port: int = 8080, model_path: Optional[str] = None):
    """Inicia o servidor uvicorn para o espectador."""
    # Se nenhum modelo for especificado, tenta carregar o melhor modelo treinado
    if model_path is None:
        candidates = [
            "checkpoints/best_ppo_model.pt",
            "checkpoints/best_imitation_model.pt",
        ]
        for c in candidates:
            if os.path.isfile(c):
                model_path = c
                break

    print("=============================================================")
    print("    Slither AI - Arena do Espectador (Live Web Viewer)")
    print("=============================================================")
    print(f"[*] Modelo em exibição: {model_path or 'Bot Especialista Nativo'}")
    print(f"[+] Servidor ativo em: http://localhost:{port}")
    print(f"    (Abra este endereço no seu navegador para assistir)")
    print("=============================================================\n")

    app = create_spectator_app(model_path=model_path)
    uvicorn.run(app, host=host, port=port, log_level="warning")
