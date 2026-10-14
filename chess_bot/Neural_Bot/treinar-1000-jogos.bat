@echo off
chcp 65001 > nul
title Treinamento 1000 Partidas: Neural vs Maximum 3200 (GPU)
cls
echo =================================================================
echo   CHESS NEURAL BOT - CICLO DE 1000 PARTIDAS CONTRA BOT 3200 ELO
echo =================================================================
echo.
echo Iniciando simulador de partidas e otimizacao na GPU (RTX 3060)...
echo.
python "%~dp0scripts\train_1000_games.py" --games 1000 --cycle-games 50 --epochs 3
pause
