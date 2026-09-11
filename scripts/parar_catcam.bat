@echo off
chcp 65001 > nul
title CatCam Monitor - Encerrando

echo ========================================================
echo        ENCERRANDO CATCAM MONITOR & TÚNEIS
echo ========================================================
echo.

echo Finalizando processos do go2rtc...
taskkill /F /IM go2rtc.exe /T > nul 2>&1

echo Finalizando túnel Cloudflare...
taskkill /F /IM cloudflared.exe /T > nul 2>&1

echo Finalizando servidor FastAPI/Uvicorn...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a > nul 2>&1

echo.
echo Todos os serviços do CatCam e túneis remotos foram finalizados com sucesso!
timeout /t 3
