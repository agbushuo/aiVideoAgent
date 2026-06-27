@echo off
chcp 65001 >nul
echo ========================================
echo   VideoAgent - Starting Services
echo ========================================
echo.

set PYTHON=C:\Users\Administrator\.conda\envs\ai-video\python.exe

echo [1/2] Backend: http://127.0.0.1:8501
start "VideoAgent Backend" %PYTHON% -c "from src.web.app import run; run()"

echo [2/2] Frontend: http://localhost:3000
timeout /t 3 /nobreak >nul
cd /d %~dp0frontend
start "VideoAgent Frontend" cmd /k "npm run dev"

echo.
echo ========================================
echo  Backend:  http://127.0.0.1:8501
echo  Frontend: http://localhost:3000
echo ========================================
echo.
pause
