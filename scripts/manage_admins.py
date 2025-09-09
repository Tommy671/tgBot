#!/usr/bin/env python3
"""
Скрипт для управления администраторами
Использование: 
  python scripts/manage_admins.py list - показать всех админов
  python scripts/manage_admins.py add <username> <password> - добавить админа
  python scripts/manage_admins.py change <username> <new_password> - изменить пароль
  python scripts/manage_admins.py delete <username> - удалить админа
"""

import sys
import os
import getpass

# Добавляем корневую папку проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_session
from app.models.models import AdminUser

def list_admins():
    """Показать всех администраторов"""
    with get_db_session() as db:
        admins = db.query(AdminUser).all()
        
        if not admins:
            print("❌ Администраторы не найдены")
            return
        
        print("👥 Список администраторов:")
        print("=" * 50)
        for admin in admins:
            status = "✅ Активен" if admin.is_active else "❌ Заблокирован"
            print(f"ID: {admin.id}")
            print(f"Username: {admin.username}")
            print(f"Status: {status}")
            print("-" * 30)

def add_admin(username, password):
    """Добавить нового администратора"""
    with get_db_session() as db:
        # Проверяем, существует ли уже такой админ
        existing_admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if existing_admin:
            print(f"❌ Администратор с именем '{username}' уже существует")
            return
        
        # Создаем нового админа
        admin = AdminUser(
            username=username,
            hashed_password=AdminUser.get_password_hash(password),
            is_active=True
        )
        
        db.add(admin)
        db.commit()
        print(f"✅ Администратор '{username}' успешно создан")

def change_password(username, new_password):
    """Изменить пароль администратора"""
    with get_db_session() as db:
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if not admin:
            print(f"❌ Администратор с именем '{username}' не найден")
            return
        
        admin.hashed_password = AdminUser.get_password_hash(new_password)
        db.commit()
        print(f"✅ Пароль для '{username}' успешно изменен")

def delete_admin(username):
    """Удалить администратора"""
    with get_db_session() as db:
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if not admin:
            print(f"❌ Администратор с именем '{username}' не найден")
            return
        
        # Проверяем, что не удаляем последнего админа
        admin_count = db.query(AdminUser).count()
        if admin_count <= 1:
            print("❌ Нельзя удалить последнего администратора")
            return
        
        db.delete(admin)
        db.commit()
        print(f"✅ Администратор '{username}' успешно удален")

def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python scripts/manage_admins.py list")
        print("  python scripts/manage_admins.py add <username> <password>")
        print("  python scripts/manage_admins.py change <username> <new_password>")
        print("  python scripts/manage_admins.py delete <username>")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_admins()
    
    elif command == "add":
        if len(sys.argv) < 4:
            print("❌ Использование: python scripts/manage_admins.py add <username> <password>")
            return
        username = sys.argv[2]
        password = sys.argv[3]
        add_admin(username, password)
    
    elif command == "change":
        if len(sys.argv) < 4:
            print("❌ Использование: python scripts/manage_admins.py change <username> <new_password>")
            return
        username = sys.argv[2]
        new_password = sys.argv[3]
        change_password(username, new_password)
    
    elif command == "delete":
        if len(sys.argv) < 3:
            print("❌ Использование: python scripts/manage_admins.py delete <username>")
            return
        username = sys.argv[2]
        delete_admin(username)
    
    else:
        print(f"❌ Неизвестная команда: {command}")

if __name__ == "__main__":
    main()
