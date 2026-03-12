@echo off
title GMDS Space Hardware Assistant

echo Starting GMDS Space Hardware Assistant...

cd /d "%~dp0"

start "Backend" cmd /k "cd backend && python3 -m uvicorn main:app --reload"

timeout /t 2 /nobreak >nul

start "Frontend" cmd /k "cd frontend && npm run dev"

echo Both services are starting. Check the terminal windows for status.
