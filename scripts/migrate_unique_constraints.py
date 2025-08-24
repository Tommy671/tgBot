"""
Миграция для изменения уникальных ограничений в базе данных
"""
import sqlite3
import os
from pathlib import Path

def migrate_unique_constraints():
    """Миграция уникальных ограничений"""
    db_path = Path("bot_database.db")
    
    if not db_path.exists():
        print("❌ База данных не найдена")
        return False
    
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 Начинаю миграцию уникальных ограничений...")
        
        # 1. Удаляем старые уникальные ограничения
        print("📝 Удаляю старые уникальные ограничения...")
        
        # Получаем информацию о таблице
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        
        # Находим индекс для telegram_id
        cursor.execute("PRAGMA index_list(users)")
        indexes = cursor.fetchall()
        
        for index in indexes:
            index_name = index[1]
            if 'telegram_id' in index_name and 'unique' in index_name.lower():
                print(f"🗑️ Удаляю индекс: {index_name}")
                cursor.execute(f"DROP INDEX {index_name}")
        
        # 2. Создаем новые уникальные ограничения
        print("📝 Создаю новые уникальные ограничения...")
        
        # Создаем уникальный индекс для username
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique 
            ON users(username) 
            WHERE username IS NOT NULL
        """)
        print("✅ Создан уникальный индекс для username")
        
        # Создаем уникальный индекс для contact_number
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_contact_number_unique 
            ON users(contact_number) 
            WHERE contact_number IS NOT NULL
        """)
        print("✅ Создан уникальный индекс для contact_number")
        
        # Создаем обычный индекс для telegram_id (не уникальный)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_telegram_id 
            ON users(telegram_id)
        """)
        print("✅ Создан обычный индекс для telegram_id")
        
        # Сохраняем изменения
        conn.commit()
        print("💾 Изменения сохранены")
        
        # Проверяем результат
        cursor.execute("PRAGMA index_list(users)")
        indexes = cursor.fetchall()
        print("\n📋 Текущие индексы таблицы users:")
        for index in indexes:
            print(f"  - {index[1]} ({'уникальный' if index[2] else 'обычный'})")
        
        conn.close()
        print("\n✅ Миграция завершена успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    migrate_unique_constraints()
