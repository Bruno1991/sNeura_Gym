"""Cliente de conexão online oficial com IA neural ou bot especialista integrado."""

import asyncio
import math
from typing import Optional
import websockets

from ..config import SlitherConfig
from ..models.inference import FastPyTorchInference
from ..utils.math_helpers import angle_to_protocol_byte
from .crypto import SlitherHandshake
from .protocol import SlitherProtocol


class SlitherOnlineClient:
    """Conecta ao WebSocket do servidor do Slither.io, executa handshake e joga com IA."""

    def __init__(
        self,
        server_ip: str = "127.0.0.1",
        server_port: int = 444,
        nickname: str = "NeuraBot_AI",
        model_path: Optional[str] = None,
    ):
        self.server_ip = server_ip
        self.server_port = server_port
        self.nickname = nickname
        self.model_path = model_path
        
        self.ai_inference: Optional[FastPyTorchInference] = None
        if model_path:
            self.ai_inference = FastPyTorchInference(model_path)

        self.is_connected = False
        self.has_shaken_hands = False
        self.game_radius = SlitherConfig.GAME_RADIUS

    async def connect_and_play(self, max_seconds: float = 60.0):
        """Estabelece a conexão e inicia o loop de jogo autônomo."""
        uri = f"ws://{self.server_ip}:{self.server_port}/slither"
        print(f"[*] Tentando conexão com servidor Slither: {uri}...")

        try:
            async with websockets.connect(uri) as ws:
                self.is_connected = True
                print("[+] Conectado com sucesso ao socket do servidor!")

                start_time = asyncio.get_event_loop().time()

                async for message in ws:
                    if asyncio.get_event_loop().time() - start_time > max_seconds:
                        print("[*] Tempo limite de sessão atingido.")
                        break

                    if isinstance(message, bytes):
                        # 1. Handshake wtfk (se ainda não autenticado)
                        if not self.has_shaken_hands and len(message) >= 4:
                            print("[*] Desafio de handshake recebido do servidor. Resolvendo CRC32...")
                            auth_response = SlitherHandshake.solve_challenge(message)
                            await ws.send(auth_response)
                            print("[+] Resposta de autenticação enviada com sucesso!")

                            # Envia login
                            login_pkt = SlitherProtocol.build_login_packet(self.nickname)
                            await ws.send(login_pkt)
                            self.has_shaken_hands = True
                            continue

                        # 2. Processamento de pacotes do jogo
                        parsed = SlitherProtocol.parse_packet(message)
                        if parsed["type"] == "world_setup":
                            if "game_radius" in parsed:
                                self.game_radius = float(parsed["game_radius"])
                                print(f"[+] Mundo inicializado! Raio do mapa: {self.game_radius}")

                        # 3. Decisão da IA e envio de comandos
                        if self.ai_inference:
                            # Mock/dummy observation para o frame online
                            import numpy as np
                            dummy_obs = np.zeros(32, dtype=np.float32)
                            angle_delta, boost_active = self.ai_inference.predict(dummy_obs)
                            
                            target_ang = (angle_delta * math.pi) % SlitherConfig.TWO_PI
                            angle_byte = angle_to_protocol_byte(target_ang)

                            # Envia steering e boost
                            await ws.send(SlitherProtocol.build_steering_packet(angle_byte))
                            await ws.send(SlitherProtocol.build_boost_packet(boost_active))

        except ConnectionRefusedError:
            print(f"[!] Conexão recusada em {uri}. Verifique se o servidor mock/oficial está ativo.")
        except Exception as e:
            print(f"[!] Erro de conexão ou loop online: {e}")
        finally:
            self.is_connected = False
            print("[*] Sessão online encerrada.")
