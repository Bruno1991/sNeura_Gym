@echo off
chcp 65001 > nul
title Duelo: Neural_Bot vs Maximum 3200 Elo
cls
echo =================================================================
echo   CONFRONTO DIRETO: NEURAL_BOT (RESNET) vs MAXIMUM (3200 ELO)
echo =================================================================
echo.
echo Iniciando partida entre os dois bots locais...
echo.
python "%~dp0batalha_neural_vs_3200.py" --delay 1.0
pause
