@echo off
@chcp 65001 >nul
title Slither AI - Treinamento Continuo 24/7 (Maestria)
cd /d "%~dp0"
set PYTHONWARNINGS=ignore::FutureWarning
set PYTHONIOENCODING=utf-8
echo =============================================================
echo   Slither AI - Treinamento Continuo 24/7 para Maestria
echo   Auto-play GPU, Benchmark de Recordes e Pesos de Ouro
echo   Pressione Ctrl+C a qualquer momento para sair salvando
echo =============================================================
python scripts\run_training_247.py %*
pause
