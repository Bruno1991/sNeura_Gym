"""Pipeline de Treinamento e Destilação da Política Polyglot em Rede Neural.

Treina a ChessPolicyValueNet para replicar a intuição de aberturas de Grandes Mestres
do arquivo balanced.bin utilizando GPU CUDA.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, random_split

from .dataset import ChessOpeningDataset
from .model import ChessPolicyValueNet


class PolicyDistillationTrainer:
    """Treinador de destilação de política supervisionada."""

    def __init__(
        self,
        model: ChessPolicyValueNet,
        dataset: ChessOpeningDataset,
        device: Optional[str] = None,
        batch_size: int = 128,
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
    ):
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = model.to(self.device)
        self.dataset = dataset
        self.batch_size = batch_size

        # Divisão 90% treino, 10% validação
        val_size = max(100, int(0.10 * len(dataset)))
        train_size = len(dataset) - val_size
        self.train_set, self.val_set = random_split(
            dataset,
            [train_size, val_size],
            generator=torch.Generator().manual_seed(42),
        )

        self.train_loader = DataLoader(
            self.train_set,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0,
            pin_memory=(self.device.type == "cuda"),
        )
        self.val_loader = DataLoader(
            self.val_set,
            batch_size=batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=(self.device.type == "cuda"),
        )

        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=lr,
            weight_decay=weight_decay,
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer,
            T_max=10,
            eta_min=1e-5,
        )

        self.history: List[Dict[str, float]] = []

    def compute_loss(
        self,
        pred_policy_logits: torch.Tensor,
        pred_value: torch.Tensor,
        target_policy: torch.Tensor,
        target_value: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Calcula a perda combinada de política (Cross-Entropy com soft targets) e valor (MSE)."""
        log_probs = F.log_softmax(pred_policy_logits, dim=-1)
        policy_loss = -torch.sum(target_policy * log_probs, dim=-1).mean()
        value_loss = F.mse_loss(pred_value, target_value)
        total_loss = policy_loss + 0.5 * value_loss
        return total_loss, policy_loss, value_loss

    def compute_accuracy(
        self,
        pred_policy_logits: torch.Tensor,
        target_policy: torch.Tensor,
    ) -> Tuple[float, float]:
        """Calcula:
        - top1_exact: O lance mais provável da rede coincide com o lance mais provável do livro.
        - top1_in_book: O lance mais provável da rede é um dos lances aprovados pelo livro (peso > 0).
        """
        pred_top1 = torch.argmax(pred_policy_logits, dim=-1)
        target_top1 = torch.argmax(target_policy, dim=-1)

        exact_matches = (pred_top1 == target_top1).float().sum().item()

        # Verifica se o lance predito tem probabilidade > 0 no livro
        in_book = target_policy.gather(1, pred_top1.unsqueeze(1)).squeeze(1) > 1e-5
        in_book_matches = in_book.float().sum().item()

        batch_size = target_policy.size(0)
        return exact_matches / batch_size, in_book_matches / batch_size

    def train_epoch(self) -> Dict[str, float]:
        """Executa uma época completa de treinamento."""
        self.model.train()
        total_loss = 0.0
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_exact = 0.0
        total_in_book = 0.0
        num_batches = 0

        for states, policies, values in self.train_loader:
            states = states.to(self.device)
            policies = policies.to(self.device)
            values = values.to(self.device)

            self.optimizer.zero_grad()
            pred_policy, pred_val = self.model(states)

            loss, p_loss, v_loss = self.compute_loss(pred_policy, pred_val, policies, values)
            loss.backward()
            nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            exact, in_book = self.compute_accuracy(pred_policy, policies)

            total_loss += loss.item()
            total_policy_loss += p_loss.item()
            total_value_loss += v_loss.item()
            total_exact += exact
            total_in_book += in_book
            num_batches += 1

        self.scheduler.step()

        return {
            "loss": total_loss / num_batches,
            "policy_loss": total_policy_loss / num_batches,
            "value_loss": total_value_loss / num_batches,
            "top1_exact": (total_exact / num_batches) * 100.0,
            "top1_in_book": (total_in_book / num_batches) * 100.0,
        }

    def evaluate(self) -> Dict[str, float]:
        """Avalia a acurácia e perda no conjunto de validação."""
        self.model.eval()
        total_loss = 0.0
        total_exact = 0.0
        total_in_book = 0.0
        num_batches = 0

        with torch.no_grad():
            for states, policies, values in self.val_loader:
                states = states.to(self.device)
                policies = policies.to(self.device)
                values = values.to(self.device)

                pred_policy, pred_val = self.model(states)
                loss, _, _ = self.compute_loss(pred_policy, pred_val, policies, values)
                exact, in_book = self.compute_accuracy(pred_policy, policies)

                total_loss += loss.item()
                total_exact += exact
                total_in_book += in_book
                num_batches += 1

        return {
            "val_loss": total_loss / num_batches,
            "val_top1_exact": (total_exact / num_batches) * 100.0,
            "val_top1_in_book": (total_in_book / num_batches) * 100.0,
        }

    def train(
        self,
        num_epochs: int = 5,
        save_path: Optional[str | Path] = None,
        onnx_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """Treina o modelo por N épocas e salva os melhores pesos."""
        print(f"\n[*] Iniciando treinamento no dispositivo: {self.device.type.upper()}")
        print(f"[*] Total amostras: {len(self.dataset)} (Treino: {len(self.train_set)}, Validação: {len(self.val_set)})")
        print(f"[*] Batch size: {self.batch_size} | Épocas: {num_epochs}")
        print("-" * 70)

        best_val_acc = 0.0

        for epoch in range(1, num_epochs + 1):
            t0 = time.time()
            train_metrics = self.train_epoch()
            val_metrics = self.evaluate()
            elapsed = time.time() - t0

            val_acc = val_metrics["val_top1_in_book"]
            epoch_data = {
                "epoch": epoch,
                "elapsed": elapsed,
                **train_metrics,
                **val_metrics,
            }
            self.history.append(epoch_data)

            is_best = val_acc > best_val_acc
            marker = " (Novo Recorde!)" if is_best else ""

            print(
                f"Época [{epoch:02d}/{num_epochs:02d}] ({elapsed:.1f}s) | "
                f"Loss: {train_metrics['loss']:.4f} | "
                f"Treino In-Book: {train_metrics['top1_in_book']:.1f}% | "
                f"Val Loss: {val_metrics['val_loss']:.4f} | "
                f"Val In-Book: {val_acc:.1f}%{marker}"
            )

            if is_best and save_path:
                best_val_acc = val_acc
                self.model.save_weights(save_path)

        if onnx_path:
            try:
                self.model.export_onnx(onnx_path)
                print(f"[+] Modelo ONNX exportado para: {onnx_path}")
            except Exception as e:
                print(f"[!] Aviso: falha ao exportar ONNX: {e}")

        return {
            "best_val_in_book_acc": best_val_acc,
            "final_epoch": num_epochs,
            "history": self.history,
        }
