#!/usr/bin/env python3
"""
Скрипт для автоматического резервного копирования базы данных в CSV
Запускается по расписанию (cron) в 00:30 каждый день
"""

import sys
import os
import csv
from datetime import datetime
from pathlib import Path
from io import StringIO
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def backup_database():
    """Создание резервной копии базы данных в CSV формате"""
    
    # Создаем подключение к базе данных
    engine = create_engine(settings.DATABASE_URL)
    
    # Путь к файлу резервной копии
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"database_backup_{timestamp}.csv"
    
    try:
        with engine.connect() as connection:
            print(f"🔄 Начинаем резервное копирование базы данных...")
            
            # Получаем все таблицы
            tables_result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in tables_result.fetchall()]
            
            if not tables:
                print("⚠️  База данных пуста - нет таблиц для резервного копирования")
                return False
            
            print(f"📊 Найдено таблиц: {len(tables)}")
            
            # Создаем словарь для хранения данных всех таблиц
            all_data = {}
            
            for table in tables:
                try:
                    # Получаем данные из таблицы
                    query = f"SELECT * FROM {table}"
                    result = connection.execute(text(query))
                    rows = result.fetchall()
                    columns = result.keys()
                    
                    if rows:
                        all_data[table] = {
                            'columns': list(columns),
                            'rows': [list(row) for row in rows]
                        }
                        print(f"✅ Таблица '{table}': {len(rows)} записей")
                    else:
                        print(f"ℹ️  Таблица '{table}': пуста")
                        
                except Exception as e:
                    print(f"❌ Ошибка при чтении таблицы '{table}': {e}")
                    continue
            
            if not all_data:
                print("⚠️  Все таблицы пусты - резервная копия не создана")
                return False
            
            # Сохраняем данные в CSV файл
            with open(backup_file, 'w', encoding='utf-8', newline='') as f:
                f.write(f"# Резервная копия базы данных от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Всего таблиц: {len(all_data)}\n\n")
                
                for table_name, data in all_data.items():
                    f.write(f"# === ТАБЛИЦА: {table_name} ===\n")
                    f.write(f"# Записей: {len(data['rows'])}\n")
                    
                    # Записываем CSV данные
                    writer = csv.writer(f)
                    writer.writerow(data['columns'])  # Заголовки
                    writer.writerows(data['rows'])    # Данные
                    f.write("\n\n")
            
            print(f"💾 Резервная копия сохранена: {backup_file}")
            print(f"📈 Всего таблиц с данными: {len(all_data)}")
            
            # Удаляем старые резервные копии (оставляем только последние 7 дней)
            cleanup_old_backups(backup_dir)
            
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при создании резервной копии: {e}")
        return False

def cleanup_old_backups(backup_dir, days_to_keep=7):
    """Удаление старых резервных копий (старше указанного количества дней)"""
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        for backup_file in backup_dir.glob("database_backup_*.csv"):
            try:
                # Извлекаем дату из имени файла
                file_timestamp = backup_file.stem.replace("database_backup_", "")
                file_date = datetime.strptime(file_timestamp, "%Y%m%d_%H%M%S")
                
                if file_date < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    print(f"🗑️  Удален старый файл: {backup_file.name}")
                    
            except Exception as e:
                print(f"⚠️  Не удалось обработать файл {backup_file.name}: {e}")
                continue
        
        if deleted_count > 0:
            print(f"🧹 Удалено старых резервных копий: {deleted_count}")
        else:
            print("ℹ️  Старые резервные копии не найдены")
            
    except Exception as e:
        print(f"⚠️  Ошибка при очистке старых резервных копий: {e}")

def restore_from_backup(backup_file_path):
    """Восстановление базы данных из резервной копии CSV"""
    
    if not os.path.exists(backup_file_path):
        print(f"❌ Файл резервной копии не найден: {backup_file_path}")
        return False
    
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            print(f"🔄 Начинаем восстановление из резервной копии: {backup_file_path}")
            
            # Читаем файл резервной копии
            with open(backup_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Парсим содержимое файла
            sections = content.split('# === ТАБЛИЦА:')
            
            if len(sections) < 2:
                print("❌ Неверный формат файла резервной копии")
                return False
            
            # Пропускаем заголовок
            for section in sections[1:]:
                lines = section.strip().split('\n')
                if not lines:
                    continue
                
                # Извлекаем название таблицы
                table_name = lines[0].split(' ===')[0].strip()
                
                # Находим начало данных CSV
                csv_start = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.startswith('#'):
                        csv_start = i
                        break
                
                if csv_start == 0:
                    print(f"⚠️  Нет данных для таблицы {table_name}")
                    continue
                
                # Читаем CSV данные
                csv_data = '\n'.join(lines[csv_start:])
                
                try:
                    # Парсим CSV данные
                    csv_reader = csv.reader(StringIO(csv_data))
                    rows = list(csv_reader)
                    
                    if not rows:
                        print(f"ℹ️  Таблица {table_name} пуста")
                        continue
                    
                    # Первая строка - заголовки
                    columns = rows[0]
                    data_rows = rows[1:]
                    
                    if not data_rows:
                        print(f"ℹ️  Таблица {table_name} пуста")
                        continue
                    
                    # Очищаем таблицу перед восстановлением
                    connection.execute(text(f"DELETE FROM {table_name}"))
                    
                    # Вставляем данные
                    placeholders = ', '.join(['?' for _ in columns])
                    insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                    
                    for row in data_rows:
                        connection.execute(text(insert_query), row)
                    
                    print(f"✅ Восстановлена таблица {table_name}: {len(data_rows)} записей")
                    
                except Exception as e:
                    print(f"❌ Ошибка при восстановлении таблицы {table_name}: {e}")
                    continue
            
            connection.commit()
            print("🎉 Восстановление завершено успешно!")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при восстановлении: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Резервное копирование базы данных')
    parser.add_argument('--restore', help='Путь к файлу резервной копии для восстановления')
    parser.add_argument('--backup', action='store_true', help='Создать резервную копию')
    
    args = parser.parse_args()
    
    if args.restore:
        print("🔄 Режим восстановления")
        if restore_from_backup(args.restore):
            print("✅ Восстановление завершено успешно!")
        else:
            print("❌ Восстановление не удалось!")
    elif args.backup:
        print("💾 Режим резервного копирования")
        if backup_database():
            print("✅ Резервное копирование завершено успешно!")
        else:
            print("❌ Резервное копирование не удалось!")
    else:
        # По умолчанию создаем резервную копию
        print("💾 Создание резервной копии базы данных")
        if backup_database():
            print("✅ Резервное копирование завершено успешно!")
        else:
            print("❌ Резервное копирование не удалось!")
