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
from typing import Any, Dict, List, Optional, Tuple

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

    @classmethod
    def load_or_extract_multi(
        cls,
        book_paths: List[str | Path],
        cache_path: str | Path,
        max_positions: Optional[int] = None,
        force_rebuild: bool = False,
    ) -> "ChessOpeningDataset":
        """Carrega do cache ou compila múltiplos livros Polyglot (.bin) unificados."""
        cache_file = Path(cache_path)
        if cache_file.is_file() and not force_rebuild:
            print(f"[*] Carregando dataset multi-livro pré-extraído de: {cache_file.name}")
            data = torch.load(str(cache_file), weights_only=True)
            return cls(data["states"], data["policies"], data["values"])

        print(f"[*] Iniciando extração multi-livro de {len(book_paths)} fontes Polyglot...")
        states, policies, values = extract_multi_polyglot_data(book_paths, max_positions=max_positions)

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {"states": states, "policies": policies, "values": values},
            str(cache_file),
        )
        print(f"[+] Dataset multi-livro salvo em cache: {cache_file} ({len(states):,} amostras)")
        return cls(states, policies, values)


def extract_polyglot_data(
    book_path: str | Path,
    max_positions: Optional[int] = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Percorre a árvore de aberturas em balanced.bin e compila os tensores de treino."""
    return extract_multi_polyglot_data([book_path], max_positions=max_positions)


def extract_multi_polyglot_data(
    book_paths: List[str | Path],
    max_positions: Optional[int] = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Percorre múltiplos livros Polyglot (.bin) unificando estados únicos e somando pesos dos lances.
    
    Permite fundir a teoria de Grandes Mestres (balanced.bin) com as refutações de iniciantes (beginner.bin),
    damas prematuras (quick_queen.bin), gambitos (gambit.bin), ataques (aggressive.bin) e flancos (nakamura.bin, offbeat.bin).
    """
    t0 = time.time()
    # Mapeamento: z_hash -> {"board": chess.Board, "moves": {chess.Move: weight}}
    position_map: Dict[int, Dict[str, Any]] = {}

    for b_path in book_paths:
        p = Path(b_path)
        if not p.is_file():
            print(f"[!] Livro não encontrado: {p}, ignorando...")
            continue

        print(f"[*] Processando livro: {p.name}...")
        try:
            reader = chess.polyglot.open_reader(str(p))
        except Exception as e:
            print(f"[!] Erro ao abrir {p.name}: {e}")
            continue

        queue: List[chess.Board] = [chess.Board()]
        book_visited = set()

        while queue:
            board = queue.pop()
            z_hash = chess.polyglot.zobrist_hash(board)
            if z_hash in book_visited:
                continue
            book_visited.add(z_hash)

            try:
                entries = list(reader.find_all(board))
            except Exception:
                entries = []

            if entries:
                if z_hash not in position_map:
                    if max_positions and len(position_map) >= max_positions:
                        break
                    position_map[z_hash] = {
                        "board": board.copy(),
                        "moves": {},
                    }

                for e in entries:
                    cur_w = position_map[z_hash]["moves"].get(e.move, 0.0)
                    position_map[z_hash]["moves"][e.move] = cur_w + float(max(1, e.weight))

                # Enfileirar ramos filhos
                for e in entries:
                    board.push(e.move)
                    child_hash = chess.polyglot.zobrist_hash(board)
                    if child_hash not in book_visited:
                        queue.append(board.copy())
                    board.pop()

        print(f"    - Livro {p.name} adicionado. Total acumulado: {len(position_map):,} posições.")
        if max_positions and len(position_map) >= max_positions:
            break

    print(f"[*] Convertendo {len(position_map):,} posições para Tensores PyTorch...")
    all_states: List[torch.Tensor] = []
    all_policies: List[torch.Tensor] = []
    all_values: List[torch.Tensor] = []

    for idx_item, (z_hash, data) in enumerate(position_map.items()):
        board = data["board"]
        moves_dict = data["moves"]

        state_tensor = encode_board(board)

        policy = np.zeros(ACTION_SIZE, dtype=np.float32)
        for move, weight in moves_dict.items():
            action_idx = encode_move(move, board.turn)
            policy[action_idx] += weight

        total_w = policy.sum()
        if total_w > 0:
            policy = policy / total_w
        else:
            policy[action_idx] = 1.0

        val = 0.0

        all_states.append(state_tensor)
        all_policies.append(torch.from_numpy(policy))
        all_values.append(torch.tensor([val], dtype=torch.float32))

        if (idx_item + 1) % 25000 == 0:
            print(f"    - Codificados {idx_item + 1:,} tensores ({time.time() - t0:.1f}s)...")

    print(f"[+] Multi-Livro Polyglot compilado com sucesso: {len(all_states):,} posições em {time.time() - t0:.2f}s!")
    states_tensor = torch.stack(all_states) if all_states else torch.empty((0, 18, 8, 8))
    policies_tensor = torch.stack(all_policies) if all_policies else torch.empty((0, ACTION_SIZE))
    values_tensor = torch.stack(all_values) if all_values else torch.empty((0, 1))

    return states_tensor, policies_tensor, values_tensor
