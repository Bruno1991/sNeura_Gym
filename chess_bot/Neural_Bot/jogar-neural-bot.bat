@echo off
chcp 65001 > nul
title Partida Contra Chess Neural Bot (ResNet)
cls
echo =================================================================
echo   PARTIDA CONTRA CHESS NEURAL BOT (RESNET POLICY-VALUE)
echo =================================================================
echo.
python "%~dp0neural_bot.py" --play
pause
