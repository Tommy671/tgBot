#!/bin/bash

echo "🚀 Автоматическое развертывание Telegram CRM Bot"
echo "=================================================="

# Проверка наличия Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker и Docker Compose"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose"
    exit 1
fi

echo "✅ Docker и Docker Compose найдены"

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "📝 Создание .env файла из примера..."
    cp env.example .env
    echo "⚠️  ВНИМАНИЕ: Отредактируйте .env файл и добавьте ваш TELEGRAM_TOKEN и SECRET_KEY"
    echo "📝 Затем запустите этот скрипт снова"
    exit 1
fi

# Проверка переменных окружения
if grep -q "your_telegram_bot_token_here" .env; then
    echo "❌ ОШИБКА: TELEGRAM_TOKEN не настроен в .env файле"
    echo "📝 Отредактируйте .env файл и добавьте ваш токен бота"
    exit 1
fi

if grep -q "your_secret_key_here" .env; then
    echo "❌ ОШИБКА: SECRET_KEY не настроен в .env файле"
    echo "📝 Отредактируйте .env файл и добавьте секретный ключ"
    exit 1
fi

echo "✅ Переменные окружения настроены"

# Создание директорий
echo "📁 Создание директорий..."
mkdir -p data logs

# Остановка существующих контейнеров
echo "🛑 Остановка существующих контейнеров..."
docker-compose down

# Сборка образа
echo "🔨 Сборка Docker образа..."
docker-compose build --no-cache

# Запуск контейнеров
echo "🚀 Запуск контейнеров..."
docker-compose up -d

# Ожидание запуска
echo "⏳ Ожидание запуска сервисов..."
sleep 10

# Проверка статуса
echo "🔍 Проверка статуса..."
if docker-compose ps | grep -q "Up"; then
    echo "✅ Контейнеры запущены успешно!"
    
    # Проверка health check
    echo "🏥 Проверка health check..."
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        echo "✅ Health check пройден!"
        echo ""
        echo "🎉 РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО УСПЕШНО!"
        echo "=================================================="
        echo "🌐 Админ панель: http://localhost:8001"
        echo "📚 API документация: http://localhost:8001/docs"
        echo "🔍 Health check: http://localhost:8001/health"
        echo ""
        echo "👤 Логин админа: admin"
        echo "🔑 Пароль админа: admin123"
        echo ""
        echo "📊 Просмотр логов: docker-compose logs -f"
        echo "🛑 Остановка: docker-compose down"
    else
        echo "⚠️  Health check не пройден, но контейнеры запущены"
        echo "📊 Проверьте логи: docker-compose logs -f"
    fi
else
    echo "❌ Ошибка запуска контейнеров"
    echo "📊 Проверьте логи: docker-compose logs"
    exit 1
fi
