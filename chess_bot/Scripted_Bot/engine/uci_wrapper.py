"""Wrapper para integração opcional com motores UCI externos (Stockfish, Komodo).

Se houver um executável compatível em bin/ ou no PATH do sistema, o bot pode
utilizá-lo para atingir cálculo de mais de 3200 Elo de forma ultrarrápida.
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
import chess
import chess.engine


class UCIEngineWrapper:
    """Gerencia comunicação UCI com executável local (Stockfish ou Komodo)."""

    def __init__(self, binary_path: Optional[str] = None):
        self.engine_path = self._locate_engine(binary_path)
        self.engine: Optional[chess.engine.SimpleEngine] = None

    def _locate_engine(self, custom_path: Optional[str]) -> Optional[Path]:
        """Localiza o binário do motor UCI."""
        if custom_path and Path(custom_path).is_file():
            return Path(custom_path)

        # Procura na pasta bin/ local do projeto
        current_dir = Path(__file__).resolve().parent.parent
        bin_dir = current_dir / "bin"
        if bin_dir.is_dir():
            for name in ["stockfish.exe", "komodo.exe", "stockfish", "komodo"]:
                candidate = bin_dir / name
                if candidate.is_file():
                    return candidate

        # Procura no PATH do sistema
        for cmd in ["stockfish", "komodo"]:
            found = shutil.which(cmd)
            if found:
                return Path(found)

        return None

    def is_available(self) -> bool:
        """Verifica se um motor UCI executável está disponível."""
        return self.engine_path is not None and self.engine_path.is_file()

    def start(self, elo_limit: int = 3200):
        """Inicia o processo do motor UCI."""
        if not self.is_available():
            raise RuntimeError("Nenhum binário de motor UCI encontrado.")

        if self.engine is None:
            self.engine = chess.engine.SimpleEngine.popen_uci(str(self.engine_path))
            try:
                # Configura limite de rating se o motor suportar
                self.engine.configure({"UCI_LimitStrength": True, "UCI_Elo": elo_limit})
            except Exception:
                pass

    def stop(self):
        """Finaliza o motor UCI."""
        if self.engine is not None:
            try:
                self.engine.quit()
            except Exception:
                pass
            self.engine = None

    def search_best_move(
        self,
        board: chess.Board,
        time_limit: float = 1.0,
        depth_limit: Optional[int] = None,
    ) -> Tuple[Optional[chess.Move], int, int]:
        """Calcula o melhor movimento usando o motor UCI.
        
        Retorna: (best_move, score_centipawns, depth)
        """
        if not self.engine:
            self.start()

        limit = chess.engine.Limit(time=time_limit, depth=depth_limit)
        info = self.engine.analyse(board, limit)
        best_move = info.get("pv", [None])[0] if "pv" in info else None
        score_val = 0
        if "score" in info:
            score = info["score"].relative
            if score.is_mate():
                score_val = 20000 if score.mate() > 0 else -20000
            else:
                score_val = score.score() or 0
        depth = info.get("depth", 0)
        return best_move, score_val, depth
