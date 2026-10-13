@chcp 65001 >nul
@echo off
title Slither AI - Avaliacao de Desempenho no Terminal
cd /d "%~dp0"
echo =============================================================
echo   Slither AI - Avaliacao de Desempenho (Max Speed)
echo   Roda partidas completas sem interface grafica
echo =============================================================
python scripts\run_eval_terminal.py
pause
