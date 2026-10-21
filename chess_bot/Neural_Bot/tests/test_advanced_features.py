"""Suíte de Testes Automatizados para Recursos Avançados de Elite (100% Autônomo).

Cobre:
1. SE-ResNet (Squeeze-and-Excitation Residual Networks)
2. Bases de Finais Syzygy & Solver Exato Minimax
3. Validador Tático PVS com Poda por Lance Nulo (Blunder Guard)
4. MCTS Tensorizado com Batching e Virtual Loss
5. Pipeline de Auto-Aperfeiçoamento por Reforço (Self-Play)
6. Integração completa no NeuralChessBot
"""

import pytest
import chess
import torch
import torch.nn as nn

from chess_ai.model import ChessPolicyValueNet, SqueezeExcitationBlock, SEResidualBlock
from chess_ai.tablebase import (
    SyzygyTablebaseManager,
    is_endgame_position,
    find_tablebase_or_exact_endgame_move,
    solve_endgame_minimax,
)
from chess_ai.tactical_pvs import TacticalPVSEngine
from chess_ai.mcts import NeuralMCTS, MCTSNode
from chess_ai.self_play import SelfPlayTrainer, SelfPlayDataset
from chess_ai.agent import NeuralChessBot


def test_se_resnet_architecture():
    """Valida a arquitetura SE-ResNet e propagação forward/backward."""
    net = ChessPolicyValueNet(
        in_channels=18,
        num_channels=64,
        num_blocks=2,
        action_size=4096,
        use_se=True,
    )
    x = torch.randn(2, 18, 8, 8)
    policy_logits, values = net(x)

    assert policy_logits.shape == (2, 4096), f"Shape incorreto: {policy_logits.shape}"
    assert values.shape == (2, 1), f"Shape de valor incorreto: {values.shape}"

    # Validação do backward pass
    loss = policy_logits.sum() + values.sum()
    loss.backward()

    # Confirmação de gradientes nos pesos de Squeeze-and-Excitation
    found_grad = False
    for name, param in net.named_parameters():
        if "se" in name and param.grad is not None:
            found_grad = True
            break
    assert found_grad, "Gradientes não foram propagados nos blocos SE!"


def test_tablebase_and_exact_endgame():
    """Valida detecção de finais, probe Syzygy e solver exato anti-afogamento."""
    # Final KQvK: Brancas têm Rei em a1, Dama em b6. Pretas têm Rei em a8.
    # Brancas jogam e devem arrematar ou evitar afogamento.
    board = chess.Board("k7/8/1Q6/8/8/8/8/K7 w - - 0 1")
    assert is_endgame_position(board), "Deveria reconhecer posição com 3 peças como final"

    tb_manager = SyzygyTablebaseManager()
    result = find_tablebase_or_exact_endgame_move(board, tb_manager, max_depth=4)
    assert result is not None, "Solver exato de finais deveria encontrar lance"
    best_move, info = result
    assert best_move in board.legal_moves, "Lance do solver exato deve ser estritamente legal"

    # Verificar que o lance escolhido NÃO afoga o rei adversário (evitar Qb7 ou Qc7 que cause stalemate imediato)
    board.push(best_move)
    assert not board.is_stalemate(), f"O solver cometeu afogamento com {best_move}!"
    board.pop()


def test_tactical_pvs_blunder_guard():
    """Valida o PVS Blunder Guard: detecção de gafes e refutação tática."""
    engine = TacticalPVSEngine()

    # Posição onde as brancas têm uma gafe óbvia: pendurar a Dama em d4 com xeque descoberto
    # Tabuleiro: Brancas Kc1, Qd4. Pretas Ke8, Rd8 (Torre mirando na Dama).
    board = chess.Board("3rk3/8/8/8/3Q4/8/8/2K5 w - - 0 1")

    # Lance suicida da dama branca: jogar Qd4-d5 onde a torre preta toma Rd8xd5 de graça
    blunder_move = chess.Move.from_uci("d4d5")
    assert blunder_move in board.legal_moves

    chosen_move, info = engine.verify_and_refine_candidate(board, blunder_move, depth=4)

    # O PVS deve refutar Qd5 e escolher um lance de salvação (ex: Qe4+, Qd3, Qd1, etc.)
    assert chosen_move != blunder_move, "PVS Blunder Guard deveria ter refutado a pendura da Dama!"
    assert info.get("source") == "pvs_blunder_refutation"
    assert info.get("candidate_rejected") == board.san(blunder_move)


def test_batched_mcts_gpu_and_virtual_loss():
    """Valida busca MCTS com Virtual Loss e inferência tensorizada em lote."""
    model = ChessPolicyValueNet(
        in_channels=18,
        num_channels=32,
        num_blocks=2,
        use_se=False,
    )
    mcts = NeuralMCTS(model=model, device="cpu", c_puct=1.5)

    board = chess.Board()
    # Executa MCTS com batch_size = 4 e 16 simulações
    best_move, stats = mcts.search(board, num_simulations=16, batch_size=4)

    assert best_move in board.legal_moves, "MCTS deve retornar lance legal"
    assert "principal_variation" in stats, "Estatísticas devem conter PV"
    assert stats["simulations"] >= 16, "Simulações devem ser executadas"


def test_self_play_trainer_integration():
    """Valida componentes de treino por auto-confronto (Self-Play AlphaZero)."""
    model = ChessPolicyValueNet(
        in_channels=18,
        num_channels=32,
        num_blocks=2,
        use_se=False,
    )
    dataset = SelfPlayDataset(max_samples=100)

    # Adicionar transições sintéticas
    b = chess.Board()
    target_pi = {b.san(m): 1.0 / len(list(b.legal_moves)) for m in b.legal_moves}
    dataset.add_trajectory([b], [target_pi], outcome=1.0)

    assert len(dataset) == 1
    sample = dataset[0]
    assert sample["state"].shape == (18, 8, 8)
    assert sample["target_policy"].shape == (4096,)
    assert sample["target_value"].item() == 1.0


def test_neural_bot_end_to_end():
    """Valida o funcionamento integrado do NeuralChessBot com todas as proteções ativas."""
    model = ChessPolicyValueNet(
        in_channels=18,
        num_channels=32,
        num_blocks=2,
        use_se=True,
    )
    bot = NeuralChessBot(
        model=model,
        device="cpu",
        use_book=False,
        use_mcts=False,
        use_pvs_blunder_guard=True,
        pvs_depth=4,
    )

    # 1. Lance na posição inicial
    board = chess.Board()
    move, info = bot.get_best_move(board)
    assert move in board.legal_moves, f"Lance inicial deve ser legal: {move}"

    # 2. Resolução exata de final (KQvK)
    endgame_board = chess.Board("k7/8/1Q6/8/8/8/8/K7 w - - 0 1")
    eg_move, eg_info = bot.get_best_move(endgame_board)
    assert eg_move in endgame_board.legal_moves
    assert "endgame" in eg_info.get("source", "").lower() or "tablebase" in eg_info.get("source", "").lower()
