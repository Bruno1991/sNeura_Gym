"""Handshake criptográfico e autenticação oficial do Slither.io (Main.as linhas 36395-36430)."""

import binascii
import random
from typing import Union


class SlitherHandshake:
    """Implementa o cálculo do desafio wtfk e resposta CRC32 do protocolo oficial."""

    @staticmethod
    def solve_challenge(challenge_payload: Union[bytes, bytearray]) -> bytes:
        """Decifra o desafio do servidor oficial e retorna o token de autenticação de 8 bytes."""
        length = len(challenge_payload)
        if length < 4:
            raise ValueError(f"Payload de desafio muito curto: {length} bytes")

        # 1. Rotação modular dos bytes
        dec_len = length - 1
        dec = bytearray(dec_len)
        for i in range(dec_len):
            dec[i] = (challenge_payload[i + 1] + i * 3) % 256

        # 2. Cálculo do Checksum CRC32
        crc_val = binascii.crc32(dec) & 0xFFFFFFFF
        crc_bytes = crc_val.to_bytes(4, byteorder="big", signed=False)

        # 3. Conversão para sequência alfanumérica pseudo-aleatória
        response = bytearray()
        shift = 12

        for i in range(4):
            b = crc_bytes[i]
            hi = b // 16
            lo = b % 16

            # Primeiro caractere (nibble alto)
            case_offset1 = 32 if random.random() < 0.5 else 0
            char1 = 65 + case_offset1 + ((hi + shift) % 26)
            response.append(char1)
            shift += 11

            # Segundo caractere (nibble baixo)
            case_offset2 = 32 if random.random() < 0.5 else 0
            char2 = 65 + case_offset2 + ((lo + shift) % 26)
            response.append(char2)
            shift += 11

        return bytes(response)
