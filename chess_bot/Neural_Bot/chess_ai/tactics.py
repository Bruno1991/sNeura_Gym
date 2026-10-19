"""Módulo de Verificação Tática e Guarda Anti-Blunder (Tactical Shield & Mini-Quiescence).

Protege o agente neural contra blunders táticos comuns (peças penduradas, garfos,
espetos, capturas sem defesa e mates em 1 ou 2 lances), garantindo solidez tática
sem comprometer a velocidade de inferência na GPU.
"""

from typing import Any, Dict, List, Optional, Tuple
import chess

# Valores padrão de material em centipawns
PIECE_VALUES: Dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


def get_piece_value(piece: Optional[chess.Piece]) -> int:
    """Retorna o valor material de uma peça ou 0 se casa vazia."""
    if piece is None:
        return 0
    return PIECE_VALUES.get(piece.piece_type, 0)


def evaluate_tactical_safety(board: chess.Board, move: chess.Move) -> Tuple[bool, int, str]:
    """Avalia a segurança tática de um lance a 1-2 plies à frente.

    Verifica:
    1. Se o adversário ganha por xeque-mate imediato (-20.000).
    2. Se a peça movida foi colocada em casa atacada por peça de menor valor sem compensação.
    3. Se o adversário possui captura direta forçada com ganho líquido de material (>= 180 centipawns).

    Retorna:
        (is_safe: bool, net_material_delta: int, reason: str)
    """
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return True, 0, "ok"

    moving_val = get_piece_value(moving_piece)
    target_piece = board.piece_at(move.to_square)
    target_val = get_piece_value(target_piece)
    moving_color = board.turn
    opp_color = not moving_color

    board.push(move)

    # 0. Checagem de afogamento (stalemate): se estamos em vantagem de material, afogar é blunder fatal
    if board.is_stalemate():
        mat_cur = sum(get_piece_value(p) for p in board.piece_map().values() if p.color == moving_color)
        mat_opp = sum(get_piece_value(p) for p in board.piece_map().values() if p.color == opp_color)
        if mat_cur > mat_opp + 150:
            board.pop()
            return False, -30000, "stalemate_blunder"

    # 1. Checagem de xeque-mate imediato do oponente (mate em 1) e mate forçado em 2
    for opp_m in board.legal_moves:
        board.push(opp_m)
        if board.is_checkmate():
            board.pop()
            board.pop()
            return False, -20000, "opp_checkmate"

        # Detector de mate forçado em 2 (se o lance for xeque e todas as respostas levarem a mate)
        if board.is_check():
            replies = list(board.legal_moves)
            if replies and len(replies) <= 4:
                all_replies_mated = True
                for rep in replies:
                    board.push(rep)
                    has_finishing_mate = any(
                        (board.push(final_m), board.is_checkmate(), board.pop())[1]
                        for final_m in board.legal_moves
                    )
                    board.pop()
                    if not has_finishing_mate:
                        all_replies_mated = False
                        break
                if all_replies_mated:
                    board.pop()
                    board.pop()
                    return False, -20000, "opp_forced_mate_in_2"

        board.pop()

    # 2. Análise de capturas e ameaças táticas forçadas (garfos) do oponente em resposta
    worst_opp_gain = 0
    threat_reason = "safe"
    for opp_m in board.legal_moves:
        if board.is_capture(opp_m):
            captured = board.piece_at(opp_m.to_square)
            cap_val = get_piece_value(captured)
            attacker = board.piece_at(opp_m.from_square)
            att_val = get_piece_value(attacker)

            is_defended = board.is_attacked_by(moving_color, opp_m.to_square)
            if not is_defended:
                # Peça pendurada sem defesa: perda total do valor da peça
                gain = cap_val
            else:
                # Peça defendida: ganho líquido é a diferença entre a capturada e o atacante
                gain = max(0, cap_val - att_val)

            # Se a resposta do oponente for um xeque com captura, o perigo tático é dobrado
            board.push(opp_m)
            if board.is_check() and gain > 0:
                gain += 200
            board.pop()

            if gain > worst_opp_gain:
                worst_opp_gain = gain
                threat_reason = "hanging_material"
        else:
            # 2.1 Análise de lances silenciosos mortais: Garfos e Ataques Duplos (ex: Cavalo/Bispo em c7/d6)
            board.push(opp_m)
            sq = opp_m.to_square
            attacker = board.piece_at(sq)
            if attacker:
                att_val = get_piece_value(attacker)
                attacks = board.attacks(sq)
                vulnerable = []
                for s in attacks:
                    p = board.piece_at(s)
                    if p and p.color == moving_color:
                        val = get_piece_value(p)
                        # Alvo vulnerável: Rei (xeque forçado), peça de maior valor ou peça desprotegida
                        if val > att_val or not board.is_attacked_by(moving_color, s):
                            vulnerable.append(val)
                is_counter_attacked = board.is_attacked_by(moving_color, sq)
                if len(vulnerable) >= 2 and not is_counter_attacked:
                    vulnerable.sort(reverse=True)
                    # O defensor só pode salvar 1 peça no lance seguinte; a 2ª mais valiosa é perdida
                    fork_gain = vulnerable[1]
                    if fork_gain > worst_opp_gain:
                        worst_opp_gain = fork_gain
                        threat_reason = f"fork_threat_{opp_m.uci()}"
            board.pop()

    board.pop()

    # Balanço líquido do lance: o que ganhamos (target_val) menos a pior perda imediata (worst_opp_gain)
    net_gain = target_val - worst_opp_gain

    # Se a perda líquida for >= 90 centipawns (qualquer peão desprotegido pendurado), é taticamente perigoso
    if net_gain <= -90:
        return False, net_gain, threat_reason

    return True, net_gain, "safe"


def find_punitive_captures(board: chess.Board) -> List[Tuple[chess.Move, int, str]]:
    """Identifica capturas imediatas que punem peças penduradas do adversário com ganho líquido >= 100 cp.
    
    Procura por lances de captura taticamente seguros que ganhem material limpo (peão passado,
    peça menor, torre ou dama desprotegida/insuficientemente defendida).
    """
    punishments: List[Tuple[chess.Move, int, str]] = []
    for m in board.legal_moves:
        if board.is_capture(m):
            is_safe, net_delta, reason = evaluate_tactical_safety(board, m)
            if is_safe and net_delta >= 100:
                punishments.append((m, net_delta, reason))

    # Ordena pelo maior ganho líquido de material (dama > torre > bispo/cavalo > peão)
    punishments.sort(key=lambda x: x[1], reverse=True)
    return punishments


def rank_candidates_with_tactical_shield(
    board: chess.Board,
    candidate_moves: List[Tuple[chess.Move, float]],
    max_eval_candidates: int = 12,
    enable_punishment_trigger: bool = True,
) -> List[Tuple[chess.Move, float, bool]]:
    """Aplica o escudo tático com Gatilho Punitivo Voraz aos melhores candidatos.

    1. Garante que nunca execute um lance suicida se houver alternativa segura.
    2. Identifica ativamente gafes do adversário: se houver peça pendurada com ganho líquido >= 180 cp,
       prioriza a punição imediata para converter a vantagem em vitória.
    3. Reordena os candidatos seguros equilibrando a preferência neural e o ganho material concreto.

    Retorna:
        Lista de tuplas (move, prob, is_safe) ordenada pela melhor opção tática e estratégica.
    """
    if not candidate_moves:
        return []

    # 1. Identificar possíveis punições imediatas de peças penduradas
    punitive_moves_dict: Dict[chess.Move, int] = {}
    if enable_punishment_trigger:
        for p_move, net_delta, _ in find_punitive_captures(board):
            punitive_moves_dict[p_move] = net_delta

    evaluated: List[Tuple[chess.Move, float, bool, int, float]] = []
    safe_list: List[Tuple[chess.Move, float, bool, int, float]] = []

    # Injetar capturas punitivas de alto valor (>= 180 cp) caso a rede não as tenha colocado no topo
    merged_candidates: List[Tuple[chess.Move, float]] = list(candidate_moves)
    existing_moves = {m for m, _ in candidate_moves}
    for p_move, net_delta in punitive_moves_dict.items():
        if net_delta >= 180 and p_move not in existing_moves:
            # Insere como candidato com probabilidade base razoável
            merged_candidates.append((p_move, 0.20))

    for i, (m, prob) in enumerate(merged_candidates):
        if i < max_eval_candidates or len(safe_list) < 2:
            is_safe, net_delta, reason = evaluate_tactical_safety(board, m)

            # Cálculo de score composto: Probabilidade Neural + Bônus de Material Ganho
            # Ganhos materiais de peças penduradas adicionam até +0.90 (Dama) ou +0.32 (Bispo/Cavalo)
            material_bonus = max(0, net_delta) / 1000.0
            composite_score = prob + material_bonus

            # Se o lance dá xeque-mate imediato, bônus supremo
            board.push(m)
            if board.is_checkmate():
                composite_score += 10.0
            board.pop()

            evaluated.append((m, prob, is_safe, net_delta, composite_score))
            if is_safe:
                safe_list.append((m, prob, is_safe, net_delta, composite_score))
        else:
            break

    # Se encontramos lances seguros, reordenamos pelo score composto (intuição + punição)
    if safe_list:
        safe_list.sort(key=lambda x: x[4], reverse=True)
        return [(m, prob, True) for m, prob, _, _, _ in safe_list]

    # Se absolutamente nenhum lance seguro foi encontrado, escolhe o de menor prejuízo material
    evaluated.sort(key=lambda x: (x[3], x[1]), reverse=True)
    return [(m, prob, False) for m, prob, _, _, _ in evaluated]


# ==============================================================================
# ENDGAME FINISHING SHIELD (MÓDULO DE XEQUE-MATE RÁPIDO & CAÇA A PEÕES)
# ==============================================================================
def chebyshev_dist(sq1: int, sq2: int) -> int:
    """Calcula a distância Chebyshev (em casas de rei) entre dois quadrados."""
    f1, r1 = chess.square_file(sq1), chess.square_rank(sq1)
    f2, r2 = chess.square_file(sq2), chess.square_rank(sq2)
    return max(abs(f1 - f2), abs(r1 - r2))


def center_dist(sq: int) -> int:
    """Distância de uma casa até o centro do tabuleiro (0 no centro, até 6 nas bordas/cantos)."""
    f, r = chess.square_file(sq), chess.square_rank(sq)
    return max(3 - f, f - 4) + max(3 - r, r - 4)


def is_decisive_endgame(board: chess.Board) -> bool:
    """Detecta se a posição é um final ganho que exige técnica de arremate por encurralamento."""
    my_color = board.turn
    opp_color = not my_color
    piece_map = board.piece_map()
    total_pieces = len(piece_map)

    my_heavy = sum(1 for p in piece_map.values() if p.color == my_color and p.piece_type in (chess.QUEEN, chess.ROOK))
    my_minors = sum(1 for p in piece_map.values() if p.color == my_color and p.piece_type in (chess.BISHOP, chess.KNIGHT))

    opp_heavy = sum(1 for p in piece_map.values() if p.color == opp_color and p.piece_type in (chess.QUEEN, chess.ROOK))
    opp_minors = sum(1 for p in piece_map.values() if p.color == opp_color and p.piece_type in (chess.BISHOP, chess.KNIGHT))

    vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
    my_mat = sum(vals.get(p.piece_type, 0) for p in piece_map.values() if p.color == my_color)
    opp_mat = sum(vals.get(p.piece_type, 0) for p in piece_map.values() if p.color == opp_color)
    mat_lead = my_mat - opp_mat

    # Caso 1: Oponente sem peças pesadas/menores (só Rei ou Rei + peões) e nós temos Dama/Torre/Vantagem >= 300
    if opp_heavy == 0 and opp_minors == 0 and (my_heavy >= 1 or mat_lead >= 300):
        return True

    # Caso 2: Oponente tem no máximo 1 peça menor e nós temos Dama/Torre com vantagem >= 400
    if opp_heavy == 0 and opp_minors <= 1 and my_heavy >= 1 and mat_lead >= 400:
        return True

    # Caso 3: Tabuleiro com poucas peças (<= 8 peças) e liderança de material >= 250
    if total_pieces <= 8 and mat_lead >= 250:
        return True

    return False


def evaluate_endgame_state(board: chess.Board, my_color: chess.Color) -> int:
    """Avaliação de final com forte incentivo geométrico a encurralar o Rei inimigo e caçar peões."""
    if board.is_checkmate():
        return 50000 if board.turn != my_color else -50000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    opp_color = not my_color
    my_k = board.king(my_color)
    opp_k = board.king(opp_color)

    vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
    my_mat = sum(vals.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == my_color)
    opp_mat = sum(vals.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == opp_color)
    score = (my_mat - opp_mat) * 10

    if my_k is not None and opp_k is not None:
        if my_mat > opp_mat + 250:
            # 1. Empurrar o rei inimigo para a borda / cantos
            score += center_dist(opp_k) * 150
            # 2. Aproximar o nosso rei do rei adversário
            dist = chebyshev_dist(my_k, opp_k)
            score += (7 - dist) * 200
            # 3. Restringir mobilidade do rei oponente
            opp_moves = len([m for m in board.legal_moves if m.from_square == opp_k])
            score += (8 - opp_moves) * 100
            # 4. Caçar peões remanescentes do adversário (cada peão eliminado elimina contrajogo)
            opp_pawns = sum(1 for p in board.piece_map().values() if p.color == opp_color and p.piece_type == chess.PAWN)
            score += (8 - opp_pawns) * 150

    return score if board.turn == my_color else -score


def endgame_alpha_beta(
    board: chess.Board, depth: int, alpha: int, beta: int, my_color: chess.Color
) -> Tuple[int, Optional[chess.Move]]:
    """Busca em profundidade rasa (depth 3-4) com Alpha-Beta para arremate em finais."""
    if depth == 0 or board.is_game_over():
        return evaluate_endgame_state(board, my_color), None

    best_move = None
    if board.turn == my_color:
        max_eval = -1000000
        # Ordenação heurística: mates primeiro, depois capturas, xeques e avanços de rei
        def move_sort_key(m: chess.Move) -> int:
            board.push(m)
            is_cm = board.is_checkmate()
            is_sm = board.is_stalemate()
            is_chk = board.is_check()
            board.pop()
            if is_cm:
                return 10000
            if is_sm:
                return -10000
            score = 0
            if board.is_capture(m):
                score += 500
            if is_chk:
                score += 200
            if m.from_square == board.king(my_color):
                score += 150
            return score

        legals = sorted(board.legal_moves, key=move_sort_key, reverse=True)
        for move in legals:
            board.push(move)
            # Evita afogamento imediato se estivermos ganhando
            if board.is_stalemate():
                board.pop()
                continue
            eval_val, _ = endgame_alpha_beta(board, depth - 1, alpha, beta, my_color)
            board.pop()

            if eval_val > max_eval:
                max_eval = eval_val
                best_move = move
            alpha = max(alpha, eval_val)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = 1000000
        legals = list(board.legal_moves)
        for move in legals:
            board.push(move)
            eval_val, _ = endgame_alpha_beta(board, depth - 1, alpha, beta, my_color)
            board.pop()

            if eval_val < min_eval:
                min_eval = eval_val
                best_move = move
            beta = min(beta, eval_val)
            if beta <= alpha:
                break
        return min_eval, best_move


def find_endgame_finishing_move(board: chess.Board, max_depth: int = 4) -> Optional[Tuple[chess.Move, Dict[str, Any]]]:
    """Identifica e retorna o melhor lance de arremate se estiver em final decisivo."""
    if not is_decisive_endgame(board):
        return None

    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    # 1. Mate em 1 imediato
    for m in legal_moves:
        board.push(m)
        if board.is_checkmate():
            board.pop()
            return m, {
                "source": "endgame_instant_mate",
                "san": board.san(m),
                "probability": 1.0,
                "value": 1.0,
            }
        board.pop()

    # 2. Solver Alpha-Beta de encurralamento com depth 4
    val, best_move = endgame_alpha_beta(
        board, depth=max_depth, alpha=-1000000, beta=1000000, my_color=board.turn
    )

    if best_move is not None:
        return best_move, {
            "source": "endgame_finisher",
            "san": board.san(best_move),
            "eval_score": val,
            "probability": 1.0,
            "value": 1.0,
        }

    return None

