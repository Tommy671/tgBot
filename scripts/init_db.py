#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных
"""
import os
import sys
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import create_tables, SessionLocal
from app.core.auth import create_default_admin

def init_database():
    """Инициализация базы данных"""
    print("🗄️ Инициализация базы данных...")
    
    # Создаем все таблицы
    create_tables()
    print("✅ Таблицы созданы")
    
    # Создаем админа по умолчанию
    print("🔐 Создание админ пользователя...")
    db = SessionLocal()
    try:
        if create_default_admin(db):
            print("✅ Админ пользователь создан (admin/admin123)")
        else:
            print("⚠️ Админ пользователь уже существует")
    except Exception as e:
        print(f"❌ Ошибка создания админа: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    print("🎉 База данных готова к использованию!")

if __name__ == "__main__":
    # Загружаем переменные окружения
    load_dotenv('.env')
    
    # Инициализируем базу
    init_database()
