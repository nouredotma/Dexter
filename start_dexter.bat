@echo off
cd /d "%~dp0"
echo ============================================
echo   Dexter is starting...
echo ============================================
echo.

:: --- 1. Start Docker services ---
echo [1/3] Starting Docker services...
docker-compose up -d
if errorlevel 1 (
    echo ERROR: docker-compose failed. Is Docker Desktop running?
    pause
    exit /b 1
)

:: --- 2. Install desktop dependencies (if missing) ---
echo [2/3] Checking dependencies...
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m pip install -q -r desktop\requirements.txt 2>nul
) else (
    echo WARNING: .venv not found. Please create a virtual environment first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt -r desktop\requirements.txt
    pause
    exit /b 1
)

:: --- 3. Wait for backend to be healthy ---
echo [3/3] Waiting for backend to come online...
set ATTEMPTS=0
set MAX_ATTEMPTS=30

:healthcheck
set /a ATTEMPTS+=1
if %ATTEMPTS% gtr %MAX_ATTEMPTS% (
    echo WARNING: Backend did not respond after %MAX_ATTEMPTS% attempts.
    echo          Starting desktop app anyway. It will retry on its own.
    goto :launch
)

:: Try the health endpoint
.venv\Scripts\python.exe -c "import httpx; r=httpx.get('http://localhost:8000/health',timeout=2); exit(0 if r.status_code==200 else 1)" 2>nul
if errorlevel 1 (
    echo   Attempt %ATTEMPTS%/%MAX_ATTEMPTS% - backend not ready yet...
    timeout /t 2 /nobreak >nul
    goto :healthcheck
)
echo   Backend is online!

:: --- 4. Launch desktop app ---
:launch
echo.
echo Dexter is ready! Check your system tray.
echo   - Double-click the orange icon to open the Dashboard
echo   - Right-click for quick actions (Listen Now, Wake Word, etc.)
echo.
start "" .venv\Scripts\pythonw.exe -m desktop.main
