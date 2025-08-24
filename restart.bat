@echo off
chcp 65001 >nul
title Перезапуск Telegram Bot + FastAPI CRM

echo.
echo ========================================
echo    Перезапуск Telegram Bot + FastAPI CRM
echo ========================================
echo.

echo 🛑 Останавливаю систему...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1

echo.
echo ⏳ Жду завершения процессов...
timeout /t 3 /nobreak >nul

echo.
echo 🚀 Запускаю систему заново...
start.bat
