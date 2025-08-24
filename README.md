# 🤖 Telegram Bot + FastAPI CRM

Современная система управления пользователями Telegram бота с веб-админкой на FastAPI.

## 🚀 Возможности

### Telegram Bot
- 📝 Интерактивная анкета регистрации
- ✅ Валидация данных (ФИО, телефон)
- 💳 Система подписок
- 🔒 Приватный чат для подписчиков
- ⚙️ Настройки профиля

### CRM Админка
- 📊 Дашборд со статистикой
- 👥 Управление пользователями
- 💳 Управление подписками
- 🔍 Поиск и фильтрация
- 📱 Адаптивный дизайн

## 🏗️ Архитектура

```
telegram-crm/
├── app/                    # Основное приложение
│   ├── core/              # Ядро приложения
│   │   ├── config.py      # Конфигурация
│   │   ├── database.py    # База данных
│   │   └── auth.py        # Аутентификация
│   ├── models/            # Модели данных
│   │   └── models.py      # SQLAlchemy модели
│   ├── schemas/           # Pydantic схемы
│   │   └── schemas.py     # Валидация данных
│   ├── bot/               # Telegram бот
│   │   └── bot.py         # Логика бота
│   └── admin/             # Админ панель
│       └── app.py         # FastAPI приложение
├── static/                # Статические файлы
├── templates/             # HTML шаблоны
├── scripts/               # Скрипты
├── data/                  # Данные (для Docker)
├── main.py               # Точка входа
├── requirements.txt      # Зависимости
├── Dockerfile           # Docker образ
├── docker-compose.yml   # Docker Compose
└── README.md            # Документация
```

## 🛠️ Технологии

- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **Bot**: python-telegram-bot
- **Database**: SQLite (можно PostgreSQL)
- **Auth**: JWT, bcrypt
- **Frontend**: Bootstrap 5, JavaScript
- **Deployment**: Docker, Docker Compose

## 📦 Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd telegram-crm
```

### 2. Настройка окружения
```bash
# Копируем пример конфигурации
cp env.example .env

# Редактируем .env файл
nano .env
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Инициализация базы данных
```bash
python scripts/init_db.py
```

### 5. Запуск
```bash
python main.py
```

## 🐳 Docker

### Быстрый запуск с Docker Compose
```bash
# Клонирование и настройка
git clone <repository-url>
cd telegram-crm
cp env.example .env
# Отредактируйте .env файл

# Запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

### Ручная сборка Docker образа
```bash
# Сборка образа
docker build -t telegram-crm .

# Запуск контейнера
docker run -d \
  --name telegram-crm \
  -p 8001:8001 \
  --env-file .env \
  telegram-crm
```

## ⚙️ Конфигурация

### Переменные окружения (.env)

```env
# Telegram Bot Token (получить у @BotFather)
TELEGRAM_TOKEN=your_telegram_bot_token_here

# Секретный ключ для JWT
SECRET_KEY=your_secret_key_here_should_be_at_least_32_characters_long

# База данных
DATABASE_URL=sqlite:///./bot_database.db

# Настройки сервера
HOST=0.0.0.0
PORT=8001

# JWT настройки
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Настройки бота
PRIVATE_CHAT_LINK=https://t.me/private_chat_link
SUBSCRIPTION_PRICE=999
SUBSCRIPTION_DURATION_DAYS=30
```

## 🔑 Получение токена бота

1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям
4. Скопируйте полученный токен в `.env`

## 📱 Использование

### Telegram Bot
1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Заполните анкету
4. Используйте меню для навигации

### CRM Админка
- **URL**: http://localhost:8001
- **Логин**: admin
- **Пароль**: admin123

## 🔧 Разработка

### Структура проекта
- `app/core/` - Ядро приложения (конфиг, БД, аутентификация)
- `app/models/` - Модели данных SQLAlchemy
- `app/schemas/` - Pydantic схемы для валидации
- `app/bot/` - Логика Telegram бота
- `app/admin/` - FastAPI админ панель

### Добавление новых функций
1. Создайте модель в `app/models/models.py`
2. Добавьте схему в `app/schemas/schemas.py`
3. Обновите API в `app/admin/app.py`
4. Добавьте логику в `app/bot/bot.py`

## 🚀 Развертывание

### Production с PostgreSQL
```env
DATABASE_URL=postgresql://user:password@localhost/telegram_crm
```

### Nginx конфигурация
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📊 API Документация

После запуска доступна автоматическая документация:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

## 🔒 Безопасность

- JWT токены для аутентификации
- Хеширование паролей с bcrypt
- Валидация данных с Pydantic
- Защита от SQL инъекций с SQLAlchemy

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License

## 🆘 Поддержка

- 📧 Email: support@example.com
- 💬 Telegram: @support_bot
- 🐛 Issues: GitHub Issues

---

**Сделано с ❤️ для сообщества Telegram разработчиков** 