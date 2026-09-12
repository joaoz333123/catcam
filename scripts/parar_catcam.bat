@echo off
title CatCam Monitor - Encerrando Servicos

echo ========================================================
echo        ENCERRANDO CATCAM MONITOR E TUNEIS
echo ========================================================
echo.

echo [1/3] Finalizando processos do go2rtc...
taskkill /F /IM go2rtc.exe /T >nul 2>&1

echo [2/3] Finalizando tuneis remotos e processos do CatCam...
taskkill /F /IM cloudflared.exe /T >nul 2>&1
powershell -NoProfile -Command "Get-Process | Where-Object { $_.ProcessName -match 'go2rtc' -or ($_.ProcessName -match 'python' -and $_.MainWindowTitle -match 'CatCam') } | Stop-Process -Force -ErrorAction SilentlyContinue" >nul 2>&1

echo [3/3] Liberando porta do servidor local (8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

echo.
echo ========================================================
echo    CatCam e todos os servicos finalizados com sucesso!
echo ========================================================
ping 127.0.0.1 -n 2 >nul
exit
