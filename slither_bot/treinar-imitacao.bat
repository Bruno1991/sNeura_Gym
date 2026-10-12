@echo off
title Slither AI - Treinamento por Imitação (Behavior Cloning)
chcp 65001 >nul
cd /d "%~dp0"
python scripts\run_training_imitation.py
pause
