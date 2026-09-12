@echo off
chcp 65001 > nul
title CatCam AI Monitor - Iniciando...

cd /d "%~dp0\.."

echo ========================================================
echo        CATCAM AI MONITOR - INICIALIZAÇÃO
echo ========================================================
echo.
echo Iniciando aplicativo na bandeja do sistema (perto do relogio)...
echo.

start "" "%~dp0..\.venv\Scripts\pythonw.exe" "%~dp0..\catcam_tray.py"

timeout /t 2 > nul
exit
