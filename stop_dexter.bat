@echo off
echo Stopping Dexter...

:: Kill the desktop app (pythonw.exe running desktop.main)
taskkill /f /fi "IMAGENAME eq pythonw.exe" /fi "WINDOWTITLE eq Dexter*" >nul 2>&1

:: Kill the uvicorn backend
taskkill /f /fi "IMAGENAME eq pythonw.exe" >nul 2>&1
taskkill /f /fi "IMAGENAME eq python.exe" /fi "WINDOWTITLE eq Dexter Backend*" >nul 2>&1

echo Dexter stopped.
