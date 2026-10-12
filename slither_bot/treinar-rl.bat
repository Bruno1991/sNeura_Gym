@echo off
title Slither AI - Treinamento por Reforço (PPO)
chcp 65001 >nul
cd /d "%~dp0"
python scripts\run_training_ppo.py
pause
