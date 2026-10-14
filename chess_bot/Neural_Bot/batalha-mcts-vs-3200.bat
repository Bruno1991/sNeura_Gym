@echo off
chcp 65001 > nul
title Duelo: Neural_Bot (MCTS) vs Maximum 3200 Elo
cls
echo =================================================================
echo   CONFRONTO DIRETO: NEURAL_BOT (MCTS TREE SEARCH) vs MAXIMUM 3200
echo =================================================================
echo.
echo Iniciando duelo com busca em arvore MCTS (50 simulacoes/lance)...
echo.
python "%~dp0batalha_neural_vs_3200.py" --mcts --mcts-sims 50 --delay 0.8
pause
