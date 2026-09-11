@echo off
chcp 65001 > nul
title CatCam - Modo Online & Acesso Remoto

echo ========================================================
echo        CATCAM MONITOR - INICIALIZAÇÃO MODO ONLINE
echo ========================================================
echo.

cd /d "%~dp0\.."

echo [1/3] Iniciando Gateway de Video (go2rtc)...
tasklist /FI "IMAGENAME eq go2rtc.exe" 2>NUL | find /I /N "go2rtc.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo       go2rtc ja esta em execucao.
) else (
    start /b "" "bin\go2rtc.exe" -config "config\go2rtc.yaml" > nul 2>&1
    timeout /t 2 /nobreak > nul
)

echo [2/3] Iniciando Servidor FastAPI & Detector OpenVINO...
start /b "" .venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > nul 2>&1
timeout /t 3 /nobreak > nul

echo [3/3] Estabelecendo Tunel HTTPS Seguro para Acesso Externo...
echo.
echo ========================================================
echo   COPIE O LINK HTTPS ABAIXO PARA ACESSAR NO CELULAR:
echo ========================================================
echo.

ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run

pause
