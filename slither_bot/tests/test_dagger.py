"""Testes unitários para o pipeline de Destilação Ativa DAgger."""

import os
import shutil
import tempfile
import unittest

from slither_ai.models.policy_net import SlitherPolicyNet
from slither_ai.training.dagger_trainer import DAggerTrainer


class TestDAggerTrainer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.model = SlitherPolicyNet()
        self.trainer = DAggerTrainer(model=self.model, batch_size=32, device="cpu")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dagger_training_cycle(self):
        """Valida se o ciclo DAgger coleta dados com o bot especialista e treina os pesos."""
        result = self.trainer.train_dagger(
            total_iterations=2,
            steps_per_iteration=250,
            epochs_per_iteration=1,
            save_dir=self.temp_dir,
        )

        # 1. Verifica integridade do histórico
        self.assertIn("history", result)
        self.assertEqual(len(result["history"]), 2)
        self.assertGreaterEqual(result["total_samples"], 500)

        # 2. Verifica se os pesos universais foram salvos
        imitation_path = os.path.join(self.temp_dir, "best_imitation_model.pt")
        ppo_warmstart_path = os.path.join(self.temp_dir, "best_ppo_model.pt")
        traced_path = os.path.join(self.temp_dir, "best_imitation_model_traced.pt")

        self.assertTrue(os.path.isfile(imitation_path))
        self.assertTrue(os.path.isfile(ppo_warmstart_path))
        self.assertTrue(os.path.isfile(traced_path))

        # 3. Testa carregamento dos pesos gerados
        new_model = SlitherPolicyNet()
        new_model.load_model(imitation_path)
        self.assertIsNotNone(new_model)


if __name__ == "__main__":
    unittest.main()
