@echo off
chcp 65001 >nul
title Telegram Bot + FastAPI CRM

echo.
echo ========================================
echo    Telegram Bot + FastAPI CRM
echo ========================================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ОШИБКА: Python не найден!
    echo 📥 Скачайте и установите Python с https://python.org
    echo.
    pause
    exit /b 1
)

REM Проверяем наличие .env файла
if not exist ".env" (
    echo ⚠️  Файл .env не найден!
    echo 📝 Создаю .env на основе env.example...
    copy "env.example" ".env" >nul
    echo.
    echo 🔧 Отредактируйте файл .env и добавьте ваш токен бота
    echo 🔑 Получить токен: https://t.me/BotFather
    echo.
    pause
    exit /b 1
)

REM Проверяем виртуальное окружение
if not exist "venv" (
    echo 📦 Создаю виртуальное окружение...
    python -m venv venv
    echo.
)

REM Активируем виртуальное окружение
echo 🔄 Активация виртуального окружения...
call venv\Scripts\activate.bat

REM Устанавливаем зависимости
echo 📦 Проверяю зависимости...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo ❌ Ошибка установки зависимостей
    echo Попробуйте: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Инициализируем базу данных
echo 🗄️  Проверяю базу данных...
python scripts\init_db.py >nul 2>&1

echo.
echo 🚀 Запуск системы...
echo ========================================
echo.

REM Запускаем систему
python main.py

pause
