"""Testes unitários para o modelo de rede neural SlitherPolicyNet."""

import unittest
import torch
import numpy as np

from slither_ai.models.policy_net import SlitherPolicyNet


class TestModel(unittest.TestCase):
    def setUp(self):
        self.model = SlitherPolicyNet()

    def test_forward_pass_shapes(self):
        batch_size = 4
        dummy_input = torch.randn(batch_size, 32)
        angle, boost_logits, value = self.model(dummy_input)

        self.assertEqual(angle.shape, (batch_size, 1))
        self.assertEqual(boost_logits.shape, (batch_size, 1))
        self.assertEqual(value.shape, (batch_size, 1))
        self.assertTrue(torch.all(angle >= -1.0) and torch.all(angle <= 1.0))

    def test_get_action(self):
        dummy_obs = np.random.randn(32).astype(np.float32)
        angle_val, boost_val = self.model.get_action(dummy_obs, deterministic=True)

        self.assertIsInstance(angle_val, float)
        self.assertIsInstance(boost_val, bool)
        self.assertTrue(-1.0 <= angle_val <= 1.0)


if __name__ == "__main__":
    unittest.main()
