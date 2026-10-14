@echo off
chcp 65001 > nul
title Treinamento de Destilacao Neural (balanced.bin -^> Pesos)
cls
echo =================================================================
echo   CHESS NEURAL BOT - TREINAMENTO DE DESTILAÇÃO DE ABERTURAS
echo =================================================================
echo.
echo Iniciando treinamento em GPU (RTX 3060)...
echo.
python "%~dp0scripts\train_distillation.py" --epochs 8 --batch-size 256
pause
