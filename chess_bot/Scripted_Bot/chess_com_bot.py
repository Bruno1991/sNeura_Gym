"""Emulador Dinâmico de Bots do Chess.com (ChessComBot).

Permite carregar qualquer um dos 217 bots oficiais do aplicativo Chess.com
a partir dos metadados extraídos em s_ADB_Tools/bots_data.json e dos livros
Polyglot (.bin) descompilados dos assets.

Suporta:
- Seleção por Elo específico (ex: --elo 2500, --elo 1500, --elo 2800)
- Seleção por nome de bot (ex: --bot Nelson, --bot Hikaru, --bot Martin)
- Calibração automática de profundidade e taxa de erro proporcional ao rating
- Frases de diálogo originais (provocações, saudações e reações)
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.polyglot

from engine.evaluation import evaluate_board
from engine.search import AlphaBetaSearcher


class ChessComBot:
    """Emulador universal de bots do Chess.com com calibração por Elo."""

    def __init__(
        self,
        target_elo: Optional[int] = None,
        bot_name: Optional[str] = None,
        scripted_bot_dir: Optional[Path] = None,
        s_adb_tools_dir: Optional[Path] = None,
    ):
        self.scripted_bot_dir = scripted_bot_dir or Path(__file__).resolve().parent
        self.s_adb_tools_dir = s_adb_tools_dir or Path("C:/dev/s_ADB_Tools")
        self.assets_dir = self.s_adb_tools_dir / "decompiled_sources" / "com.chess" / "app" / "src" / "main" / "assets"
        self.fallback_assets_dir = self.scripted_bot_dir / "assets"

        self.bots_data_file = self.s_adb_tools_dir / "bots_data.json"
        self.profile: Dict[str, Any] = self._resolve_bot_profile(target_elo, bot_name)

        self.name: str = self.profile.get("name", "Maximum")
        self.username: str = self.profile.get("username", "Komodo25")
        self.rating: int = int(self.profile.get("rating", 3200))
        self.group_name: str = self.profile.get("groupName", "Engine")
        self.description: str = self.profile.get("description", "")
        self.phrases: Dict[str, str] = self.profile.get("phraseList", {})

        # Calibrar motor com base no Elo
        self.calibrated_depth, self.blunder_rate = self._calibrate_engine_for_elo(self.rating)

        # Inicializar busca Alpha-Beta PeSTO
        self.searcher = AlphaBetaSearcher(max_depth=self.calibrated_depth, max_time_seconds=2.0)

        # Inicializar Livro de Abertura Polyglot
        self.polyglot_reader: Optional[chess.polyglot.MemoryMappedReader] = None
        self.book_name = self.profile.get("book", "balanced")
        self._init_polyglot_book()

    def _resolve_bot_profile(self, target_elo: Optional[int], bot_name: Optional[str]) -> Dict[str, Any]:
        """Localiza o bot correspondente ao Elo ou nome solicitado."""
        all_bots: List[Dict[str, Any]] = []

        if self.bots_data_file.is_file():
            try:
                with open(self.bots_data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for g in data.get("botGroups", []):
                        g_name = g.get("name", "Geral")
                        for b in g.get("botPersonalities", []):
                            b_copy = dict(b)
                            b_copy["groupName"] = g_name
                            all_bots.append(b_copy)
            except Exception as e:
                print(f"[!] Aviso ao ler bots_data.json: {e}")

        if not all_bots:
            # Fallback seguro para o Maximum 3200 local
            default_profile_file = self.fallback_assets_dir / "bot_3200_profile.json"
            if default_profile_file.is_file():
                try:
                    with open(default_profile_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return {
                "name": "Maximum",
                "username": "Komodo25",
                "rating": 3200,
                "book": "balanced",
                "phraseList": {"greeting": "Pronto para o confronto máximo (Rating 3200)."},
            }

        # 1. Se informou nome de bot específico
        if bot_name:
            query = bot_name.strip().lower()
            # Match exato
            for b in all_bots:
                if b.get("name", "").lower() == query or b.get("username", "").lower() == query:
                    return b
            # Match por substring
            for b in all_bots:
                if query in b.get("name", "").lower() or query in b.get("username", "").lower():
                    return b

        # 2. Se informou Elo desejado
        if target_elo is not None:
            # Encontrar o bot com rating mais próximo
            best_bot = min(all_bots, key=lambda b: abs(int(b.get("rating", 1500)) - target_elo))
            return best_bot

        # Padrão: Maximum 3200 se não especificado
        for b in all_bots:
            if b.get("name") == "Maximum" or int(b.get("rating", 0)) == 3200:
                return b

        return all_bots[-1]

    def _calibrate_engine_for_elo(self, elo: int) -> Tuple[int, float]:
        """Calcula profundidade de busca e taxa de blunder proporcional ao Elo."""
        if elo <= 500:
            return 1, 0.50   # Iniciante total (Martin = 250): blunders frequentes
        elif elo <= 900:
            return 1, 0.30   # Principiante (Aron = 700)
        elif elo <= 1400:
            return 2, 0.12   # Intermediário (Nelson = 1300)
        elif elo <= 1900:
            return 2, 0.04   # Avançado (Pablo = 1600 / GothamChess = 1800)
        elif elo <= 2500:
            return 3, 0.00   # Mestre / IM (Luk.AI = 2500)
        else:
            return 3, 0.00   # Super GM / Engine (Hikaru = 2820 / Maximum = 3200)

    def _init_polyglot_book(self):
        """Carrega o livro Polyglot (.bin) correspondente."""
        book_candidates = []
        if self.book_name:
            clean_name = self.book_name.lower().replace(".bin", "")
            book_candidates.append(self.assets_dir / f"{clean_name}.bin")
            book_candidates.append(self.fallback_assets_dir / f"{clean_name}.bin")

        # Fallbacks
        book_candidates.append(self.fallback_assets_dir / "balanced.bin")
        book_candidates.append(self.assets_dir / "balanced.bin")

        for cand in book_candidates:
            if cand.is_file():
                try:
                    self.polyglot_reader = chess.polyglot.open_reader(str(cand))
                    self.active_book_path = cand
                    return
                except Exception:
                    pass

        self.polyglot_reader = None
        self.active_book_path = None

    def get_book_move(self, board: chess.Board) -> Optional[Tuple[chess.Move, int]]:
        """Busca movimento no livro Polyglot do bot."""
        if not self.polyglot_reader:
            return None

        try:
            entries = list(self.polyglot_reader.find_all(board))
            if not entries:
                return None

            weights = [e.weight for e in entries]
            total_w = sum(weights)
            if total_w > 0:
                chosen = random.choices(entries, weights=weights, k=1)[0]
                return chosen.move, chosen.weight
            return entries[0].move, entries[0].weight
        except Exception:
            return None

    def get_best_move(
        self,
        board: chess.Board,
        max_depth: Optional[int] = None,
        max_time_seconds: Optional[float] = None,
    ) -> Tuple[Optional[chess.Move], Dict[str, Any]]:
        """Determina o melhor lance do bot de acordo com o seu perfil de Elo."""
        if board.is_game_over():
            return None, {"source": "game_over"}

        # 1. Consulta ao Livro de Abertura Polyglot oficial
        book_res = self.get_book_move(board)
        if book_res is not None:
            move, weight = book_res
            return move, {
                "source": "book",
                "book": self.active_book_path.name if self.active_book_path else "polyglot",
                "weight": weight,
                "san": board.san(move),
            }

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None, {"source": "no_legal_moves"}

        # 2. Simulação de Blunder Humano proporcional ao Elo
        if self.blunder_rate > 0.0 and random.random() < self.blunder_rate:
            # Em bots de Elo baixo, escolhe um lance legal aleatório ou subótimo
            blunder_move = random.choice(legal_moves)
            return blunder_move, {
                "source": "blunder_emulation",
                "elo": self.rating,
                "san": board.san(blunder_move),
            }

        # 3. Motor Alpha-Beta PeSTO calibrado
        depth = max_depth or self.calibrated_depth
        move, score, d, nodes = self.searcher.search_best_move(
            board,
            max_depth=depth,
            max_time_seconds=max_time_seconds or 1.5,
        )

        return move, {
            "source": "builtin_pesto",
            "depth": d,
            "score_cp": score,
            "nodes": nodes,
            "san": board.san(move) if move else None,
        }

    def get_phrase(self, category: str) -> Optional[str]:
        """Retorna uma frase de diálogo original do bot para a situação."""
        return self.phrases.get(category)
