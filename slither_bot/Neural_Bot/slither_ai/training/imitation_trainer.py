"""Treinador por Aprendizado por Imitação (Behavior Cloning) a partir da IA especialista."""

import os
from pathlib import Path
from typing import Optional
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm

from ..models.policy_net import SlitherPolicyNet
from .dataset import ExpertDataset


class ImitationTrainer:
    """Treina a rede neural para clonar o comportamento do bot nativo do Slither.io."""

    def __init__(
        self,
        model: Optional[SlitherPolicyNet] = None,
        learning_rate: float = 1e-3,
        batch_size: int = 128,
        device: Optional[str] = None,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = (model or SlitherPolicyNet()).to(self.device)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate, weight_decay=1e-4)
        self.batch_size = batch_size

        self.mse_loss = nn.MSELoss()
        self.bce_loss = nn.BCEWithLogitsLoss()

    def train(
        self,
        dataset: ExpertDataset,
        epochs: int = 25,
        validation_split: float = 0.15,
        save_path: str = "checkpoints/best_imitation_model.pt",
    ) -> SlitherPolicyNet:
        """Executa o ciclo de treino supervisionado."""
        total_len = len(dataset)
        val_len = int(total_len * validation_split)
        train_len = total_len - val_len

        train_data, val_data = random_split(dataset, [train_len, val_len])
        train_loader = DataLoader(train_data, batch_size=self.batch_size, shuffle=True)
        val_loader = DataLoader(val_data, batch_size=self.batch_size, shuffle=False)

        print(f"[*] Iniciando treino por imitação no dispositivo: {self.device}")
        print(f"    Total de Amostras: {total_len} (Treino: {train_len}, Validação: {val_len})")
        print(f"    Épocas: {epochs} | Batch Size: {self.batch_size}")

        os.makedirs(Path(save_path).parent, exist_ok=True)
        best_val_loss = float("inf")

        for epoch in range(1, epochs + 1):
            # Fase de Treino
            self.model.train()
            train_loss_accum = 0.0

            for obs, target_angle, target_boost in train_loader:
                obs = obs.to(self.device)
                target_angle = target_angle.to(self.device)
                target_boost = target_boost.to(self.device)

                self.optimizer.zero_grad()
                pred_angle, pred_boost_logits, _ = self.model(obs)

                loss_angle = self.mse_loss(pred_angle, target_angle)
                loss_boost = self.bce_loss(pred_boost_logits, target_boost)
                total_loss = loss_angle + 0.5 * loss_boost

                total_loss.backward()
                self.optimizer.step()

                train_loss_accum += total_loss.item()

            train_loss_avg = train_loss_accum / max(1, len(train_loader))

            # Fase de Validação
            self.model.eval()
            val_loss_accum = 0.0

            with torch.no_grad():
                for obs, target_angle, target_boost in val_loader:
                    obs = obs.to(self.device)
                    target_angle = target_angle.to(self.device)
                    target_boost = target_boost.to(self.device)

                    pred_angle, pred_boost_logits, _ = self.model(obs)
                    l_angle = self.mse_loss(pred_angle, target_angle)
                    l_boost = self.bce_loss(pred_boost_logits, target_boost)
                    val_loss_accum += (l_angle + 0.5 * l_boost).item()

            val_loss_avg = val_loss_accum / max(1, len(val_loader))

            print(
                f"    [Época {epoch:02d}/{epochs:02d}] "
                f"Treino Loss: {train_loss_avg:.4f} | "
                f"Val Loss: {val_loss_avg:.4f}"
            )

            # Salva o melhor checkpoint
            if val_loss_avg < best_val_loss:
                best_val_loss = val_loss_avg
                self.model.save_model(save_path)

        print(f"[+] Treinamento por imitação finalizado com sucesso! Modelo salvo em: {save_path}")
        return self.model
