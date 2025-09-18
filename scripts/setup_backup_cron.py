#!/usr/bin/env python3
"""
Скрипт для настройки автоматического резервного копирования по расписанию
"""

import os
import subprocess
import sys
from pathlib import Path

def setup_cron_job():
    """Настройка cron задачи для автоматического резервного копирования"""
    
    # Получаем абсолютный путь к скрипту резервного копирования
    script_dir = Path(__file__).parent
    backup_script = script_dir / "backup_database.py"
    project_root = script_dir.parent
    
    if not backup_script.exists():
        print(f"❌ Скрипт резервного копирования не найден: {backup_script}")
        return False
    
    # Команда для cron (запуск в 00:30 каждый день)
    cron_command = f"30 0 * * * cd {project_root} && python {backup_script} --backup >> logs/backup.log 2>&1"
    
    try:
        # Проверяем, существует ли уже такая задача
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        
        if result.returncode == 0:
            existing_crontab = result.stdout
            if "backup_database.py" in existing_crontab:
                print("ℹ️  Задача резервного копирования уже настроена в cron")
                return True
        else:
            existing_crontab = ""
        
        # Добавляем новую задачу
        new_crontab = existing_crontab.rstrip() + "\n" + cron_command + "\n"
        
        # Устанавливаем новый crontab
        process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
        process.communicate(input=new_crontab)
        
        if process.returncode == 0:
            print("✅ Задача резервного копирования успешно добавлена в cron")
            print(f"📅 Расписание: каждый день в 00:30")
            print(f"📁 Логи: {project_root}/logs/backup.log")
            return True
        else:
            print("❌ Ошибка при добавлении задачи в cron")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при настройке cron: {e}")
        return False

def remove_cron_job():
    """Удаление задачи резервного копирования из cron"""
    
    try:
        # Получаем текущий crontab
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("ℹ️  Нет настроенных cron задач")
            return True
        
        existing_crontab = result.stdout
        
        # Удаляем строки с backup_database.py
        lines = existing_crontab.split('\n')
        filtered_lines = [line for line in lines if "backup_database.py" not in line]
        
        if len(filtered_lines) == len(lines):
            print("ℹ️  Задача резервного копирования не найдена в cron")
            return True
        
        # Устанавливаем обновленный crontab
        new_crontab = '\n'.join(filtered_lines)
        
        process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
        process.communicate(input=new_crontab)
        
        if process.returncode == 0:
            print("✅ Задача резервного копирования удалена из cron")
            return True
        else:
            print("❌ Ошибка при удалении задачи из cron")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при удалении cron задачи: {e}")
        return False

def show_cron_status():
    """Показать статус cron задач"""
    
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("ℹ️  Нет настроенных cron задач")
            return
        
        crontab_content = result.stdout
        
        if "backup_database.py" in crontab_content:
            print("✅ Задача резервного копирования настроена")
            
            # Находим строку с задачей
            for line in crontab_content.split('\n'):
                if "backup_database.py" in line:
                    print(f"📅 Расписание: {line}")
                    break
        else:
            print("❌ Задача резервного копирования не настроена")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке cron: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Управление автоматическим резервным копированием')
    parser.add_argument('--setup', action='store_true', help='Настроить автоматическое резервное копирование')
    parser.add_argument('--remove', action='store_true', help='Удалить автоматическое резервное копирование')
    parser.add_argument('--status', action='store_true', help='Показать статус резервного копирования')
    
    args = parser.parse_args()
    
    if args.setup:
        print("🔧 Настройка автоматического резервного копирования...")
        if setup_cron_job():
            print("✅ Настройка завершена успешно!")
        else:
            print("❌ Настройка не удалась!")
    elif args.remove:
        print("🗑️  Удаление автоматического резервного копирования...")
        if remove_cron_job():
            print("✅ Удаление завершено успешно!")
        else:
            print("❌ Удаление не удалось!")
    elif args.status:
        print("📊 Статус автоматического резервного копирования:")
        show_cron_status()
    else:
        print("Использование:")
        print("  python setup_backup_cron.py --setup    # Настроить автоматическое резервное копирование")
        print("  python setup_backup_cron.py --remove   # Удалить автоматическое резервное копирование")
        print("  python setup_backup_cron.py --status   # Показать статус")
