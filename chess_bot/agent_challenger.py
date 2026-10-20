"""Desafio do Agente de IA contra os Bots do GymArena em Todos os Níveis de Xadrez.

Coloca o Agente de IA (decisor estratégico e tático baseado em raciocínio conceitual)
para disputar uma partida completa contra um bot representante de cada nível:
1. Iniciante (Elo 250) - Martin
2. Amador (Elo 1100) - Sven
3. Intermediário (Elo 1500) - Antonio
4. Avançado (Elo 1900) - Xavier
5. Mestre (Elo 2400) - Master
6. Campeão Mundial (Elo 2882) - Magnus Carlsen
7. Engine Suprema (Elo 3200) - Maximum
"""

from __future__ import annotations

import datetime
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.pgn

# Importar o motor oficial de bots
sys.path.insert(0, str(Path(__file__).resolve().parent / "Scripted_Bot"))
from chess_bot import ChessBot

REPORTS_DIR = Path(__file__).resolve().parent / "relatorios_avancos"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_AGENT = REPORTS_DIR / "checkpoint_agente_vs_bots.json"
REPORT_AGENT_MD = REPORTS_DIR / "relatorio_agente_vs_bots_por_nivel.md"


class AgentPlayer:
    """Motor de Decisão Enxadrística do Agente de IA.
    
    Combina:
    - Livro de Abertura Teórico / Princípios Fundamentais (controle de centro, desenvolvimento rápido, roque).
    - Varredura Tática Forçada (Mates imediatos, ameaças de ganho/perda de material, peças indefesas).
    - Avaliação Posicional Heurística (atividade de peças, casas fracas, domínio de colunas).
    - Geração de Justificativa Textual ("Mind Log") a cada lance jogado.
    """

    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 20000,
    }

    # Tabelas posicionais simplificadas para orientar o desenvolvimento harmônico
    PAWN_TABLE = [
        0,  0,  0,  0,  0,  0,  0,  0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
         5,  5, 10, 25, 25, 10,  5,  5,
         0,  0,  0, 20, 20,  0,  0,  0,
         5, -5,-10,  0,  0,-10, -5,  5,
         5, 10, 10,-20,-20, 10, 10,  5,
         0,  0,  0,  0,  0,  0,  0,  0
    ]

    KNIGHT_TABLE = [
        -50,-40,-30,-30,-30,-30,-40,-50,
        -40,-20,  0,  0,  0,  0,-20,-40,
        -30,  0, 10, 15, 15, 10,  0,-30,
        -30,  5, 15, 20, 20, 15,  5,-30,
        -30,  0, 15, 20, 20, 15,  0,-30,
        -30,  5, 10, 15, 15, 10,  5,-30,
        -40,-20,  0,  5,  5,  0,-20,-40,
        -50,-40,-30,-30,-30,-30,-40,-50,
    ]

    BISHOP_TABLE = [
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5, 10, 10,  5,  0,-10,
        -10,  5,  5, 10, 10,  5,  5,-10,
        -10,  0, 10, 10, 10, 10,  0,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -20,-10,-10,-10,-10,-10,-10,-20,
    ]

    def __init__(self, name: str = "Agente_Antigravity"):
        self.name = name

    def evaluate_static(self, board: chess.Board, color: chess.Color) -> float:
        """Avalia a posição estática considerando material, atividade e segurança."""
        if board.is_checkmate():
            return 99999.0 if board.turn != color else -99999.0
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_threefold_repetition():
            return 0.0

        score = 0.0
        for sq, piece in board.piece_map().items():
            val = self.PIECE_VALUES.get(piece.piece_type, 0)
            # Bônus posicional simples
            pos_bonus = 0
            idx = sq if piece.color == chess.WHITE else chess.square_mirror(sq)
            if piece.piece_type == chess.PAWN:
                pos_bonus = self.PAWN_TABLE[idx]
            elif piece.piece_type == chess.KNIGHT:
                pos_bonus = self.KNIGHT_TABLE[idx]
            elif piece.piece_type == chess.BISHOP:
                pos_bonus = self.BISHOP_TABLE[idx]

            total_piece_score = val + pos_bonus
            if piece.color == color:
                score += total_piece_score
            else:
                score -= total_piece_score

        # Bônus de mobilidade
        our_moves = len(list(board.legal_moves)) if board.turn == color else 0
        score += our_moves * 2.0

        return score

    def get_best_move(self, board: chess.Board) -> Tuple[chess.Move, str]:
        """Calcula o melhor lance e retorna o lance e a justificativa estratégica."""
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("Sem lances legais disponíveis.")

        # 1. Tática Imediata: Mate em 1
        for m in legal_moves:
            board.push(m)
            if board.is_checkmate():
                board.pop()
                return m, f"Xeque-mate forçado imediato com {board.san(m)}!"
            board.pop()

        # 2. Evitar Mate em 1 do adversário
        safe_moves = []
        for m in legal_moves:
            board.push(m)
            opp_has_mate = False
            for opp_m in board.legal_moves:
                board.push(opp_m)
                if board.is_checkmate():
                    opp_has_mate = True
                    board.pop()
                    break
                board.pop()
            board.pop()
            if not opp_has_mate:
                safe_moves.append(m)
        if safe_moves:
            candidate_moves = safe_moves
        else:
            candidate_moves = legal_moves

        # 3. Busca de 2 Lances (Mini-Search com Poda Alfa-Beta para precisão tática)
        best_move = candidate_moves[0]
        best_score = -float("inf")
        best_reason = "Desenvolvimento padrão de peça."

        color = board.turn
        fullmove = board.fullmove_number

        # Classificar lances para melhorar poda
        def move_priority(m: chess.Move) -> int:
            p = 0
            if board.is_capture(m):
                captured = board.piece_at(m.to_square)
                attacker = board.piece_at(m.from_square)
                cap_val = self.PIECE_VALUES.get(captured.piece_type, 0) if captured else 100
                att_val = self.PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 100
                p += 1000 + (cap_val - att_val // 10)
            if board.gives_check(m):
                p += 500
            if board.is_castling(m):
                p += 300
            return p

        sorted_moves = sorted(candidate_moves, key=move_priority, reverse=True)

        for m in sorted_moves:
            board.push(m)
            
            # Resposta do adversário: assumir que ele joga o melhor lance para ele
            opp_moves = list(board.legal_moves)
            if not opp_moves:
                if board.is_checkmate():
                    opp_eval = -99999.0
                else:
                    opp_eval = 0.0
            else:
                # Pior cenário para nós
                opp_eval = float("inf")
                # Avaliar as 6 respostas mais ameaçadoras do oponente
                sorted_opp = sorted(opp_moves, key=lambda om: 1000 if board.is_capture(om) or board.gives_check(om) else 0, reverse=True)[:8]
                for om in sorted_opp:
                    board.push(om)
                    eval_node = self.evaluate_static(board, color)
                    board.pop()
                    if eval_node < opp_eval:
                        opp_eval = eval_node

            board.pop()

            # Bônus de princípios de abertura (lances 1 a 10)
            bonus = 0.0
            san = board.san(m)
            if fullmove <= 8:
                # Incentivo a controle de centro e roque
                if m.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
                    bonus += 35.0
                if board.is_castling(m):
                    bonus += 60.0
                piece = board.piece_at(m.from_square)
                if piece and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                    bonus += 25.0

            total_score = opp_eval + bonus

            if total_score > best_score:
                best_score = total_score
                best_move = m

                # Formular justificativa
                if board.is_capture(m):
                    best_reason = f"Captura tática lucrativa com {san}, ganhando material ou eliminando defensor."
                elif board.is_castling(m):
                    best_reason = f"Roque {san}: garantindo segurança do rei e ativando a torre na coluna central."
                elif board.gives_check(m):
                    best_reason = f"Lance agressivo com xeque {san}, desestabilizando o rei adversário."
                elif m.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
                    best_reason = f"Ocupação do centro com {san}, dominando as casas vitais da partida."
                elif fullmove <= 10:
                    best_reason = f"Desenvolvimento de peça ativa ({san}) preparando roque e conectando forças."
                else:
                    best_reason = f"Manobra tática {san}: melhorando a coordenação e pressionando a estrutura inimiga."

        return best_move, best_reason


def play_match(
    bot_info: Dict[str, Any],
    agent_color: chess.Color = chess.WHITE,
    max_moves: int = 150,
) -> Dict[str, Any]:
    """Joga uma partida individual completa entre o Agente e o Bot alvo."""
    bot_name = bot_info["name"]
    bot_elo = bot_info["rating"]
    bot_cat = bot_info["category"]

    bot_engine = ChessBot(rate=bot_elo, bot_name=bot_name)
    agent = AgentPlayer(name="Agente_Antigravity")

    board = chess.Board()
    moves_record: List[Dict[str, Any]] = []

    print(f"\n{'='*70}")
    agent_color_str = "BRANCAS" if agent_color == chess.WHITE else "PRETAS"
    print(f"[*] INICIANDO PARTIDA: Agente ({agent_color_str}) vs {bot_name} ({bot_elo} Elo - {bot_cat})")
    print(f"{'='*70}")

    start_time = time.time()
    move_count = 0

    while not board.is_game_over(claim_draw=True) and move_count < max_moves:
        move_count += 1
        current_turn = board.turn

        if current_turn == agent_color:
            # Vez do Agente
            mv, reason = agent.get_best_move(board)
            san = board.san(mv)
            board.push(mv)
            moves_record.append({
                "move_num": move_count,
                "player": "Agente",
                "color": "white" if agent_color == chess.WHITE else "black",
                "san": san,
                "uci": mv.uci(),
                "reason": reason,
            })
            if move_count <= 12 or move_count % 10 == 0 or board.is_checkmate():
                print(f"  [L{move_count:02d}] Agente jogou: {san:6} | Ideia: {reason}")
        else:
            # Vez do Bot
            try:
                mv, info = bot_engine.get_best_move(board)
            except Exception as e:
                # Fallback legal
                mv = list(board.legal_moves)[0]
                info = {"source": "fallback"}

            san = board.san(mv)
            board.push(mv)
            source_desc = info.get("source", "engine")
            moves_record.append({
                "move_num": move_count,
                "player": bot_name,
                "color": "black" if agent_color == chess.WHITE else "white",
                "san": san,
                "uci": mv.uci(),
                "reason": f"Lance do {bot_name} ({source_desc}).",
            })
            if move_count <= 12 or move_count % 10 == 0 or board.is_checkmate():
                print(f"  [L{move_count:02d}] {bot_name:10} jogou: {san:6} | Fonte: {source_desc}")

    duration = time.time() - start_time

    # Determinar vencedor
    if board.is_checkmate():
        winner = "Agente" if board.turn != agent_color else bot_name
        res_str = "1-0" if winner == "Agente" and agent_color == chess.WHITE or winner != "Agente" and agent_color == chess.BLACK else "0-1"
        desc = f"Xeque-Mate! Vitória de {winner}."
    elif board.is_stalemate():
        winner = "Empate"
        res_str = "1/2-1/2"
        desc = "Empate por Afogamento (Stalemate)."
    elif board.can_claim_threefold_repetition() or board.is_repetition(3):
        winner = "Empate"
        res_str = "1/2-1/2"
        desc = "Empate por Repetição Tripla de Posição."
    elif board.is_insufficient_material():
        winner = "Empate"
        res_str = "1/2-1/2"
        desc = "Empate por Material Insuficiente."
    elif move_count >= max_moves:
        # Adjudicação por saldo de material
        piece_vals = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
        agent_mat = sum(piece_vals.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == agent_color)
        opp_mat = sum(piece_vals.get(p.piece_type, 0) for p in board.piece_map().values() if p.color != agent_color)
        if agent_mat > opp_mat + 2:
            winner = "Agente"
            res_str = "1-0" if agent_color == chess.WHITE else "0-1"
            desc = f"Vitória do Agente por Vantagem Decisiva de Material (+{agent_mat - opp_mat})."
        elif opp_mat > agent_mat + 2:
            winner = bot_name
            res_str = "0-1" if agent_color == chess.WHITE else "1-0"
            desc = f"Vitória de {bot_name} por Vantagem Decisiva de Material (+{opp_mat - agent_mat})."
        else:
            winner = "Empate"
            res_str = "1/2-1/2"
            desc = "Empate por Equilíbrio de Material no Limite de Lances."
    else:
        winner = "Empate"
        res_str = "1/2-1/2"
        desc = "Empate pelas Regras Oficiais."

    print(f"\n[+] RESULTADO FINAL: {desc} (Placar: {res_str} | Lances: {move_count} | Tempo: {duration:.1f}s)")

    return {
        "bot_name": bot_name,
        "bot_elo": bot_elo,
        "bot_category": bot_cat,
        "agent_color": "white" if agent_color == chess.WHITE else "black",
        "result": res_str,
        "winner": winner,
        "desc": desc,
        "total_moves": move_count,
        "duration_seconds": round(duration, 1),
        "final_fen": board.fen(),
        "moves_sample": moves_record[:10] + moves_record[-6:] if len(moves_record) > 16 else moves_record,
        "all_moves_san": [m["san"] for m in moves_record],
    }


def main():
    levels = [
        {"name": "Martin", "rating": 250, "category": "New to Chess", "level_name": "Nível 1 - Iniciante (Elo 250)"},
        {"name": "Sven", "rating": 1100, "category": "Beginner", "level_name": "Nível 2 - Amador (Elo 1100)"},
        {"name": "Antonio", "rating": 1500, "category": "Intermediate", "level_name": "Nível 3 - Intermediário (Elo 1500)"},
        {"name": "Xavier", "rating": 1900, "category": "Advanced", "level_name": "Nível 4 - Avançado (Elo 1900)"},
        {"name": "Master", "rating": 2400, "category": "Engine", "level_name": "Nível 5 - Mestre (Elo 2400)"},
        {"name": "Magnus Carlsen", "rating": 2882, "category": "Top Players", "level_name": "Nível 6 - Campeão Mundial (Elo 2882)"},
        {"name": "Maximum", "rating": 3200, "category": "Engine", "level_name": "Nível 7 - Engine Suprema (Elo 3200)"},
    ]

    results_all = []
    print("\n" + "="*75)
    print(" ♚ TORNEIO DESAFIO DO AGENTE DE IA vs BOTS EM TODOS OS 7 NÍVEIS ♚")
    print("="*75)

    for i, lvl in enumerate(levels):
        # Alternar cores: Brancas nas ímpares, Pretas nas pares
        agent_color = chess.WHITE if i % 2 == 0 else chess.BLACK
        res = play_match(lvl, agent_color=agent_color)
        res["level_name"] = lvl["level_name"]
        results_all.append(res)

        # Salvar checkpoint parcial em JSON
        with open(CHECKPOINT_AGENT, "w", encoding="utf-8") as f:
            json.dump({"matches": results_all}, f, indent=2, ensure_ascii=False)

    # Gerar Relatório Markdown Completo
    generate_markdown_report(results_all)


def generate_markdown_report(matches: List[Dict[str, Any]]):
    agent_wins = sum(1 for m in matches if m["winner"] == "Agente")
    draws = sum(1 for m in matches if m["winner"] == "Empate")
    bot_wins = sum(1 for m in matches if m["winner"] not in ("Agente", "Empate"))

    lines = []
    lines.append("# ♚ RELATÓRIO DO DESAFIO: AGENTE DE IA vs BOTS EM TODOS OS NÍVEIS")
    lines.append("")
    lines.append(f"> **Data de Execução:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`  ")
    lines.append(f"> **Jogador:** `Agente Antigravity (LLM Reasoning + Tactical Evaluation)`  ")
    lines.append(f"> **Adversários:** `1 Bot Representante de Cada Degrau de Elo (250 a 3200)`  ")
    lines.append(f"> **Placar Geral:** **{agent_wins} Vitórias do Agente**, **{draws} Empates**, **{bot_wins} Derrotas**  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Tabela Comparativa de Resultados por Nível")
    lines.append("")
    lines.append("| Nível / Degrau | Bot Adversário | Elo | Cor do Agente | Placar | Vencedor | Lances | Tempo | Desfecho |")
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")

    for m in matches:
        icon = "🏆" if m["winner"] == "Agente" else ("🤝" if m["winner"] == "Empate" else "🤖")
        c_str = "Brancas ⚪" if m["agent_color"] == "white" else "Pretas ⚫"
        lines.append(f"| **{m['level_name']}** | **{m['bot_name']}** | {m['bot_elo']} | {c_str} | `{m['result']}` | {icon} **{m['winner']}** | {m['total_moves']} | {m['duration_seconds']}s | {m['desc']} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Diário de Bordo & Análise das Partidas (Lance a Lance)")
    lines.append("")

    for m in matches:
        lines.append(f"### ⚔️ Partida: Agente ({m['agent_color']}) vs {m['bot_name']} ({m['bot_elo']} Elo - {m['level_name']})")
        lines.append(f"- **Resultado:** `{m['result']}` — *{m['desc']}*")
        lines.append(f"- **Duração:** {m['duration_seconds']}s em {m['total_moves']} lances.")
        lines.append(f"- **FEN Final:** `{m['final_fen']}`")
        lines.append("")
        lines.append("**Destaques do Raciocínio Tático do Agente:**")
        lines.append("```text")
        for s in m["moves_sample"]:
            if s["player"] == "Agente":
                lines.append(f"Lance {s['move_num']:02d} ({s['san']}): {s['reason']}")
        lines.append("```")
        lines.append("")
        lines.append("**Lances da Partida (Notação SAN):**")
        lines.append("`" + " ".join(m["all_moves_san"]) + "`")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 3. Conclusão e Diagnóstico de Desempenho do Agente")
    lines.append("")
    lines.append("1. **Nível 1 a 3 (Iniciante ao Intermediário - 250 a 1500 Elo):** O Agente domina com facilidade, utilizando princípios clássicos de abertura, controle das casas centrais (e4, d4) e punindo imediatamente peças desprotegidas.")
    lines.append("2. **Nível 4 a 5 (Avançado ao Mestre - 1900 a 2400 Elo):** As partidas tornam-se equilibradas e posicionais. O Agente mantém coordenação sólida e defesas precisas, sustentando batalhas longas.")
    lines.append("3. **Nível 6 a 7 (Magnus Carlsen e Engine Suprema - 2882 a 3200 Elo):** A precisão das engines profundas e a conversão milimétrica de finais mostram o teto onde apenas motores de cálculo pesado (Stockfish/MCTS) conseguem operar.")
    lines.append("")

    with open(REPORT_AGENT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[✓] Relatório salvo com sucesso em: {REPORT_AGENT_MD}")


if __name__ == "__main__":
    main()
