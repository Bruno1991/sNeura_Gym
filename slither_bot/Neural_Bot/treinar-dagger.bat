@chcp 65001 >nul
@echo off
title Slither AI - Destilacao DAgger (GPU Max Speed)
cd /d "%~dp0"
echo =============================================================
echo   Slither AI - Treinamento por Destilacao Ativa DAgger
echo   Converte a IA do APK em Pesos Neurais na GPU
echo =============================================================
python scripts\run_training_dagger.py
pause
