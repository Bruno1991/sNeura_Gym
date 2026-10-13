@echo off
title Slither AI - Benchmark de Performance
chcp 65001 >nul
cd /d "%~dp0"
python scripts\run_benchmark.py
pause
