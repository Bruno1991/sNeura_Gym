@echo off
title Slither AI - Avaliacao de Desempenho no Terminal
chcp 65001 >nul
cd /d "%~dp0"
echo =============================================================
echo   Slither AI - Avaliação de Desempenho (Max Speed)
echo   Roda partidas completas sem interface gráfica
echo =============================================================
python scripts\run_eval_terminal.py
pause
