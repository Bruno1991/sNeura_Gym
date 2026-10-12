"""Testes unitários para o motor de física do Slither.io."""

import math
import unittest

from slither_ai.config import SlitherConfig
from slither_ai.core.entities import Snake
from slither_ai.core.physics import SlitherPhysics


class TestSlitherPhysics(unittest.TestCase):
    def setUp(self):
        self.snake = Snake(snake_id=1, x=0.0, y=0.0, angle=0.0)

    def test_turn_rate_scaling(self):
        # Cobras maiores devem ter taxa de giro menor (mang)
        small_turn = SlitherPhysics.calculate_turn_rate(self.snake)
        
        large_snake = Snake(snake_id=2, x=0.0, y=0.0, initial_score=150.0)
        large_turn = SlitherPhysics.calculate_turn_rate(large_snake)
        
        self.assertGreater(small_turn, large_turn, "Cobra menor deve manobrar mais rápido que cobra gigante.")

    def test_forward_motion(self):
        # Avança 1 segundo em linha reta apontando para o leste (angle = 0)
        dt = 0.033
        prev_x = self.snake.x
        SlitherPhysics.update_snake_motion(self.snake, dt)
        
        self.assertGreater(self.snake.x, prev_x)
        self.assertEqual(len(self.snake.history_points), int(self.snake.score * 3) + 1)

    def test_boost_speed_and_poop(self):
        # Ativa boost em cobra com massa suficiente
        self.snake.score = 25.0
        self.snake.is_boosting = True
        
        poop_dropped = False
        for _ in range(10):
            dropped = SlitherPhysics.update_snake_motion(self.snake, 0.033)
            if dropped:
                poop_dropped = True
                break

        self.assertGreater(self.snake.speed, SlitherConfig.SPEED_NORMAL)
        self.assertTrue(poop_dropped, "Aceleração contínua deve soltar massa (poop).")


if __name__ == "__main__":
    unittest.main()
