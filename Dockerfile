FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 appuser

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Делаем entrypoint скрипт исполняемым
RUN chmod +x docker-entrypoint.sh

# Создаем директории для данных
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app

# Переключаемся на пользователя
USER appuser

# Открываем порт
EXPOSE 8001

# Entrypoint и команда запуска
ENTRYPOINT ["./docker-entrypoint.sh"]
