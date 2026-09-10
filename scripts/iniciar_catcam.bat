@echo off
chcp 65001 > nul
title CatCam Monitor - Inicialização

echo ========================================================
echo        CATCAM MONITOR - VISÃO COMPUTACIONAL LOCAL
echo ========================================================
echo.

cd /d "%~dp0\.."

echo [1/3] Verificando Gateway de Video (go2rtc)...
tasklist /FI "IMAGENAME eq go2rtc.exe" 2>NUL | find /I /N "go2rtc.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo       go2rtc ja esta em execucao.
) else (
    echo       Iniciando go2rtc em segundo plano...
    start /b "" "bin\go2rtc.exe" -config "config\go2rtc.yaml" > nul 2>&1
    timeout /t 2 /nobreak > nul
)

echo [2/3] Abrindo Dashboard no navegador (http://localhost:8000)...
start "" "http://localhost:8000"

echo [3/3] Iniciando Servidor FastAPI e Detector de IA (YOLO11n + OpenVINO)...
echo.
echo Pressione Ctrl+C para encerrar o monitoramento.
echo.
call .venv\Scripts\activate.bat
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

pause
