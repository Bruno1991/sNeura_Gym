"""Treina a rede neural por Aprendizado por Imitação usando a IA especialista nativa."""

import sys
from pathlib import Path

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slither_ai.models.inference import export_to_onnx, export_to_torchscript
from slither_ai.models.policy_net import SlitherPolicyNet
from slither_ai.training.dataset import ExpertDataset
from slither_ai.training.imitation_trainer import ImitationTrainer


def main():
    print("=============================================================")
    print("    Slither AI - Treinamento por Imitação (Behavior Cloning)")
    print("=============================================================")

    # 1. Coleta de amostras do Expert Bot
    num_samples = 6000
    dataset = ExpertDataset.collect_from_simulation(num_samples=num_samples)

    # 2. Inicialização do modelo e treinador
    model = SlitherPolicyNet()
    trainer = ImitationTrainer(model=model, learning_rate=1e-3, batch_size=128)

    # 3. Treinamento supervisionado
    model_path = "checkpoints/best_imitation_model.pt"
    trainer.train(dataset, epochs=15, validation_split=0.15, save_path=model_path)

    # 4. Exportação para TorchScript e ONNX
    ts_path = "checkpoints/best_imitation_model_traced.pt"
    export_to_torchscript(model, ts_path)
    print(f"[+] Modelo TorchScript exportado com sucesso: {ts_path}")

    onnx_path = "checkpoints/best_imitation_model.onnx"
    export_to_onnx(model, onnx_path)

    print("=============================================================")
    print("    Treinamento Concluído com Sucesso!")
    print("=============================================================\n")


if __name__ == "__main__":
    main()
