#!/bin/bash
set -e

echo "🚀 Запуск Telegram CRM Bot в Docker..."

# Создаем директории если их нет
mkdir -p /app/data
mkdir -p /app/logs

# Проверяем переменные окружения
if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "❌ ОШИБКА: TELEGRAM_TOKEN не установлен"
    echo "📝 Установите переменную TELEGRAM_TOKEN в docker-compose.yml или .env файле"
    exit 1
fi

if [ -z "$SECRET_KEY" ]; then
    echo "❌ ОШИБКА: SECRET_KEY не установлен"
    echo "📝 Установите переменную SECRET_KEY в docker-compose.yml или .env файле"
    exit 1
fi

echo "✅ Переменные окружения проверены"

# Запускаем приложение
echo "🤖 Запуск приложения..."
exec python main.py
