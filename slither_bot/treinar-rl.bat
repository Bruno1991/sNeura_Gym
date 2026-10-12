@chcp 65001 >nul
@echo off
title Slither AI - Treinamento por Reforco (PPO)
cd /d "%~dp0"
python scripts\run_training_ppo.py
pause
