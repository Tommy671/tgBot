# 🚀 Настройка автоматического резервного копирования на сервере

## 📋 Быстрая настройка

### 1. Загрузить файлы на сервер

```bash
# Скопировать скрипты резервного копирования
scp scripts/backup_database.py user@server:/path/to/project/scripts/
scp scripts/setup_backup_cron.py user@server:/path/to/project/scripts/
```

### 2. Настроить автоматическое резервное копирование

```bash
# Подключиться к серверу
ssh user@server

# Перейти в директорию проекта
cd /path/to/project

# Создать директории
mkdir -p backups logs

# Настроить cron задачу
python scripts/setup_backup_cron.py --setup

# Проверить статус
python scripts/setup_backup_cron.py --status
```

### 3. Протестировать резервное копирование

```bash
# Создать тестовую резервную копию
python scripts/backup_database.py --backup

# Проверить созданный файл
ls -la backups/
```

## 🔧 Команды управления

```bash
# Создать резервную копию вручную
python scripts/backup_database.py --backup

# Восстановить из резервной копии
python scripts/backup_database.py --restore backups/database_backup_YYYYMMDD_HHMMSS.csv

# Проверить статус автоматического резервного копирования
python scripts/setup_backup_cron.py --status

# Удалить автоматическое резервное копирование
python scripts/setup_backup_cron.py --remove
```

## 📅 Расписание

- **Время запуска**: каждый день в 00:30
- **Хранение**: последние 7 дней
- **Формат файлов**: `database_backup_YYYYMMDD_HHMMSS.csv`
- **Логи**: `logs/backup.log`

## 🚨 В случае проблем

### Проблема: Ошибка "no such column: users.offer_consent_given"

```bash
# Выполнить миграцию базы данных
python scripts/add_offer_columns.py
```

### Проблема: Cron не работает

```bash
# Проверить права доступа
chmod +x scripts/backup_database.py
chmod +x scripts/setup_backup_cron.py

# Переустановить cron задачу
python scripts/setup_backup_cron.py --remove
python scripts/setup_backup_cron.py --setup
```

### Проблема: Недостаточно места

```bash
# Очистить старые резервные копии
rm backups/database_backup_*.csv

# Проверить свободное место
df -h
```

## 📊 Мониторинг

```bash
# Просмотр логов резервного копирования
tail -f logs/backup.log

# Проверка последних резервных копий
ls -lt backups/ | head -10

# Проверка размера резервных копий
du -sh backups/
```

## ✅ Проверка работоспособности

После настройки проверьте:

1. ✅ Cron задача настроена: `python scripts/setup_backup_cron.py --status`
2. ✅ Ручное резервное копирование работает: `python scripts/backup_database.py --backup`
3. ✅ Файл резервной копии создан: `ls -la backups/`
4. ✅ Логи записываются: `tail logs/backup.log`

## 🎯 Результат

После настройки у вас будет:

- 🔄 **Автоматическое резервное копирование** каждый день в 00:30
- 💾 **Резервные копии в CSV формате** - легко читать и восстанавливать
- 🧹 **Автоматическая очистка** старых резервных копий
- 📝 **Подробные логи** всех операций
- 🚨 **Защита от потери данных** при сбоях системы
