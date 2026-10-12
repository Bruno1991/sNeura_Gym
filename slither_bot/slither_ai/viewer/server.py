"""Servidor Web e WebSocket assíncrono para a Arena do Espectador em tempo real."""

import asyncio
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional
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

# Cores vibrantes inspiradas nas skins clássicas e raras do Slither.io APK
SNAKE_SKINS = [
    {"name": "Esmeralda", "head": "#10b981", "body": ["#059669", "#34d399"], "border": "#064e3b"},
    {"name": "Rubi Fogo", "head": "#ef4444", "body": ["#dc2626", "#f87171"], "border": "#7f1d1d"},
    {"name": "Safira Elétrica", "head": "#3b82f6", "body": ["#2563eb", "#60a5fa"], "border": "#1e3a8a"},
    {"name": "Ametista Neon", "head": "#a855f7", "body": ["#9333ea", "#c084fc"], "border": "#581c87"},
    {"name": "Âmbar Solar", "head": "#f59e0b", "body": ["#d97706", "#fbbf24"], "border": "#78350f"},
    {"name": "Ciano Ártico", "head": "#06b6d4", "body": ["#0891b2", "#22d3ee"], "border": "#164e63"},
    {"name": "Rosa Choque", "head": "#ec4899", "body": ["#db2777", "#f472b6"], "border": "#831843"},
    {"name": "Arco-Íris", "head": "#e11d48", "body": ["#f97316", "#eab308", "#10b981", "#06b6d4", "#6366f1", "#a855f7"], "border": "#4c0519"},
]

# Skin especial para o bot do jogador espectador (Tecnologia IA NeuraBot)
PLAYER_SKIN = {
    "name": "NeuraBot_AI",
    "head": "#00f0ff",
    "body": ["#0ea5e9", "#00f0ff", "#38bdf8"],
    "border": "#0369a1",
}


def create_spectator_app(default_brain: str = "native", model_path: Optional[str] = None) -> FastAPI:
    """Cria e configura a aplicação FastAPI para o espectador."""
    if model_path:
        if "ppo" in model_path.lower():
            default_brain = "ppo"
        elif "imitation" in model_path.lower():
            default_brain = "imitation"

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

    # Pré-carrega cérebros neurais se disponíveis
    imitation_model_path = "checkpoints/best_imitation_model.pt"
    ppo_model_path = "checkpoints/best_ppo_model.pt"

    neural_brains: Dict[str, Optional[FastPyTorchInference]] = {
        "imitation": None,
        "ppo": None,
    }

    if os.path.isfile(imitation_model_path):
        try:
            neural_brains["imitation"] = FastPyTorchInference(imitation_model_path, device="cpu")
            print("[+] Cérebro Neural (Imitação) pronto para uso.")
        except Exception as e:
            print(f"[!] Aviso ao carregar modelo de imitação: {e}")

    if os.path.isfile(ppo_model_path):
        try:
            neural_brains["ppo"] = FastPyTorchInference(ppo_model_path, device="cpu")
            print("[+] Cérebro Neural (PPO) pronto para uso.")
        except Exception as e:
            print(f"[!] Aviso ao carregar modelo PPO: {e}")

    @app.websocket("/ws")
    async def websocket_spectator(websocket: WebSocket):
        await websocket.accept()
        print("[+] Espectador conectado via WebSocket!")

        # Inicializa a arena simulada (raio 2500, 15 bots, 600 orbs)
        engine = SlitherEngine(
            arena_radius=SlitherConfig.ARENA_RADIUS_TRAIN,
            num_bots=SlitherConfig.NUM_BOTS_TRAIN,
            num_foods=SlitherConfig.NUM_FOOD_TRAIN,
        )
        player_snake = engine.add_player_snake("NeuraBot (IA)")
        native_bot = SlitherNativeBot(player_snake)

        # Cérebro ativo: "native" (Padrão: IA Original do APK), "imitation", "ppo" ou "manual"
        current_brain = default_brain
        manual_target_angle = player_snake.angle
        manual_is_boosting = False

        # Atribuição de skins para bots inimigos
        skin_map = {}
        for idx, s in enumerate(engine.snakes):
            skin_map[s.id] = SNAKE_SKINS[idx % len(SNAKE_SKINS)]

        fps_target = 60
        frame_interval = 1.0 / fps_target

        try:
            while True:
                frame_start = asyncio.get_event_loop().time()

                # Processa comandos recebidos do cliente web
                try:
                    while True:
                        data = await asyncio.wait_for(websocket.receive_text(), timeout=0.002)
                        msg = json.loads(data)
                        cmd = msg.get("cmd")

                        if cmd == "reset":
                            engine.reset()
                            player_snake = engine.add_player_snake("NeuraBot (IA)")
                            native_bot = SlitherNativeBot(player_snake)
                            manual_target_angle = player_snake.angle
                            manual_is_boosting = False
                            for idx, s in enumerate(engine.snakes):
                                skin_map[s.id] = SNAKE_SKINS[idx % len(SNAKE_SKINS)]

                        elif cmd == "set_brain":
                            requested_brain = msg.get("brain", "native")
                            if requested_brain in ["native", "imitation", "ppo", "manual"]:
                                current_brain = requested_brain
                                print(f"[*] Cérebro do bot alterado para: {current_brain}")

                        elif cmd == "mouse_control":
                            if "angle" in msg:
                                manual_target_angle = float(msg["angle"])
                            if "boost" in msg:
                                manual_is_boosting = bool(msg["boost"])

                except (asyncio.TimeoutError, json.JSONDecodeError):
                    pass

                # 1. Se a cobra do jogador morreu, faz respawn com imunidade inicial
                if not player_snake.is_alive:
                    player_snake = engine.add_player_snake("NeuraBot (IA)")
                    native_bot = SlitherNativeBot(player_snake)
                    manual_target_angle = player_snake.angle

                # 2. Extrai Observação Sensorial (32 floats LIDAR)
                obs = SlitherSensors.get_observation(
                    snake=player_snake,
                    all_snakes=engine.snakes,
                    foods=engine.foods,
                    arena_radius=engine.arena_radius,
                )

                # 3. Execução da Decisão Conforme o Cérebro Selecionado
                brain_label = "🧠 IA Nativa Especialista (Slither APK)"

                if current_brain == "manual":
                    brain_label = "🎮 Controle Manual (Mouse do Operador)"
                    player_snake.target_angle = manual_target_angle
                    player_snake.is_boosting = manual_is_boosting

                elif current_brain == "imitation" and neural_brains["imitation"] is not None:
                    brain_label = "⚡ Rede Neural - Imitação (Behavior Cloning)"
                    angle_delta, boost_active = neural_brains["imitation"].predict(obs)
                    player_snake.target_angle = normalize_angle_two_pi(
                        player_snake.angle + angle_delta * math.pi
                    )
                    player_snake.is_boosting = boost_active

                elif current_brain == "ppo" and neural_brains["ppo"] is not None:
                    brain_label = "🎯 Rede Neural - Reforço (PPO Self-Play)"
                    angle_delta, boost_active = neural_brains["ppo"].predict(obs)
                    player_snake.target_angle = normalize_angle_two_pi(
                        player_snake.angle + angle_delta * math.pi
                    )
                    player_snake.is_boosting = boost_active

                else:
                    # Padrão: 100% IA Especialista Original de gaim.Main.as
                    current_brain = "native"
                    brain_label = "🧠 IA Nativa Especialista (Slither APK)"
                    native_bot.update_decision(
                        all_snakes=engine.snakes,
                        foods=engine.foods,
                        current_time_sec=engine.current_time_sec,
                        arena_radius=engine.arena_radius,
                    )

                # 4. Avança o Passo Físico da Engine
                engine.step(dt=0.025)

                # 5. Prepara os dados das cobras inimigas
                other_snakes_data = []
                for s in engine.snakes:
                    if s.id != player_snake.id and s.is_alive:
                        other_snakes_data.append({
                            "id": s.id,
                            "name": s.name,
                            "x": round(s.x, 1),
                            "y": round(s.y, 1),
                            "angle": round(s.angle, 3),
                            "target_angle": round(s.target_angle, 3),
                            "radius": round(s.radius, 1),
                            "score": round(s.score, 1),
                            "is_boosting": s.is_boosting,
                            "skin": skin_map.get(s.id, SNAKE_SKINS[0]),
                            "segments": [
                                {"x": round(seg.x, 1), "y": round(seg.y, 1), "radius": round(seg.radius, 1)}
                                for seg in s.segments
                            ],
                        })

                # 6. Alimentos visíveis na vizinhança da câmera
                cam_x, cam_y = player_snake.x, player_snake.y
                visible_foods = []
                for fo in engine.foods:
                    if not fo.is_eaten:
                        dx = fo.x - cam_x
                        dy = fo.y - cam_y
                        if (dx * dx + dy * dy) < (1500 * 1500):
                            visible_foods.append({
                                "id": fo.id,
                                "x": round(fo.x, 1),
                                "y": round(fo.y, 1),
                                "radius": round(fo.radius, 1),
                                "value": round(fo.value, 1),
                                "is_poop": fo.is_poop,
                            })

                # 7. Placar (Leaderboard) - Top 10 cobras da arena
                sorted_snakes = sorted(
                    [s for s in engine.snakes if s.is_alive],
                    key=lambda s: s.score,
                    reverse=True
                )
                leaderboard = [
                    {
                        "rank": idx + 1,
                        "name": s.name,
                        "score": round(s.score),
                        "is_player": (s.id == player_snake.id),
                    }
                    for idx, s in enumerate(sorted_snakes[:10])
                ]

                # 8. Minimapa (posição do jogador e pontos dos inimigos)
                minimap_dots = [
                    {
                        "x": round(s.x, 1),
                        "y": round(s.y, 1),
                        "radius": round(s.radius, 1),
                        "is_player": (s.id == player_snake.id),
                    }
                    for s in sorted_snakes
                ]

                state_payload = {
                    "active_brain": current_brain,
                    "brain_label": brain_label,
                    "available_brains": {
                        "native": True,
                        "imitation": (neural_brains["imitation"] is not None),
                        "ppo": (neural_brains["ppo"] is not None),
                        "manual": True,
                    },
                    "arena_radius": engine.arena_radius,
                    "snakes_count": len([s for s in engine.snakes if s.is_alive]),
                    "foods_count": len(engine.foods),
                    "player_snake": {
                        "name": player_snake.name,
                        "x": round(player_snake.x, 1),
                        "y": round(player_snake.y, 1),
                        "angle": round(player_snake.angle, 3),
                        "target_angle": round(player_snake.target_angle, 3),
                        "speed": round(player_snake.speed, 1),
                        "score": round(player_snake.score, 1),
                        "kills": player_snake.kills,
                        "radius": round(player_snake.radius, 1),
                        "is_boosting": player_snake.is_boosting,
                        "is_alive": player_snake.is_alive,
                        "skin": PLAYER_SKIN,
                        "segments": [
                            {"x": round(seg.x, 1), "y": round(seg.y, 1), "radius": round(seg.radius, 1)}
                            for seg in player_snake.segments
                        ],
                    },
                    "lidar_readings": [round(float(v), 2) for v in obs[0:16]],
                    "other_snakes": other_snakes_data,
                    "foods": visible_foods,
                    "leaderboard": leaderboard,
                    "minimap_dots": minimap_dots,
                }

                await websocket.send_text(json.dumps(state_payload))

                # Mantém 60 FPS fluídos
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
    default_brain = "native"
    if model_path:
        if "ppo" in model_path.lower():
            default_brain = "ppo"
        elif "imitation" in model_path.lower():
            default_brain = "imitation"

    print("=============================================================")
    print("    Slither AI - Arena Oficial do Espectador (Live 60 FPS)")
    print("=============================================================")
    print(f"[*] Cérebro Inicial Padrão: {default_brain.upper()} (IA Nativa do Slither APK)")
    print(f"[+] Servidor ativo em: http://localhost:{port}")
    print(f"    (Abra este endereço no seu navegador para assistir)")
    print("=============================================================\n")

    app = create_spectator_app(default_brain=default_brain)
    uvicorn.run(app, host=host, port=port, log_level="warning")
