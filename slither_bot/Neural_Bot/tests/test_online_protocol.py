"""Testes unitários para o protocolo e handshake criptográfico oficial."""

import unittest

from slither_ai.online.crypto import SlitherHandshake
from slither_ai.online.protocol import SlitherProtocol


class TestOnlineProtocol(unittest.TestCase):
    def test_handshake_challenge(self):
        # Desafio sintético de 6 bytes
        sample_challenge = bytes([10, 20, 30, 40, 50, 60])
        response = SlitherHandshake.solve_challenge(sample_challenge)

        self.assertEqual(len(response), 8, "Token de autenticação de handshake deve ter 8 bytes.")
        self.assertTrue(all(65 <= b <= 122 for b in response), "Todos os caracteres devem ser alfanuméricos ASCII.")

    def test_packet_building(self):
        steering_pkt = SlitherProtocol.build_steering_packet(angle_byte=125)
        self.assertEqual(len(steering_pkt), 1)
        self.assertEqual(steering_pkt[0], 125)

        boost_on = SlitherProtocol.build_boost_packet(is_boosting=True)
        self.assertEqual(boost_on[0], 253)

        boost_off = SlitherProtocol.build_boost_packet(is_boosting=False)
        self.assertEqual(boost_off[0], 254)


if __name__ == "__main__":
    unittest.main()
