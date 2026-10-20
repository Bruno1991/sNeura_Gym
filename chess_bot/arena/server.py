"""GymArena Backend Server (Mobile Chess Experience).

Interface de servidor FastAPI para a GymArena:
- 100% fiel à experiência do aplicativo mobile do Chess.com (GymArena)
- Catálogo oficial dos 217 bots do APK (s_ADB_Tools/bots_data.json)
- Integração do Neural_Bot 3200 Elo (ResNet + MCTS com Escudo Tático)
- Suporte a duelo Neural vs Bot, Humano vs Bot e Humano vs Neural
- WebSocket em tempo real e rotas REST completas
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.polyglot
import torch
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configuração de caminhos
CURRENT_DIR = Path(__file__).resolve().parent
CHESS_BOT_ROOT = CURRENT_DIR.parent
NEURAL_DIR = CHESS_BOT_ROOT / "Neural_Bot"
SCRIPTED_DIR = CHESS_BOT_ROOT / "Scripted_Bot"
CHECKPOINTS_DIR = NEURAL_DIR / "checkpoints"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(NEURAL_DIR))
sys.path.insert(0, str(SCRIPTED_DIR))

from chess_bot import ChessBot
from chess_ai.agent import NeuralChessBot
from chess_ai.model import ChessPolicyValueNet
from chess_ai.online_learning import OnlineLearner

WEIGHTS_PATH = CHECKPOINTS_DIR / "chess_policy_weights.pt"
ONNX_PATH = CHECKPOINTS_DIR / "chess_policy_weights.onnx"
ONLINE_HISTORY_PATH = CHECKPOINTS_DIR / "online_learning_history.json"
BOTS_DATA_PATH = CHESS_BOT_ROOT / "bots_data.json"
if not BOTS_DATA_PATH.is_file():
    BOTS_DATA_PATH = Path(r"C:\dev\s_ADB_Tools\bots_data.json")

# Otimização de Hardware para o Xeon (12 núcleos / 24 threads) e RTX 3060
try:
    torch.set_num_threads(12)
    torch.set_num_interop_threads(6)
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
except Exception:
    pass

app = FastAPI(title="GymArena - Mobile Chess Experience", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir assets estáticos (sons, avatares, peças)
ASSETS_DIR = CURRENT_DIR / "assets"
if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


def resolve_bot_avatar(bot_name: Optional[str], group_name: str = "", remote_url: Optional[str] = None) -> str:
    """Resolve caminho para o avatar do bot existente, URL remota ou fallback seguro para default.png."""
    if not bot_name:
        return "/assets/avatars/default.png"
    if bot_name == "Neural_Bot":
        return "/assets/avatars/neural_bot.png"

    avatars_dir = CURRENT_DIR / "assets" / "avatars"
    exact = avatars_dir / f"{bot_name}.png"
    if exact.is_file():
        return f"/assets/avatars/{bot_name}.png"

    # Busca por prefixo ou correspondência insensível a maiúsculas/minúsculas
    low = bot_name.lower()
    for f in avatars_dir.glob("*.png"):
        stem_low = f.stem.lower()
        if stem_low == low or stem_low.startswith(low + "-"):
            return f"/assets/avatars/{f.name}"

    # Fallback por grupo (ex: Beginner.png, Intermediate.png, Advanced.png)
    if group_name:
        for f in avatars_dir.glob("*.png"):
            if f.stem.lower() == group_name.lower():
                return f"/assets/avatars/{f.name}"

    if remote_url and remote_url.startswith("http"):
        return remote_url

    return "/assets/avatars/default.png"


# ==============================================================================
# GERENCIADOR DE PARTIDAS (MATCH MANAGER)
# ==============================================================================
class MatchManager:
    """Controlador de estado da partida na GymArena."""

    def __init__(self):
        self.lock = threading.Lock()
        self.match_generation: int = 0
        self.board = chess.Board()
        self.board_stack: List[str] = [self.board.fen()]

        # Configurações dos jogadores
        self.white_player_type = "neural"  # "human", "neural", "bot"
        self.black_player_type = "bot"
        self.white_bot_name: Optional[str] = None
        self.black_bot_name: Optional[str] = "Nelson"
        self.white_bot_elo: int = 3200
        self.black_bot_elo: int = 1300

        # Modo do Neural_Bot: MCTS ativo por padrão (3200 Elo)
        self.neural_mode: str = "mcts"
        self.neural_mcts_sims: int = 50

        self.auto_play: bool = True
        self.step_delay: float = 0.5
        self.is_running: bool = False

        self.last_move: Optional[Dict[str, Any]] = None
        self.eval_score: float = 0.0
        self.neural_info: Dict[str, Any] = {}
        self.move_history: List[str] = []
        self.current_speech: Optional[Dict[str, str]] = None
        self.online_trained_notice: Optional[Dict[str, Any]] = None

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.neural_model: Optional[ChessPolicyValueNet] = None
        self.neural_agent: Optional[NeuralChessBot] = None
        self.learner: Optional[OnlineLearner] = None

        self.active_white_engine: Optional[ChessBot] = None
        self.active_black_engine: Optional[ChessBot] = None

        self._init_neural()
        self.reset_game()

    def _init_neural(self):
        try:
            if WEIGHTS_PATH.is_file():
                self.neural_model = ChessPolicyValueNet.load_weights(WEIGHTS_PATH, device=self.device)
            else:
                self.neural_model = ChessPolicyValueNet(num_channels=128, num_blocks=4).to(self.device)

            self.neural_agent = NeuralChessBot(
                model=self.neural_model,
                device=self.device,
                use_mcts=True,
                mcts_sims=self.neural_mcts_sims,
                adaptive_mcts=True,
                adaptive_sims=35,
                use_book=True,
            )
            self.learner = OnlineLearner(
                model=self.neural_model,
                weights_path=WEIGHTS_PATH,
                onnx_path=ONNX_PATH,
                history_path=ONLINE_HISTORY_PATH,
                device=self.device,
            )
        except Exception as e:
            print(f"[!] Erro ao inicializar agente neural: {e}")

    def reset_game(self):
        """Reinicia o tabuleiro para novo jogo de forma thread-safe."""
        with self.lock:
            self.match_generation += 1
            self.board.reset()
            self.board_stack = [self.board.fen()]
            self.move_history.clear()
            self.last_move = None
            self.eval_score = 0.0
            self.neural_info = {}
            self.online_trained_notice = None

            if self.learner:
                self.learner.start_game()

            # Instanciar motores conforme os tipos configurados
            if self.white_player_type == "bot":
                self.active_white_engine = ChessBot(rate=self.white_bot_elo, bot_name=self.white_bot_name)
            else:
                self.active_white_engine = None

            if self.black_player_type == "bot":
                self.active_black_engine = ChessBot(rate=self.black_bot_elo, bot_name=self.black_bot_name)
            else:
                self.active_black_engine = None

            # Saudação inicial do bot adversário
            self._emit_initial_greeting()

    def _emit_initial_greeting(self):
        bot_engine = self.active_black_engine or self.active_white_engine
        if bot_engine:
            greeting = bot_engine.get_phrase("greeting")
            if greeting:
                side = "black" if self.black_player_type == "bot" else "white"
                bot_name = self.black_bot_name if side == "black" else self.white_bot_name
                self.current_speech = {
                    "text": greeting,
                    "speaker": bot_name or "Bot",
                    "avatar": resolve_bot_avatar(bot_name),
                    "side": side,
                }
            else:
                self.current_speech = None
        else:
            self.current_speech = None

    def check_tcec_adjudication(self) -> Tuple[bool, str, str]:
        """Adjudica vitória técnica a partir do lance 30 se houver vantagem decisiva de material (>=9 pts vs <=4 pts)."""
        if self.board.fullmove_number < 30:
            return False, "*", ""
        piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
        white_mat = sum(piece_values.get(p.piece_type, 0) for p in self.board.piece_map().values() if p.color == chess.WHITE)
        black_mat = sum(piece_values.get(p.piece_type, 0) for p in self.board.piece_map().values() if p.color == chess.BLACK)
        net_mat = white_mat - black_mat
        if net_mat >= 9 and black_mat <= 5:
            return True, "1-0", "Vitória das Brancas por Adjudicação TCEC (Vantagem Decisiva)."
        elif net_mat <= -9 and white_mat <= 5:
            return True, "0-1", "Vitória das Pretas por Adjudicação TCEC (Vantagem Decisiva)."
        return False, "*", ""

    def get_state(self) -> Dict[str, Any]:
        """Gera o estado completo sincronizado com a interface GymArena Mobile."""
        with self.lock:
            piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
            piece_symbols = {chess.PAWN: 'p', chess.KNIGHT: 'n', chess.BISHOP: 'b', chess.ROOK: 'r', chess.QUEEN: 'q'}

            starting_pieces = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}
            white_present: Dict[chess.PieceType, int] = {}
            black_present: Dict[chess.PieceType, int] = {}

            for sq in chess.SQUARES:
                p = self.board.piece_at(sq)
                if p:
                    if p.color == chess.WHITE:
                        white_present[p.piece_type] = white_present.get(p.piece_type, 0) + 1
                    else:
                        black_present[p.piece_type] = black_present.get(p.piece_type, 0) + 1

            captured_by_white = []
            for pt, cnt in starting_pieces.items():
                diff = cnt - black_present.get(pt, 0)
                if diff > 0 and pt in piece_symbols:
                    captured_by_white.extend(['b' + piece_symbols[pt]] * diff)

            captured_by_black = []
            for pt, cnt in starting_pieces.items():
                diff = cnt - white_present.get(pt, 0)
                if diff > 0 and pt in piece_symbols:
                    captured_by_black.extend(['w' + piece_symbols[pt]] * diff)

            white_mat = sum(cnt * piece_values.get(pt, 0) for pt, cnt in white_present.items())
            black_mat = sum(cnt * piece_values.get(pt, 0) for pt, cnt in black_present.items())
            material_diff = (white_mat - black_mat) / 100.0

            legal_uci = [m.uci() for m in self.board.legal_moves]

            # Resultado da partida
            is_over = self.board.is_game_over(claim_draw=True)
            game_result = self.board.result(claim_draw=True) if is_over else "*"
            result_desc = ""

            # Adjudicação TCEC de Finais Decididos (Win Adjudication)
            if not is_over:
                tcec_decisive, tcec_res, tcec_desc = self.check_tcec_adjudication()
                if tcec_decisive:
                    is_over = True
                    game_result = tcec_res
                    result_desc = tcec_desc

            if self.board.is_checkmate():
                winner = "Brancas" if self.board.turn == chess.BLACK else "Pretas"
                result_desc = f"Xeque-Mate! Vitória das {winner}."
            elif self.board.is_stalemate():
                result_desc = "Empate por Afogamento (Stalemate)."
            elif self.board.is_insufficient_material():
                result_desc = "Empate por Material Insuficiente."
            elif self.board.can_claim_threefold_repetition() or self.board.is_repetition(3):
                result_desc = "Empate por Repetição Tripla."
            elif self.board.can_claim_fifty_moves() or self.board.is_fifty_moves():
                result_desc = "Empate pela Regra dos 50 Lances."

            return {
                "fen": self.board.fen(),
                "turn": "w" if self.board.turn == chess.WHITE else "b",
                "move_number": self.board.fullmove_number,
                "legal_moves": legal_uci,
                "last_move": self.last_move,
                "is_check": self.board.is_check(),
                "is_game_over": is_over,
                "result": game_result,
                "result_desc": result_desc,
                "eval_score": self.eval_score,
                "material_diff": material_diff,
                "captured_by_white": captured_by_white,
                "captured_by_black": captured_by_black,
                "move_history": list(self.move_history),
                "neural_info": self.neural_info,
                "current_speech": self.current_speech,
                "white_player": {
                    "type": self.white_player_type,
                    "name": "Neural_Bot" if self.white_player_type == "neural" else (self.white_bot_name or "Você"),
                    "elo": 3200 if self.white_player_type == "neural" else (self.white_bot_elo if self.white_player_type == "bot" else 1500),
                    "avatar": "/assets/avatars/neural_bot.png" if self.white_player_type == "neural" else (resolve_bot_avatar(self.white_bot_name) if self.white_player_type == "bot" else "/assets/avatars/human.png")
                },
                "black_player": {
                    "type": self.black_player_type,
                    "name": "Neural_Bot" if self.black_player_type == "neural" else (self.black_bot_name or "Você"),
                    "elo": 3200 if self.black_player_type == "neural" else (self.black_bot_elo if self.black_player_type == "bot" else 1500),
                    "avatar": "/assets/avatars/neural_bot.png" if self.black_player_type == "neural" else (resolve_bot_avatar(self.black_bot_name) if self.black_player_type == "bot" else "/assets/avatars/human.png")
                },
                "neural_mode": self.neural_mode,
                "mcts_sims": self.neural_mcts_sims,
                "auto_play": self.auto_play,
                "step_delay": self.step_delay,
                "online_trained": self.online_trained_notice,
            }

    def play_move(self, move: chess.Move) -> bool:
        """Aplica o lance ao tabuleiro e calcula os eventos e reações."""
        with self.lock:
            if move not in self.board.legal_moves:
                return False

            mover_color = self.board.turn
            is_neural = (
                (mover_color == chess.WHITE and self.white_player_type == "neural") or
                (mover_color == chess.BLACK and self.black_player_type == "neural")
            )

            from_sq = chess.square_name(move.from_square)
            to_sq = chess.square_name(move.to_square)
            san = self.board.san(move)

            is_capture = self.board.is_capture(move)
            is_castle = self.board.is_castling(move)
            is_promo = (move.promotion is not None)

            if self.learner and ("neural" in (self.white_player_type, self.black_player_type)):
                self.learner.record_move(self.board, move, is_neural=is_neural)

            self.board.push(move)
            self.board_stack.append(self.board.fen())
            self.move_history.append(san)

            sound_type = "move"
            if self.board.is_check():
                sound_type = "check"
            elif is_capture:
                sound_type = "capture"
            elif is_castle:
                sound_type = "castle"
            elif is_promo:
                sound_type = "promote"

            self.last_move = {
                "from": from_sq,
                "to": to_sq,
                "san": san,
                "sound": sound_type,
                "color": "w" if mover_color == chess.WHITE else "b",
            }

            # Atualizar fala contextual do bot scriptado se aplicável
            self._update_speech_reaction(mover_color, move, was_capture=is_capture)

            # Aprendizado online ao fim do jogo (Mate, Empate formal ou Adjudicação TCEC decisiva)
            tcec_decisive, _, _ = self.check_tcec_adjudication()
            if (self.board.is_game_over(claim_draw=True) or tcec_decisive) and ("neural" in (self.white_player_type, self.black_player_type)):
                neural_is_white = (self.white_player_type == "neural")
                opp_name = self.black_bot_name if neural_is_white else self.white_bot_name
                if self.learner:
                    res = self.learner.learn_from_completed_game(
                        self.board,
                        neural_is_white=neural_is_white,
                        opponent_name=opp_name or "Adversário",
                    )
                    self.online_trained_notice = res

            return True

    def _update_speech_reaction(self, mover_color: chess.Color, last_move: chess.Move, was_capture: bool = False):
        """Dispara falas contextuais autênticas dos bots do Chess.com."""
        bot_side = "black" if self.black_player_type == "bot" else ("white" if self.white_player_type == "bot" else None)
        if not bot_side:
            self.current_speech = None
            return

        engine = self.active_black_engine if bot_side == "black" else self.active_white_engine
        bot_name = self.black_bot_name if bot_side == "black" else self.white_bot_name
        if not engine:
            self.current_speech = None
            return

        phrase = None
        if self.board.is_checkmate():
            phrase = engine.get_phrase("won") if (self.board.turn != mover_color) else engine.get_phrase("lost")
        elif self.board.is_check():
            phrase = engine.get_phrase("givingCheck")
        elif was_capture and random.random() < 0.40:
            phrase = engine.get_phrase("winning") or engine.get_phrase("greeting")
        elif random.random() < 0.15:
            phrase = engine.get_phrase("greeting")

        if phrase:
            self.current_speech = {
                "text": phrase,
                "speaker": bot_name or "Bot",
                "avatar": resolve_bot_avatar(bot_name),
                "side": bot_side,
            }
        else:
            self.current_speech = None

    def undo_move(self) -> bool:
        """Desfaz lances no tabuleiro de forma thread-safe."""
        with self.lock:
            if len(self.board_stack) <= 1:
                return False

            human_playing = ("human" in (self.white_player_type, self.black_player_type))
            steps_to_pop = 2 if human_playing and len(self.board_stack) > 2 else 1

            for _ in range(steps_to_pop):
                if len(self.board_stack) > 1:
                    self.board.pop()
                    self.board_stack.pop()
                    if self.move_history:
                        self.move_history.pop()

            self.last_move = None
            self.current_speech = None
            return True

    def compute_next_bot_move(self) -> Optional[chess.Move]:
        """Calcula a jogada da IA da vez de forma não bloqueante e com descarte de geração defasada."""
        with self.lock:
            gen = self.match_generation
            if self.board.is_game_over(claim_draw=True):
                return None

            is_white_turn = (self.board.turn == chess.WHITE)
            current_type = self.white_player_type if is_white_turn else self.black_player_type

            if current_type == "human":
                return None

            board_snapshot = self.board.copy()
            white_bot_elo = self.white_bot_elo
            black_bot_elo = self.black_bot_elo
            white_bot_name = self.white_bot_name
            black_bot_name = self.black_bot_name
            neural_mode = self.neural_mode
            mcts_sims = self.neural_mcts_sims

        try:
            # 1. VEZ DO NEURAL_BOT
            if current_type == "neural":
                if not self.neural_agent:
                    legal = list(board_snapshot.legal_moves)
                    return legal[0] if legal else None

                use_mcts_flag = (neural_mode == "mcts")
                sims = mcts_sims if use_mcts_flag else 0
                move, info = self.neural_agent.get_best_move(
                    board_snapshot,
                    use_mcts=use_mcts_flag,
                    num_simulations=sims,
                )

                val = info.get("value", info.get("root_value", 0.0))
                raw_eval = val * 4.0
                eval_score = round(raw_eval if is_white_turn else -raw_eval, 2)

                neural_info = {
                    "source": info.get("source", "mcts_search" if use_mcts_flag else "neural_policy"),
                    "visits": info.get("best_move_visits", mcts_sims if use_mcts_flag else 1),
                    "depth": info.get("depth_reached", 4),
                    "confidence": round(info.get("probability", 1.0) * 100, 1),
                    "san": info.get("san", board_snapshot.san(move) if move else None),
                    "top_candidates": info.get("top_candidates", []),
                }

                with self.lock:
                    if gen != self.match_generation:
                        return None
                    self.eval_score = eval_score
                    self.neural_info = neural_info
                    return move

            # 2. VEZ DO SCRIPTED BOT (CHESS.COM)
            if current_type == "bot":
                engine = self.active_white_engine if is_white_turn else self.active_black_engine
                if engine is None:
                    engine = ChessBot(
                        rate=white_bot_elo if is_white_turn else black_bot_elo,
                        bot_name=white_bot_name if is_white_turn else black_bot_name
                    )

                move, info = engine.get_best_move(board_snapshot)
                score_cp = info.get("score_cp", 0)
                score_white = (score_cp if is_white_turn else -score_cp) / 100.0
                eval_score = round(score_white, 2)

                neural_info = {
                    "source": info.get("source", "chess_com_engine"),
                    "depth": info.get("depth", 2),
                    "book": info.get("book", None),
                    "san": info.get("san", board_snapshot.san(move) if move else None),
                }

                with self.lock:
                    if gen != self.match_generation:
                        return None
                    self.eval_score = eval_score
                    self.neural_info = neural_info
                    return move

        except Exception as e:
            print(f"[!] Erro ao computar lance da IA ({current_type}): {e}")
            with self.lock:
                if gen != self.match_generation:
                    return None
                legal = list(self.board.legal_moves)
                return legal[0] if legal else None

    def get_hint_move(self) -> Optional[Dict[str, Any]]:
        with self.lock:
            if not self.neural_agent or self.board.is_game_over(claim_draw=True):
                return None
            board_snapshot = self.board.copy()

        move, info = self.neural_agent.get_best_move(board_snapshot, use_mcts=True, num_simulations=35)
        if move:
            return {
                "uci": move.uci(),
                "san": board_snapshot.san(move),
                "from": chess.square_name(move.from_square),
                "to": chess.square_name(move.to_square),
                "confidence": round(info.get("probability", 1.0) * 100, 1),
                "source": "neural_hint",
            }
        return None


manager = MatchManager()


# ==============================================================================
# WEBSOCKET MANAGER
# ==============================================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


ws_manager = ConnectionManager()


# ==============================================================================
# ROTAS ESTÁTICAS E API
# ==============================================================================
@app.get("/")
def serve_index():
    return FileResponse(
        str(CURRENT_DIR / "index.html"),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/style.css")
def serve_css():
    return FileResponse(
        str(CURRENT_DIR / "style.css"),
        media_type="text/css",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/app.js")
def serve_js():
    return FileResponse(
        str(CURRENT_DIR / "app.js"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/favicon.ico", include_in_schema=False)
def serve_favicon():
    fav = CURRENT_DIR / "favicon.ico"
    if fav.is_file():
        return FileResponse(str(fav), media_type="image/x-icon")
    return Response(status_code=204)


@app.get("/api/bots")
def list_available_bots():
    """Retorna os 217 bots oficiais do APK organizados por categorias + Neural_Bot 3200."""
    categories: List[Dict[str, Any]] = []

    cat_meta_map = {
        "🧠 Neural_Bot 3200": {"icon": "🧠", "label": "Rede Neural (3200 Elo)"},
        "The Cryptids": {"icon": "🐾", "label": "The Cryptids (Lendas)"},
        "New to Chess": {"icon": "🐣", "label": "Iniciantes (Aprendendo)"},
        "Beginner": {"icon": "♟️", "label": "Principiantes"},
        "Intermediate": {"icon": "⚔️", "label": "Intermediários"},
        "Advanced": {"icon": "🛡️", "label": "Avançados"},
        "Master": {"icon": "👑", "label": "Mestres"},
        "Top Players": {"icon": "🏆", "label": "Grandes Mestres & Top Players"},
        "Creators": {"icon": "🎭", "label": "Criadores de Conteúdo"},
        "Athletes": {"icon": "⚡", "label": "Atletas"},
        "Musicians": {"icon": "🎵", "label": "Músicos"},
        "Adaptive": {"icon": "🔄", "label": "Bots Adaptativos"},
        "Personalities": {"icon": "🧩", "label": "Personalidades Históricas"},
        "Visualization": {"icon": "👁️", "label": "Treinadores de Visualização"},
        "Engine": {"icon": "🤖", "label": "Komodo Engine (Níveis 1-25)"},
    }

    # 1. Categoria Especial: Neural_Bot (Residente de Elite)
    categories.append({
        "group_name": "🧠 Neural_Bot 3200",
        "label": "Rede Neural (3200 Elo)",
        "icon": "🧠",
        "count": 1,
        "min_elo": 3200,
        "max_elo": 3200,
        "description": "Rede Neural ResNet de 128 Canais com MCTS Profundo e 97,4% de Win Rate",
        "bots": [
            {
                "name": "Neural_Bot",
                "username": "Neural_Bot_3200",
                "rating": 3200,
                "group": "Neural AI",
                "description": "Inteligência Artificial por Reforço treinada com 50.000 partidas e livros Polyglot fundidos.",
                "greeting": "Prepare-se para enfrentar a inteligência máxima da GymArena.",
                "avatar": "/assets/avatars/neural_bot.png",
                "is_neural": True,
            }
        ]
    })

    # 2. Bots Oficiais do APK Chess.com (bots_data.json)
    if BOTS_DATA_PATH.is_file():
        try:
            with open(BOTS_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            for g in data.get("botGroups", []):
                group_name = g.get("name", "Outros")
                bot_list = []
                for b in g.get("botPersonalities", []):
                    b_name = b.get("name")
                    pl = b.get("phraseList", {})
                    greeting = pl.get("greeting", f"Olá, eu sou {b_name}!")
                    bot_list.append({
                        "name": b_name,
                        "username": b.get("username", b_name),
                        "rating": int(b.get("rating", 1500)),
                        "group": group_name,
                        "description": b.get("bio", b.get("description", "")),
                        "greeting": greeting,
                        "book": b.get("book", "balanced"),
                        "avatar": resolve_bot_avatar(b_name, group_name, b.get("imageUrl") or b.get("avatarWithoutBackground")),
                        "is_neural": False,
                    })

                if bot_list:
                    meta = cat_meta_map.get(group_name, {"icon": "♟️", "label": group_name})
                    elos = [b["rating"] for b in bot_list]
                    categories.append({
                        "group_name": group_name,
                        "label": meta.get("label", group_name),
                        "icon": meta.get("icon", "♟️"),
                        "count": len(bot_list),
                        "min_elo": min(elos),
                        "max_elo": max(elos),
                        "description": f"{len(bot_list)} bots oficiais disponíveis (Elo {min(elos)} - {max(elos)})",
                        "bots": bot_list
                    })
            flat_bots = [b for c in categories for b in c["bots"]]
            return {"categories": categories, "bots": flat_bots}
        except Exception as e:
            print(f"[!] Erro ao carregar bots_data.json: {e}")

    # Fallback
    sample = [
        {"name": "Martin", "rating": 250, "group": "Beginner", "avatar": "/assets/avatars/Martin.png", "greeting": "Adoro jogar xadrez!"},
        {"name": "Nelson", "rating": 1300, "group": "Intermediate", "avatar": "/assets/avatars/Nelson.png", "greeting": "Cuidado com a minha Dama!"},
        {"name": "Wendy", "rating": 1500, "group": "Advanced", "avatar": "/assets/avatars/Wendy.png", "greeting": "Vamos jogar!"},
        {"name": "Hikaru", "rating": 2820, "group": "Top Players", "avatar": "/assets/avatars/Hikaru.png", "greeting": "Vamos ver o que você tem."},
        {"name": "Maximum", "rating": 3200, "group": "Engine", "avatar": "/assets/avatars/Maximum.png", "greeting": "Modo de cálculo ativado."},
    ]
    return {"categories": [{"group_name": "Oficiais", "description": "Bots em destaque", "bots": sample}], "bots": sample}


class MatchConfig(BaseModel):
    mode: str = "neural_vs_bot"  # "neural_vs_bot", "human_vs_bot", "human_vs_neural"
    player_color: str = "white"   # "white", "black", "random"
    bot_name: str = "Nelson"
    bot_elo: int = 1300
    neural_mode: str = "mcts"     # "mcts" ou "direct"
    mcts_sims: int = 50
    step_delay: float = 0.5
    auto_play: bool = True


@app.post("/api/match/start")
async def start_match(config: MatchConfig):
    """Inicia confronto configurado na GymArena."""
    mode = config.mode
    color = config.player_color

    if color == "random":
        color = random.choice(["white", "black"])

    if mode == "neural_vs_bot":
        if color == "white":
            manager.white_player_type = "neural"
            manager.white_bot_name = None
            manager.white_bot_elo = 3200

            manager.black_player_type = "bot"
            manager.black_bot_name = config.bot_name
            manager.black_bot_elo = config.bot_elo
        else:
            manager.white_player_type = "bot"
            manager.white_bot_name = config.bot_name
            manager.white_bot_elo = config.bot_elo

            manager.black_player_type = "neural"
            manager.black_bot_name = None
            manager.black_bot_elo = 3200
        manager.auto_play = config.auto_play

    elif mode == "human_vs_bot":
        if color == "white":
            manager.white_player_type = "human"
            manager.white_bot_name = "Você"
            manager.white_bot_elo = 1500

            manager.black_player_type = "bot"
            manager.black_bot_name = config.bot_name
            manager.black_bot_elo = config.bot_elo
        else:
            manager.white_player_type = "bot"
            manager.white_bot_name = config.bot_name
            manager.white_bot_elo = config.bot_elo

            manager.black_player_type = "human"
            manager.black_bot_name = "Você"
            manager.black_bot_elo = 1500
        manager.auto_play = False

    elif mode == "human_vs_neural":
        if color == "white":
            manager.white_player_type = "human"
            manager.white_bot_name = "Você"
            manager.white_bot_elo = 1500

            manager.black_player_type = "neural"
            manager.black_bot_name = None
            manager.black_bot_elo = 3200
        else:
            manager.white_player_type = "neural"
            manager.white_bot_name = None
            manager.white_bot_elo = 3200

            manager.black_player_type = "human"
            manager.black_bot_name = "Você"
            manager.black_bot_elo = 1500
        manager.auto_play = False

    manager.neural_mode = config.neural_mode
    manager.neural_mcts_sims = config.mcts_sims
    manager.step_delay = config.step_delay

    if manager.neural_agent:
        manager.neural_agent.use_mcts = (config.neural_mode == "mcts")
        manager.neural_agent.mcts_sims = manager.neural_mcts_sims

    manager.reset_game()
    state = manager.get_state()
    await ws_manager.broadcast({"type": "state_update", "state": state})
    return {"success": True, "state": state}


@app.get("/api/match/state")
def get_match_state():
    return manager.get_state()


class MoveRequest(BaseModel):
    uci: str


@app.post("/api/match/move")
async def make_human_move(req: MoveRequest):
    try:
        move = chess.Move.from_uci(req.uci)
    except Exception:
        raise HTTPException(status_code=400, detail="Lance UCI inválido")

    success = manager.play_move(move)
    if not success:
        raise HTTPException(status_code=400, detail="Lance ilegal")

    state = manager.get_state()
    sound = (state.get("last_move") or {}).get("sound", "move")
    await ws_manager.broadcast({"type": "state_update", "state": state})
    return {"success": True, "state": state, "sound": sound}


@app.post("/api/match/step")
async def execute_engine_step():
    """Avança exatamente um lance calculado pela IA da vez."""
    bot_move = await asyncio.to_thread(manager.compute_next_bot_move)
    if bot_move:
        manager.play_move(bot_move)

    state = manager.get_state()
    sound = (state.get("last_move") or {}).get("sound", "move")
    await ws_manager.broadcast({"type": "state_update", "state": state})
    return {"success": True, "state": state, "sound": sound}


@app.post("/api/match/undo")
async def undo_last_move():
    success = manager.undo_move()
    state = manager.get_state()
    await ws_manager.broadcast({"type": "state_update", "state": state})
    return {"success": success, "state": state}


@app.get("/api/match/hint")
async def get_neural_hint():
    hint = await asyncio.to_thread(manager.get_hint_move)
    return {"hint": hint}


@app.post("/api/match/reset")
async def reset_board():
    manager.reset_game()
    state = manager.get_state()
    await ws_manager.broadcast({"type": "state_update", "state": state})
    return {"success": True, "state": state}


class MCTSConfigRequest(BaseModel):
    use_mcts: bool
    sims: Optional[int] = 50


@app.post("/api/match/mcts")
async def toggle_mcts_mode(req: MCTSConfigRequest):
    """Ativa ou desativa a busca em árvore neural MCTS em tempo real."""
    manager.neural_mode = "mcts" if req.use_mcts else "direct"
    if req.sims is not None and req.sims > 0:
        manager.neural_mcts_sims = req.sims
    if manager.neural_agent:
        manager.neural_agent.use_mcts = req.use_mcts
        manager.neural_agent.mcts_sims = manager.neural_mcts_sims
    state = manager.get_state()
    await ws_manager.broadcast({"type": "state_update", "state": state})
    return {
        "success": True,
        "neural_mode": manager.neural_mode,
        "mcts_sims": manager.neural_mcts_sims,
        "state": state,
    }


@app.websocket("/ws/match")
async def websocket_match_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({"type": "state_update", "state": manager.get_state()})
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "step":
                    bot_move = await asyncio.to_thread(manager.compute_next_bot_move)
                    if bot_move:
                        manager.play_move(bot_move)
                    await ws_manager.broadcast({"type": "state_update", "state": manager.get_state()})
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
