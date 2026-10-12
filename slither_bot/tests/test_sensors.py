"""Testes unitários para o extrator sensorial LIDAR e radar de observação."""

import unittest
import numpy as np

from slither_ai.core.entities import Food, Snake
from slither_ai.env.sensors import SlitherSensors


class TestSensors(unittest.TestCase):
    def test_observation_shape_and_bounds(self):
        snake = Snake(snake_id=1, x=0.0, y=0.0, angle=0.0)
        enemy = Snake(snake_id=2, x=150.0, y=0.0)
        food = Food(id=1, x=80.0, y=0.0)

        obs = SlitherSensors.get_observation(
            snake=snake,
            all_snakes=[snake, enemy],
            foods=[food],
            arena_radius=2000.0,
        )

        self.assertIsInstance(obs, np.ndarray)
        self.assertEqual(obs.shape, (32,))
        self.assertTrue(np.all(obs >= -1.0) and np.all(obs <= 1.0), "Observações devem estar normalizadas entre -1 e 1.")


if __name__ == "__main__":
    unittest.main()
