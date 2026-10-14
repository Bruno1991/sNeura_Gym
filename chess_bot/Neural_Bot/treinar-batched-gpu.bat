@echo off
chcp 65001 > nul
title BatchedRLTrainer - 64 Workers Paralelos + AMP FP16

echo ===============================================================================
echo     INICIANDO TREINAMENTO PARALELO: 64 WORKERS + AMP FP16 (RTX 3060)
echo ===============================================================================
echo.

python "%~dp0scripts\train_batched_rl.py" --workers 64 --games 1000 --cycle-games 100 --batch-size 512

echo.
pause
