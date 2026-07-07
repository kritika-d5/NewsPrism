@echo off
echo ========================================
echo   Starting NewsPrism Application
echo ========================================
echo.

echo Starting Backend Server...
start "NewsPrism Backend" cmd /k "cd backend && python run.py"

timeout /t 3 /nobreak >nul

echo Starting Frontend Server...
start "NewsPrism Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo   Both servers are starting...
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to close this window (servers will keep running)...
pause >nul

