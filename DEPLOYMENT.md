# 🚀 Инструкции по развертыванию Telegram CRM Bot

## 📋 Требования

- Docker и Docker Compose
- Git
- Доступ к интернету
- Telegram Bot Token

## 🔧 Подготовка к развертыванию

### 1. Клонирование репозитория
```bash
git clone <your-repo-url>
cd tgBot
```

### 2. Создание .env файла
Создайте файл `.env` в корневой директории:
```bash
# Telegram Bot
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Безопасность
SECRET_KEY=your_secret_key_here

# База данных
DATABASE_URL=sqlite:///./data/bot_database.db

# Сервер
HOST=0.0.0.0
PORT=8001

# JWT
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Логирование
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### 3. Создание директорий
```bash
mkdir -p data logs
```

## 🐳 Запуск с Docker

### Сборка и запуск
```bash
# Сборка образа
docker-compose build

# Запуск в фоновом режиме
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

### Остановка
```bash
docker-compose down
```

## 🔍 Проверка работы

### 1. Проверка контейнера
```bash
docker-compose ps
```

### 2. Проверка health check
```bash
curl http://localhost:8001/health
```

### 3. Доступ к админ панели
- URL: http://your-server-ip:8001
- Логин: admin
- Пароль: admin123

## 📊 Мониторинг

### Логи приложения
```bash
# Все логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f telegram-crm
```

### Статистика контейнера
```bash
docker stats telegram-crm-bot
```

## 🔧 Обновление

### Обновление кода
```bash
# Остановка
docker-compose down

# Получение обновлений
git pull

# Пересборка и запуск
docker-compose up -d --build
```

## 🛠️ Устранение неполадок

### Проблема: Контейнер не запускается
```bash
# Проверка логов
docker-compose logs

# Проверка переменных окружения
docker-compose config
```

### Проблема: Не работает Telegram бот
1. Проверьте правильность TELEGRAM_TOKEN
2. Убедитесь, что бот не заблокирован
3. Проверьте логи: `docker-compose logs -f`

### Проблема: Не работает админ панель
1. Проверьте доступность порта 8001
2. Проверьте firewall на сервере
3. Проверьте логи приложения

## 🔒 Безопасность

### Рекомендации для продакшена
1. Измените пароль админа по умолчанию
2. Используйте HTTPS (настройте reverse proxy)
3. Ограничьте доступ к порту 8001
4. Регулярно обновляйте зависимости

### Настройка reverse proxy (nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📝 Полезные команды

```bash
# Перезапуск сервиса
docker-compose restart telegram-crm

# Просмотр использования ресурсов
docker stats

# Очистка неиспользуемых образов
docker system prune -a

# Резервное копирование базы данных
docker cp telegram-crm-bot:/app/data/bot_database.db ./backup/
```
