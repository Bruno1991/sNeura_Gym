@echo off
title Slither AI - Arena do Espectador Web (Live 60 FPS)
chcp 65001 >nul
cd /d "%~dp0"
echo =============================================================
echo   Iniciando Servidor Espectador em http://localhost:8080
echo   Abra http://localhost:8080 no seu navegador para assistir!
echo =============================================================
python scripts\run_spectator.py
pause
