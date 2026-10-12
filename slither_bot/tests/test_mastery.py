"""Testes unitários para o motor de maestria contínua 24/7."""

import os
import shutil
import tempfile
import pytest
import torch

from slither_ai.training.mastery_trainer import MasteryCurriculumEngine


@pytest.fixture
def temp_checkpoint_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_mastery_engine_init(temp_checkpoint_dir):
    engine = MasteryCurriculumEngine(
        target_mastery=90.0,
        eval_interval=2,
        save_dir=temp_checkpoint_dir,
        device="cpu",
    )
    assert engine.target_mastery == 90.0
    assert engine.eval_interval == 2
    assert engine.device.type == "cpu"
    assert engine.model is not None


def test_mastery_rollout_and_benchmark(temp_checkpoint_dir):
    engine = MasteryCurriculumEngine(
        target_mastery=80.0,
        eval_interval=1,
        save_dir=temp_checkpoint_dir,
        device="cpu",
    )

    # 1. Teste de coleta de rollout com poucos passos para rapidez
    obs_b, act_b, old_log_p_b, adv_b, ret_b, ticks, fps = engine._collect_curriculum_rollout(steps=32)
    assert obs_b.shape == (32, 32)
    assert act_b.shape == (32, 2)
    assert adv_b.shape == (32,)
    assert ret_b.shape == (32,)
    assert ticks == 32
    assert fps > 0

    # 2. Teste de otimização PPO
    p_loss, v_loss = engine._optimize_ppo(
        obs_b, act_b, old_log_p_b, adv_b, ret_b, epochs=1, batch_size=16
    )
    assert isinstance(p_loss, float)
    assert isinstance(v_loss, float)

    # 3. Teste de avaliação determinística de maestria
    m_data = engine._evaluate_mastery_benchmark(episodes=2, max_steps=50)
    assert "mastery_index" in m_data
    assert 0.0 <= m_data["mastery_index"] <= 100.0
    assert "avg_score" in m_data
    assert "avg_kills" in m_data
    assert "wall_rate" in m_data

    # 4. Teste de salvamento de pesos
    engine._save_master_weights()
    assert os.path.isfile(os.path.join(temp_checkpoint_dir, "master_bot_model.pt"))
    assert os.path.isfile(os.path.join(temp_checkpoint_dir, "master_bot_model_traced.pt"))
