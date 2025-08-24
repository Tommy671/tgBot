#!/usr/bin/env python3
"""
Скрипт для проверки состояния базы данных
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, create_tables
from app.models.models import User, Subscription, AdminUser
from app.core.auth import create_default_admin
from datetime import datetime, timezone

def check_database():
    """Проверка состояния базы данных"""
    print("🔍 Проверка базы данных...")
    
    try:
        # Создаем таблицы если их нет
        create_tables()
        print("✅ Таблицы созданы/проверены")
        
        # Подключаемся к базе
        db = SessionLocal()
        
        try:
            # Проверяем количество пользователей
            users_count = db.query(User).count()
            print(f"👥 Пользователей в базе: {users_count}")
            
            # Проверяем количество подписок
            subscriptions_count = db.query(Subscription).count()
            print(f"💳 Подписок в базе: {subscriptions_count}")
            
            # Проверяем количество админов
            admins_count = db.query(AdminUser).count()
            print(f"👨‍💼 Админов в базе: {admins_count}")
            
            # Показываем последних пользователей
            if users_count > 0:
                print("\n📋 Последние пользователи:")
                recent_users = db.query(User).order_by(User.registration_date.desc()).limit(5).all()
                for user in recent_users:
                    print(f"  - {user.full_name} (@{user.username}) - {user.registration_date.strftime('%d.%m.%Y')}")
            
            # Проверяем админа по умолчанию
            if admins_count == 0:
                print("\n⚠️  Админов нет! Создаю админа по умолчанию...")
                if create_default_admin(db):
                    print("✅ Админ создан: admin / admin123")
                else:
                    print("❌ Ошибка создания админа")
            else:
                print("\n✅ Админы есть в базе")
                
        finally:
            db.close()
            
        print("\n🎉 Проверка завершена!")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке базы данных: {e}")
        return False
    
    return True

if __name__ == "__main__":
    check_database()
