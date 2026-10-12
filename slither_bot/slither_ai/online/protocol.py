"""Parser e serializador do protocolo binário Slither v5+ (Main.as linhas 33460-36650)."""

import struct
from typing import Any, Dict, List, Optional, Tuple


class SlitherProtocol:
    """Serialização e deserialização de pacotes do servidor oficial."""

    @staticmethod
    def build_login_packet(nick: str = "NeuraBot", skin: int = 0) -> bytes:
        """Monta o pacote de login/spawn inicial."""
        nick_bytes = nick.encode("utf-8")[:24]
        packet = bytearray()
        packet.append(ord("s"))  # Opcode de spawn inicial
        packet.append(1)         # Protocol version 5+ flag
        packet.append(skin)      # Skin selecionada
        packet.extend(nick_bytes)
        return bytes(packet)

    @staticmethod
    def build_steering_packet(angle_byte: int) -> bytes:
        """Monta pacote de 1 byte de direção (protocol v5+)."""
        byte_val = max(0, min(251, angle_byte))
        return bytes([byte_val])

    @staticmethod
    def build_boost_packet(is_boosting: bool) -> bytes:
        """Monta pacote de turbo: 253 para ligar, 254 para desligar."""
        opcode = 253 if is_boosting else 254
        return bytes([opcode])

    @staticmethod
    def parse_packet(raw_bytes: bytes) -> Dict[str, Any]:
        """Identifica e extrai o opcode e payload básico do pacote recebido."""
        if not raw_bytes:
            return {"type": "empty"}

        opcode_char = chr(raw_bytes[0])
        payload = raw_bytes[1:]

        if opcode_char == "a":
            # Configuração inicial do mundo
            if len(payload) >= 15:
                grd = (payload[0] << 16) | (payload[1] << 8) | payload[2]
                sector_size = (payload[5] << 8) | payload[6]
                return {
                    "type": "world_setup",
                    "opcode": "a",
                    "game_radius": grd,
                    "sector_size": sector_size,
                }
            return {"type": "world_setup", "opcode": "a"}

        elif opcode_char in ("g", "n", "G", "N", "+"):
            return {"type": "snake_spawn", "opcode": opcode_char, "raw_len": len(payload)}

        elif opcode_char in ("e", "E", "3", "4", "5"):
            return {"type": "snake_move", "opcode": opcode_char, "raw_len": len(payload)}

        elif opcode_char in ("d", "7"):
            return {"type": "snake_dead", "opcode": opcode_char, "raw_len": len(payload)}

        elif opcode_char in ("s", "b", "f"):
            return {"type": "food_spawn", "opcode": opcode_char, "raw_len": len(payload)}

        elif opcode_char == "F":
            return {"type": "food_eaten", "opcode": "F"}

        elif opcode_char == "l":
            return {"type": "leaderboard", "opcode": "l"}

        return {"type": "unknown", "opcode": opcode_char, "raw_len": len(payload)}
