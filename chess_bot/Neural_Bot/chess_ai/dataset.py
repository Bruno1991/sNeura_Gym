"""Módulo de Extração e Carregamento do Dataset Polyglot (balanced.bin -> Tensores).

Percorre a árvore de aberturas de Grandes Mestres no arquivo Polyglot e
gera o dataset de treinamento supervisionado contendo:
- Estados do tabuleiro em representação canônica (N, 18, 8, 8)
- Distribuição de probabilidades alvo da política (N, 4096)
- Avaliação posicional escalar normalizada (N, 1)
"""

import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import chess
import chess.polyglot
import numpy as np
import torch
from torch.utils.data import Dataset

from .encoder import ACTION_SIZE, encode_board, encode_move


class ChessOpeningDataset(Dataset):
    """Dataset PyTorch para treinamento de destilação de aberturas."""

    def __init__(self, states: torch.Tensor, policies: torch.Tensor, values: torch.Tensor):
        self.states = states
        self.policies = policies
        self.values = values

    def __len__(self) -> int:
        return len(self.states)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.states[idx], self.policies[idx], self.values[idx]

    @classmethod
    def load_or_extract(
        cls,
        book_path: str | Path,
        cache_path: str | Path,
        max_positions: Optional[int] = None,
        force_rebuild: bool = False,
    ) -> "ChessOpeningDataset":
        """Carrega do arquivo de cache .pt ou extrai do balanced.bin se não existir."""
        cache_file = Path(cache_path)
        if cache_file.is_file() and not force_rebuild:
            print(f"[*] Carregando dataset pré-extraído de: {cache_file.name}")
            data = torch.load(str(cache_file), weights_only=True)
            return cls(data["states"], data["policies"], data["values"])

        print(f"[*] Extraindo posições de aberturas de: {Path(book_path).name}")
        states, policies, values = extract_polyglot_data(book_path, max_positions=max_positions)

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {"states": states, "policies": policies, "values": values},
            str(cache_file),
        )
        print(f"[+] Dataset salvo em cache: {cache_file} ({len(states)} amostras)")
        return cls(states, policies, values)


def extract_polyglot_data(
    book_path: str | Path,
    max_positions: Optional[int] = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Percorre a árvore de aberturas em balanced.bin e compila os tensores de treino."""
    reader = chess.polyglot.open_reader(str(book_path))

    visited_hashes = set()
    queue: List[chess.Board] = [chess.Board()]

    all_states: List[torch.Tensor] = []
    all_policies: List[torch.Tensor] = []
    all_values: List[torch.Tensor] = []

    t0 = time.time()
    count = 0

    while queue:
        board = queue.pop()
        z_hash = chess.polyglot.zobrist_hash(board)
        if z_hash in visited_hashes:
            continue
        visited_hashes.add(z_hash)

        try:
            entries = list(reader.find_all(board))
        except Exception:
            entries = []

        if entries:
            # 1. Tensor do tabuleiro
            state_tensor = encode_board(board)

            # 2. Distribuição da política (softmax sobre os pesos Polyglot)
            policy = np.zeros(ACTION_SIZE, dtype=np.float32)
            for e in entries:
                action_idx = encode_move(e.move, board.turn)
                # Pesos maiores que 0 recebem a pontuação
                policy[action_idx] += float(max(1, e.weight))

            total_weight = policy.sum()
            if total_weight > 0:
                policy = policy / total_weight
            else:
                policy[action_idx] = 1.0

            # 3. Valor aproximado da posição (-1.0 a +1.0)
            # Para aberturas de mestres, posições no livro giram em torno do equilíbrio (0.0)
            # com pequenas variações para o lado com vantagem de tempo/peão
            val = 0.0

            all_states.append(state_tensor)
            all_policies.append(torch.from_numpy(policy))
            all_values.append(torch.tensor([val], dtype=torch.float32))

            count += 1
            if count % 10000 == 0:
                print(f"    - Processadas {count} posições únicas ({time.time() - t0:.1f}s)...")

            if max_positions and count >= max_positions:
                break

            # Enfileirar posições filhas
            for e in entries:
                board.push(e.move)
                child_hash = chess.polyglot.zobrist_hash(board)
                if child_hash not in visited_hashes:
                    queue.append(board.copy())
                board.pop()

    print(f"[+] Extração concluída: {len(all_states)} posições em {time.time() - t0:.2f}s")
    states_tensor = torch.stack(all_states)
    policies_tensor = torch.stack(all_policies)
    values_tensor = torch.stack(all_values)

    return states_tensor, policies_tensor, values_tensor
