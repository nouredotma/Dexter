@echo off
cd /d "%~dp0"
echo Dexter is starting... check system tray.
docker-compose up -d
timeout /t 5 /nobreak >nul
start "" pyw -3 desktop/main.py
