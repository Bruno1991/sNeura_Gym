"""Testes unitários para o ambiente Gymnasium SlitherEnv."""

import unittest
import numpy as np

from slither_ai.env.slither_env import SlitherEnv


class TestSlitherEnv(unittest.TestCase):
    def setUp(self):
        self.env = SlitherEnv(max_steps=50)

    def test_gym_reset_and_step(self):
        obs, info = self.env.reset()
        self.assertEqual(obs.shape, (32,))
        self.assertIn("score", info)

        action = np.array([0.2, 0.0], dtype=np.float32)
        next_obs, reward, terminated, truncated, step_info = self.env.step(action)

        self.assertEqual(next_obs.shape, (32,))
        self.assertIsInstance(reward, float)
        self.assertIsInstance(terminated, bool)
        self.assertIsInstance(truncated, bool)
        self.assertIn("score", step_info)


if __name__ == "__main__":
    unittest.main()
