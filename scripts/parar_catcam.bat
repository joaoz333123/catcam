@echo off
chcp 65001 > nul
title CatCam Monitor - Encerrando Serviços

echo ========================================================
echo        ENCERRANDO CATCAM MONITOR & TÚNEIS
echo ========================================================
echo.

echo [1/4] Finalizando aplicativo de bandeja e processos Python...
taskkill /F /FI "WINDOWTITLE eq CatCam*" > nul 2>&1
for /f "tokens=2" %%p in ('wmic process where "commandline like '%%catcam_tray.py%%'" get processid ^| findstr [0-9]') do taskkill /F /PID %%p > nul 2>&1

echo [2/4] Finalizando processos do go2rtc...
taskkill /F /IM go2rtc.exe /T > nul 2>&1

echo [3/4] Finalizando túneis remotos...
taskkill /F /IM cloudflared.exe /T > nul 2>&1
for /f "tokens=2" %%p in ('wmic process where "commandline like '%%nokey@localhost.run%%'" get processid ^| findstr [0-9]') do taskkill /F /PID %%p > nul 2>&1

echo [4/4] Liberando porta do servidor local (8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a > nul 2>&1

echo.
echo ========================================================
echo    CatCam e todos os servicos finalizados com sucesso!
echo ========================================================
timeout /t 2 > nul
exit
