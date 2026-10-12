@echo off
title Slither AI - Destilação DAgger (GPU Max Speed)
chcp 65001 >nul
cd /d "%~dp0"
echo =============================================================
echo   Slither AI - Treinamento por Destilação Ativa DAgger
echo   Converte a IA do APK em Pesos Neurais na GPU
echo =============================================================
python scripts\run_training_dagger.py
pause
