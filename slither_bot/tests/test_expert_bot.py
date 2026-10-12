"""Testes unitários para o bot nativo do Slither.io (SlitherNativeBot)."""

import math
import unittest

from slither_ai.core.entities import Food, Snake
from slither_ai.core.expert_bot import SlitherNativeBot


class TestExpertBot(unittest.TestCase):
    def setUp(self):
        self.bot_snake = Snake(snake_id=1, x=0.0, y=0.0, angle=0.0, is_bot=True)
        self.bot = SlitherNativeBot(self.bot_snake)

    def test_foraging_towards_food(self):
        # Comida localizada em (100, 0)
        food = Food(id=1, x=100.0, y=0.0)
        self.bot.update_decision(
            all_snakes=[self.bot_snake],
            foods=[food],
            current_time_sec=10.0,
            arena_radius=2000.0,
        )

        # O bot deve apontar para o ângulo 0 rad (leste) em direção à comida
        self.assertAlmostEqual(self.bot_snake.target_angle, 0.0, delta=0.1)

    def test_avoidance_steering(self):
        # Outra cobra com obstáculo logo à frente da cabeça do bot em (50, 0)
        enemy = Snake(snake_id=2, x=200.0, y=200.0)
        enemy.segments[0].x = 50.0
        enemy.segments[0].y = 0.0

        self.bot.update_decision(
            all_snakes=[self.bot_snake, enemy],
            foods=[],
            current_time_sec=1.0,
            arena_radius=2000.0,
        )

        # O bot deve desviar tangencialmente (ângulo diferente de 0.0)
        self.assertNotAlmostEqual(self.bot_snake.target_angle, 0.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
