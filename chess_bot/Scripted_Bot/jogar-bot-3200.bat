@echo off
chcp 65001 > nul
title Chess 3200 Elo Bot - Maximum (Komodo 25)
cls
echo =================================================================
echo   CHESS BOT 3200 ELO - MAXIMUM (KOMODO 25)
echo =================================================================
echo.
echo Iniciando motor e carregando livro de abertura Polyglot...
echo.
python "%~dp0bot_3200.py" --play
pause
