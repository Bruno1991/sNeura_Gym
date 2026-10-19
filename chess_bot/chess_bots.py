"""Módulo de Análise e Emulação de Bots do Chess.com descompilado (com.chess).

Permite:
- Consultar todos os 217 bots oficiais organizados por 14 categorias.
- Inspecionar parâmetros de engine (Livro de Abertura Polyglot .bin, Komodo Skill, Elo, Estilo).
- Visualizar frases de diálogo interativas de cada bot.
- Jogar partidas diretamente pelo terminal contra qualquer bot (usando os livros de abertura .bin reais).
- Analisar a arquitetura de bloqueio client-side (canPlay / BotAccessResolverImpl).
"""

import json
import os
import random
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Forçar suporte UTF-8 no console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import chess
    import chess.polyglot
    HAS_CHESS_LIB = True
except ImportError:
    HAS_CHESS_LIB = False

TWIRP_BOTS_URL = "https://api.chess.com/rpc/chesscom.bots.v1.BotGroupService/ListBotGroups"


class ChessBotsManager:
    """Gerencia consulta, análise e emulação dos bots do com.chess."""

    def __init__(self, workspace_root: Optional[Path] = None):
        if workspace_root is None:
            self.root = Path(__file__).resolve().parent
        else:
            self.root = workspace_root

        self.assets_dir = self.root / "books"
        self.cache_file = self.root / "bots_data.json"
        self._data: Optional[Dict[str, Any]] = None

    def load_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Carrega a base de bots do cache local ou busca diretamente da API Twirp."""
        if self._data and not force_refresh:
            return self._data

        if self.cache_file.is_file() and not force_refresh:
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                    return self._data
            except Exception:
                pass

        # Buscar da API Twirp oficial
        try:
            req = urllib.request.Request(
                TWIRP_BOTS_URL,
                data=json.dumps({"withBots": True}).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Chess/v1 (Android)",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                self._data = json.loads(res.read().decode("utf-8"))

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)

            return self._data
        except Exception as e:
            if self.cache_file.is_file():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                    return self._data
            raise RuntimeError(f"Não foi possível carregar a lista de bots: {e}")

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """Retorna todos os grupos de bots."""
        data = self.load_data()
        return data.get("botGroups", [])

    def get_all_bots(self) -> List[Dict[str, Any]]:
        """Retorna lista plana de todos os bots com informação do grupo."""
        groups = self.get_all_groups()
        all_bots = []
        for g in groups:
            group_name = g.get("name", "Geral")
            for b in g.get("botPersonalities", []):
                bot_copy = dict(b)
                bot_copy["groupName"] = group_name
                all_bots.append(bot_copy)
        return all_bots

    def search_bots(self, query: str) -> List[Dict[str, Any]]:
        """Busca bots por nome, username ou grupo."""
        q = query.lower()
        results = []
        for b in self.get_all_bots():
            name = b.get("name", "").lower()
            user = b.get("username", "").lower()
            group = b.get("groupName", "").lower()
            if q in name or q in user or q in group:
                results.append(b)
        return results

    def find_bot(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Encontra um bot exato ou o mais próximo."""
        bots = self.get_all_bots()
        id_lower = identifier.lower().strip()

        # Correspondência exata por nome ou username
        for b in bots:
            if b.get("name", "").lower() == id_lower or b.get("username", "").lower() == id_lower:
                return b

        # Substring match
        matches = self.search_bots(identifier)
        if matches:
            return matches[0]

        return None

    def get_book_path(self, book_name: Optional[str]) -> Optional[Path]:
        """Retorna o caminho do livro Polyglot .bin nos assets descompilados."""
        if not book_name:
            return None
        candidate = self.assets_dir / f"{book_name.lower()}.bin"
        if candidate.is_file():
            return candidate
        return None

    def list_available_books(self) -> List[Path]:
        """Lista todos os livros .bin presentes nos assets."""
        if not self.assets_dir.is_dir():
            return []
        return sorted(list(self.assets_dir.glob("*.bin")))


def print_bot_summary(manager: ChessBotsManager):
    """Exibe um resumo estatístico e categorizado dos bots."""
    groups = manager.get_all_groups()
    all_bots = manager.get_all_bots()
    books = manager.list_available_books()

    print("\n" + "=" * 65)
    print("      CHESS.COM - ANÁLISE COMPLETA DO MOTOR DE BOTS")
    print("=" * 65)
    print(f"[*] Total de Grupos/Categorias: {len(groups)}")
    print(f"[*] Total de Bots Registrados:  {len(all_bots)}")
    print(f"[*] Livros Polyglot (.bin) nos assets: {len(books)}")

    free_count = sum(1 for b in all_bots if b.get("canPlay") is True)
    premium_count = sum(1 for b in all_bots if b.get("premium") is True)
    print(f"[*] Bots Gratuitos (canPlay=True):   {free_count}")
    print(f"[*] Bots Bloqueados (premium=True):  {premium_count}")
    print("-" * 65)

    for idx, g in enumerate(groups, 1):
        bots = g.get("botPersonalities", [])
        g_free = sum(1 for b in bots if b.get("canPlay") is True)
        g_prem = sum(1 for b in bots if b.get("premium") is True)
        print(f"[{idx:02d}] {g.get('name'):<22} | Total: {len(bots):2d} | Grátis: {g_free:2d} | Premium: {g_prem:2d}")

    print("\n[+] Livros de Abertura (.bin) extraídos em assets/:")
    for bk in books:
        size_kb = bk.stat().st_size / 1024
        print(f"    - {bk.name:<20} ({size_kb:.1f} KB)")
    print()


def print_bot_detail(bot: Dict[str, Any], manager: ChessBotsManager):
    """Exibe ficha técnica detalhada de um bot específico."""
    print("\n" + "=" * 60)
    print(f" FICHA TÉCNICA DO BOT: {bot.get('name')}")
    print("=" * 60)
    print(f" Identificador (UUID) : {bot.get('id')}")
    print(f" Username no App      : {bot.get('username')}")
    print(f" Categoria / Grupo    : {bot.get('groupName')}")
    print(f" Rating Elo           : {bot.get('rating')} ({bot.get('ratingText', 'N/A')})")
    print(f" Nível Komodo Skill   : {bot.get('komodoSkill')} (Level: {bot.get('komodoSkillLevel')})")
    print(f" Estilo / Personality : {bot.get('personality')}")
    print(f" Adaptativo           : {'Sim' if bot.get('adapt') else 'Não'}")
    print(f" Status de Acesso     : {'Gratuito (canPlay=True)' if bot.get('canPlay') else 'BLOQUEADO (premium=True)'}")

    book_name = bot.get("book")
    book_path = manager.get_book_path(book_name)
    book_status = f"Disponível em {book_path.name}" if book_path else "Não encontrado em assets"
    print(f" Livro de Abertura    : {book_name} ({book_status})")
    print(f" Livro Fallback       : {bot.get('bookFallback') or 'Nenhum'}")

    desc = bot.get("description", "")
    if desc:
        print(f"\n Biografia / Descrição:\n   \"{desc}\"")

    phrase_list = bot.get("phraseList", {})
    if phrase_list:
        print(f"\n Frases Interativas de Diálogo ({len(phrase_list)} reações):")
        sample_keys = [
            ("greeting", "Saudação Inicial"),
            ("won", "Ao Vencer"),
            ("lost", "Ao Perder"),
            ("givingCheck", "Ao Dar Xeque"),
            ("queenCaptured", "Quando perde a Dama"),
            ("capturingQueen", "Quando captura sua Dama"),
        ]
        for key, label in sample_keys:
            val = phrase_list.get(key)
            if val:
                print(f"   * {label:<22}: \"{val}\"")

    print("\n" + "=" * 60 + "\n")


def play_interactive_game(bot: Dict[str, Any], manager: ChessBotsManager):
    """Executa partida interativa no terminal contra o bot escolhido."""
    if not HAS_CHESS_LIB:
        print("[!] A biblioteca 'python-chess' é necessária para jogar.")
        print("    Instale via: pip install chess")
        return

    book_name = bot.get("book")
    book_path = manager.get_book_path(book_name)
    phrase_list = bot.get("phraseList", {})

    print("\n" + "=" * 60)
    print(f" PARTIDA CONTRA: {bot.get('name')} (Rating {bot.get('rating')})")
    print("=" * 60)
    greeting = phrase_list.get("greeting")
    if greeting:
        print(f" {bot.get('name')}: \"{greeting}\"")
    print("-" * 60)

    board = chess.Board()

    # Perguntar cor do jogador
    color_choice = input("Deseja jogar de Brancas (b) ou Pretas (p)? [Padrão: b]: ").strip().lower()
    player_is_white = color_choice != "p"

    polyglot_reader = None
    if book_path and book_path.is_file():
        try:
            polyglot_reader = chess.polyglot.open_reader(str(book_path))
            print(f"[*] Livro de abertura Polyglot ativo: {book_path.name}")
        except Exception as e:
            print(f"[!] Não foi possível carregar livro {book_path}: {e}")

    def pick_bot_move() -> chess.Move:
        # 1. Tentar mover do livro de abertura
        if polyglot_reader:
            try:
                entries = list(polyglot_reader.find_all(board))
                if entries:
                    weights = [e.weight for e in entries]
                    total_w = sum(weights)
                    if total_w > 0:
                        chosen = random.choices(entries, weights=weights, k=1)[0]
                        return chosen.move
                    return entries[0].move
            except Exception:
                pass

        # 2. Fallback heurístico inteligente proporcional ao Elo do bot
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None

        rating = bot.get("rating", 1200)

        # Para bots fracos (Martin = 250), adiciona chance de blunder / movimento aleatório
        if rating <= 400 and random.random() < 0.65:
            return random.choice(legal_moves)
        elif rating <= 800 and random.random() < 0.35:
            return random.choice(legal_moves)

        # Avaliação de captura e controle de centro
        best_move = legal_moves[0]
        best_score = -999999

        piece_values = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 20000,
        }

        for m in legal_moves:
            score = 0
            if board.is_capture(m):
                captured = board.piece_at(m.to_square)
                attacker = board.piece_at(m.from_square)
                cap_val = piece_values.get(captured.piece_type, 0) if captured else 0
                att_val = piece_values.get(attacker.piece_type, 0) if attacker else 0
                score += (cap_val * 10) - att_val
            if m.to_square in [chess.D4, chess.D5, chess.E4, chess.E5]:
                score += 30
            if board.gives_check(m):
                score += 45

            # Adicionar ruído controlado para variar o jogo
            noise = random.randint(-20, 20)
            score += noise

            if score > best_score:
                best_score = score
                best_move = m

        return best_move

    try:
        while not board.is_game_over():
            print("\n" + str(board))
            print(f"Turno: {'Brancas' if board.turn == chess.WHITE else 'Pretas'}")

            is_player_turn = (board.turn == chess.WHITE and player_is_white) or (
                board.turn == chess.BLACK and not player_is_white
            )

            if is_player_turn:
                while True:
                    user_input = input("\nSeu lance (SAN ex: e4, Nf3 ou UCI ex: e2e4, ou 'sair'): ").strip()
                    if user_input.lower() in ["sair", "quit", "exit"]:
                        print("\nPartida interrompida.")
                        return

                    try:
                        move = board.parse_san(user_input)
                        board.push(move)
                        break
                    except Exception:
                        try:
                            move = chess.Move.from_uci(user_input)
                            if move in board.legal_moves:
                                board.push(move)
                                break
                        except Exception:
                            pass
                    print("[!] Lance inválido. Tente novamente.")
            else:
                print(f"\n[*] {bot.get('name')} está pensando...")
                b_move = pick_bot_move()
                if not b_move:
                    break

                san_move = board.san(b_move)
                board.push(b_move)
                print(f"[+] {bot.get('name')} jogou: {san_move}")

                # Falas do bot durante o jogo
                if board.is_check():
                    chk = phrase_list.get("givingCheck")
                    if chk:
                        print(f" {bot.get('name')}: \"{chk}\"")

        print("\n" + "=" * 50)
        print(" FIM DE PARTIDA")
        print("=" * 50)
        print(str(board))
        print(f"Resultado: {board.result()}")
        if board.is_checkmate():
            if (board.turn == chess.WHITE and player_is_white) or (board.turn == chess.BLACK and not player_is_white):
                won_phrase = phrase_list.get("won")
                if won_phrase:
                    print(f"\n{bot.get('name')} venceu: \"{won_phrase}\"")
            else:
                lost_phrase = phrase_list.get("lost")
                if lost_phrase:
                    print(f"\nVocê venceu! {bot.get('name')}: \"{lost_phrase}\"")
    finally:
        if polyglot_reader:
            polyglot_reader.close()
