@echo off
chcp 65001 > nul
title CatCam - Túnel de Acesso Remoto (Cloudflare)

echo ========================================================
echo        CATCAM - GERADOR DE LINK DE ACESSO REMOTO
echo ========================================================
echo.
echo Iniciando túnel seguro para http://localhost:8000...
echo Copie a URL HTTPS gerada abaixo para acessar no celular ou fora de casa!
echo.
echo ========================================================
echo.

cd /d "%~dp0\.."

bin\cloudflared.exe tunnel --url http://localhost:8000

pause
