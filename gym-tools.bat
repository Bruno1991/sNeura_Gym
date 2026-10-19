@echo off
title s_Neura_Gym: Hub Central de Ambientes e Bots
chcp 65001 >nul
cd /d "%~dp0"

REM Roteamento direto por argumento
if /i "%~1"=="chess" (
    shift
    cd /d "%~dp0chess_bot"
    call "%~dp0chess_bot\tools.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)

if /i "%~1"=="slither" (
    shift
    cd /d "%~dp0slither_bot"
    call "%~dp0slither_bot\tools.bat" %1 %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)

if /i "%~1"=="bedrock" (
    shift
    cd /d "%~dp0bedrock_bot\Scripted_Bot"
    npm test
    exit /b %ERRORLEVEL%
)

:MENU
cls
echo ======================================================================
echo           ♛ S_NEURA_GYM: ECOSSISTEMA DE BOTS ^& GYM HUB ♛
echo ======================================================================
echo  [1] Xadrez ^& GymArena (chess_bot - 217 Bots, MCTS, Baterias, Arena)
echo  [2] Slither.io (slither_bot - Bot Neural, DAgger, PPO RL, Benchmark)
echo  [3] Minecraft Bedrock (bedrock_bot - Bot Scriptado, Protocolo BDS)
echo  [0] Sair
echo ======================================================================
set /p GYM_CHOICE="Escolha o ambiente de IA (0-3): "

if "%GYM_CHOICE%"=="1" (
    cd /d "%~dp0chess_bot"
    call "%~dp0chess_bot\tools.bat"
    goto MENU
)

if "%GYM_CHOICE%"=="2" (
    cd /d "%~dp0slither_bot"
    call "%~dp0slither_bot\tools.bat"
    goto MENU
)

if "%GYM_CHOICE%"=="3" (
    cd /d "%~dp0bedrock_bot\Scripted_Bot"
    echo.
    echo [*] Executando testes e inicializacao do Bedrock Bot...
    npm test
    pause
    goto MENU
)

if "%GYM_CHOICE%"=="0" (
    echo.
    echo Até logo!
    exit /b 0
)

echo.
echo [!] Opcao invalida.
timeout /t 2 >nul
goto MENU
