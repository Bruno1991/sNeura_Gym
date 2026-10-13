@echo off
title Slither AI - Jogar em Servidor com Bot Neural
chcp 65001 >nul
cd /d "%~dp0"
echo =======================================================
echo    Slither AI - Conectar ao Servidor
echo =======================================================
echo.
set /p SERVER_IP="Digite o IP do servidor (ou Enter para 127.0.0.1): "
if "%SERVER_IP%"=="" set SERVER_IP=127.0.0.1
set /p SERVER_PORT="Digite a porta (ou Enter para 444): "
if "%SERVER_PORT%"=="" set SERVER_PORT=444
echo.
python scripts\run_online_bot.py --host %SERVER_IP% --port %SERVER_PORT%
pause
