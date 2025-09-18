#!/usr/bin/env python3
"""
Скрипт для добавления колонок offer_consent_given и offer_consent_date в таблицу users
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def add_offer_columns():
    """Добавление колонок для согласия на оферту"""
    
    # Создаем подключение к базе данных
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # Начинаем транзакцию
            trans = connection.begin()
            
            try:
                print("🔧 Начинаем добавление колонок для согласия на оферту...")
                
                # Проверяем, существуют ли уже колонки
                result = connection.execute(text("PRAGMA table_info(users)"))
                columns = [row[1] for row in result.fetchall()]
                
                if 'offer_consent_given' not in columns:
                    # Добавляем колонку offer_consent_given
                    connection.execute(text("ALTER TABLE users ADD COLUMN offer_consent_given BOOLEAN DEFAULT 0"))
                    print("✅ Добавлена колонка offer_consent_given")
                else:
                    print("ℹ️  Колонка offer_consent_given уже существует")
                
                if 'offer_consent_date' not in columns:
                    # Добавляем колонку offer_consent_date
                    connection.execute(text("ALTER TABLE users ADD COLUMN offer_consent_date DATETIME"))
                    print("✅ Добавлена колонка offer_consent_date")
                else:
                    print("ℹ️  Колонка offer_consent_date уже существует")
                
                # Подтверждаем транзакцию
                trans.commit()
                print("🎉 Колонки успешно добавлены!")
                
            except Exception as e:
                # Откатываем транзакцию в случае ошибки
                trans.rollback()
                print(f"❌ Ошибка при добавлении колонок: {e}")
                raise
                
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔧 Добавление колонок для согласия на оферту в таблицу users")
    print("   - offer_consent_given (BOOLEAN DEFAULT 0)")
    print("   - offer_consent_date (DATETIME)")
    print()
    
    if add_offer_columns():
        print("\n✅ Миграция завершена успешно!")
    else:
        print("\n❌ Миграция не удалась!")
