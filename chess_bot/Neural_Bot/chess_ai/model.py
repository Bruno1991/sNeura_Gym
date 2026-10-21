"""Arquitetura da Rede Neural Convolucional Residual com Dupla Cabeça (Policy-Value ResNet).

Inspirada na arquitetura AlphaZero / Leela Chess Zero:
- Entrada: Tensor (B, 18, 8, 8) representando o tabuleiro na forma canônica.
- Backbone: Blocos residuais com convoluções 3x3 e BatchNorm.
- Cabeça de Política (Policy Head): Prediz a distribuição de probabilidade de lances (4096 ações).
- Cabeça de Valor (Value Head): Prediz a avaliação posicional escalar entre -1.0 e +1.0.
"""

import os
import time
from pathlib import Path
from typing import Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from .encoder import ACTION_SIZE, NUM_CHANNELS


class SqueezeExcitationBlock(nn.Module):
    """Módulo Squeeze-and-Excitation (SE-Attention) para recalibração de canais."""

    def __init__(self, channels: int, reduction: int = 4):
        super().__init__()
        self.fc1 = nn.Linear(channels, channels // reduction, bias=False)
        self.fc2 = nn.Linear(channels // reduction, channels, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, _, _ = x.size()
        # Squeeze: Global Average Pooling (B, C)
        w = F.adaptive_avg_pool2d(x, 1).view(b, c)
        # Excitation: MLP com sigmoid
        w = F.relu(self.fc1(w))
        w = torch.sigmoid(self.fc2(w)).view(b, c, 1, 1)
        return x * w


class ResidualBlock(nn.Module):
    """Bloco residual padrão com convoluções 3x3 e BatchNorm."""

    def __init__(self, channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = F.relu(out + residual)
        return out


class SEResidualBlock(nn.Module):
    """Bloco residual aprimorado com Squeeze-and-Excitation (SE-ResNet)."""

    def __init__(self, channels: int, reduction: int = 4):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)
        self.se = SqueezeExcitationBlock(channels, reduction=reduction)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = self.se(out)
        out = F.relu(out + residual)
        return out


class ChessPolicyValueNet(nn.Module):
    """Rede Neural de Dupla Cabeça para Política e Avaliação de Posições."""

    def __init__(
        self,
        in_channels: int = NUM_CHANNELS,
        num_channels: int = 128,
        num_blocks: int = 4,
        action_size: int = ACTION_SIZE,
        use_se: bool = False,
    ):
        super().__init__()
        self.in_channels = in_channels
        self.num_channels = num_channels
        self.num_blocks = num_blocks
        self.action_size = action_size
        self.use_se = use_se

        # Camada Convolucional de Entrada
        self.conv_in = nn.Conv2d(in_channels, num_channels, kernel_size=3, padding=1, bias=False)
        self.bn_in = nn.BatchNorm2d(num_channels)

        # Backbone Residual (Padrão ou SE-ResNet)
        block_cls = SEResidualBlock if use_se else ResidualBlock
        self.res_blocks = nn.ModuleList([block_cls(num_channels) for _ in range(num_blocks)])

        # Cabeça de Política (Policy Head)
        self.policy_conv = nn.Conv2d(num_channels, 32, kernel_size=1, bias=False)
        self.policy_bn = nn.BatchNorm2d(32)
        self.policy_fc = nn.Linear(32 * 8 * 8, action_size)

        # Cabeça de Valor (Value Head)
        self.value_conv = nn.Conv2d(num_channels, 8, kernel_size=1, bias=False)
        self.value_bn = nn.BatchNorm2d(8)
        self.value_fc1 = nn.Linear(8 * 8 * 8, 128)
        self.value_fc2 = nn.Linear(128, 1)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Passagem direta pela rede.
        
        Retorna:
            policy_logits: (B, 4096) logits não normalizados de lances.
            value: (B, 1) avaliação escalar no intervalo [-1.0, 1.0].
        """
        # Entrada
        out = F.relu(self.bn_in(self.conv_in(x)))

        # Blocos Residuais
        for block in self.res_blocks:
            out = block(out)

        # Cabeça de Política
        p = F.relu(self.policy_bn(self.policy_conv(out)))
        p = p.flatten(start_dim=1)
        policy_logits = self.policy_fc(p)

        # Cabeça de Valor
        v = F.relu(self.value_bn(self.value_conv(out)))
        v = v.flatten(start_dim=1)
        v = F.relu(self.value_fc1(v))
        value = torch.tanh(self.value_fc2(v))

        return policy_logits, value

    def save_weights(self, path: str | Path):
        """Salva os pesos do modelo em arquivo .pt com escrita atômica e proteção contra locks."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        temp_p = p.with_name(f"{p.stem}_{os.getpid()}_{time.time_ns()}.tmp")
        payload = {
            "state_dict": self.state_dict(),
            "num_channels": self.num_channels,
            "num_blocks": self.num_blocks,
            "in_channels": self.in_channels,
            "action_size": self.action_size,
            "use_se": self.use_se,
        }
        for attempt in range(5):
            try:
                torch.save(payload, str(temp_p))
                temp_p.replace(p)
                return
            except Exception:
                if attempt == 4:
                    try:
                        torch.save(payload, str(p))
                        return
                    except Exception:
                        pass
                time.sleep(0.1 * (attempt + 1))
            finally:
                if temp_p.is_file():
                    try:
                        temp_p.unlink()
                    except Exception:
                        pass

    @classmethod
    def load_weights(cls, path: str | Path, device: str = "cpu") -> "ChessPolicyValueNet":
        """Carrega os pesos salvos em arquivo .pt."""
        checkpoint = torch.load(str(path), map_location=device, weights_only=True)
        model = cls(
            in_channels=checkpoint.get("in_channels", NUM_CHANNELS),
            num_channels=checkpoint.get("num_channels", 128),
            num_blocks=checkpoint.get("num_blocks", 4),
            action_size=checkpoint.get("action_size", ACTION_SIZE),
            use_se=checkpoint.get("use_se", False),
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.to(device)
        model.eval()
        return model

    def export_onnx(self, path: str | Path):
        """Exporta o modelo para o formato universal ONNX."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        device = next(self.parameters()).device
        dummy_input = torch.randn(1, self.in_channels, 8, 8, device=device)
        self.eval()
        torch.onnx.export(
            self,
            dummy_input,
            str(p),
            input_names=["board_state"],
            output_names=["policy_logits", "value"],
            dynamic_axes={"board_state": {0: "batch_size"}, "policy_logits": {0: "batch_size"}, "value": {0: "batch_size"}},
            opset_version=14,
        )
