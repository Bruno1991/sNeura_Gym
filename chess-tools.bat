@echo off
title s_Neura_Gym: Canivete Suíço do Xadrez & GymArena
chcp 65001 >nul
cd /d "%~dp0\chess_bot"

python cli.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Processo encerrado com código %ERRORLEVEL%.
    pause
)
