"""Exportação e inferência otimizada para implantação do bot em produção."""

from pathlib import Path
from typing import Tuple
import torch
import numpy as np

from .policy_net import SlitherPolicyNet


def export_to_torchscript(model: SlitherPolicyNet, output_path: str, input_dim: int = 32):
    """Exporta o modelo para formato standalone TorchScript (.pt) executável em C++ e Python."""
    model.eval()
    device = next(model.parameters()).device
    dummy_input = torch.randn(1, input_dim, dtype=torch.float32, device=device)
    traced_model = torch.jit.trace(model, dummy_input)
    traced_model.save(output_path)


def export_to_onnx(model: SlitherPolicyNet, output_path: str, input_dim: int = 32) -> bool:
    """Exporta o modelo PyTorch para o formato interoperável ONNX se suportado."""
    try:
        model.eval()
        device = next(model.parameters()).device
        dummy_input = torch.randn(1, input_dim, dtype=torch.float32, device=device)
        torch.onnx.export(
            model,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=["observation"],
            output_names=["angle_output", "boost_logits", "state_value"],
            dynamic_axes={"observation": {0: "batch_size"}},
        )
        return True
    except Exception as e:
        print(f"[!] Exportação ONNX não pôde ser concluída ({e}). Utilizando TorchScript nativo.")
        return False


class FastPyTorchInference:
    """Executor de inferência ultra-rápido para loop de rede de 30Hz."""

    def __init__(self, model_path: str, device: str = "cpu"):
        self.device = torch.device(device)
        self.model = SlitherPolicyNet().to(self.device)
        self.model.load_model(model_path, map_location=self.device)
        self.model.eval()

    def predict(self, observation: np.ndarray) -> Tuple[float, bool]:
        """Prediz o ângulo de manobra e a decisão de turbo."""
        return self.model.get_action(observation, deterministic=True)
