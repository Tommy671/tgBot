#!/usr/bin/env python3
"""
Скрипт для очистки базы данных - обнуление всех регистраций пользователей
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def cleanup_database():
    """Очистка базы данных от всех пользовательских данных"""
    
    # Создаем подключение к базе данных
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # Начинаем транзакцию
            trans = connection.begin()
            
            try:
                print("🧹 Начинаем очистку базы данных...")
                
                # Удаляем все подписки
                result = connection.execute(text("DELETE FROM subscriptions"))
                print(f"✅ Удалено подписок: {result.rowcount}")
                
                # Удаляем все платежи
                result = connection.execute(text("DELETE FROM payments"))
                print(f"✅ Удалено платежей: {result.rowcount}")
                
                # Удаляем всех пользователей
                result = connection.execute(text("DELETE FROM users"))
                print(f"✅ Удалено пользователей: {result.rowcount}")
                
                # Сбрасываем автоинкремент для таблиц
                connection.execute(text("DELETE FROM sqlite_sequence WHERE name='users'"))
                connection.execute(text("DELETE FROM sqlite_sequence WHERE name='subscriptions'"))
                connection.execute(text("DELETE FROM sqlite_sequence WHERE name='payments'"))
                print("✅ Сброшены счетчики автоинкремента")
                
                # Подтверждаем транзакцию
                trans.commit()
                print("🎉 База данных успешно очищена!")
                
            except Exception as e:
                # Откатываем транзакцию в случае ошибки
                trans.rollback()
                print(f"❌ Ошибка при очистке базы данных: {e}")
                raise
                
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("⚠️  ВНИМАНИЕ: Этот скрипт удалит ВСЕ данные пользователей!")
    print("   - Всех пользователей")
    print("   - Все подписки")
    print("   - Все платежи")
    print()
    
    confirm = input("Вы уверены, что хотите продолжить? (yes/no): ").lower().strip()
    
    if confirm in ['yes', 'y', 'да', 'д']:
        if cleanup_database():
            print("\n✅ Очистка завершена успешно!")
        else:
            print("\n❌ Очистка не удалась!")
    else:
        print("❌ Очистка отменена.")
