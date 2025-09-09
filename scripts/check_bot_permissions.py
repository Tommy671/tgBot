#!/usr/bin/env python3
"""
Скрипт для проверки прав бота в каналах
Использование: python scripts/check_bot_permissions.py
"""

import asyncio
import httpx
from app.core.config import settings

async def check_bot_permissions():
    """Проверка прав бота в каналах"""
    
    # Создаем клиент для Telegram API
    async with httpx.AsyncClient() as client:
        base_url = f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}"
        
        print("🤖 Проверка прав бота в каналах...")
        print("=" * 50)
        
        # Проверяем бесплатный канал
        if settings.FREE_CHANNEL_ID.startswith('@'):
            print(f"📢 Бесплатный канал: {settings.FREE_CHANNEL_ID}")
            try:
                response = await client.get(f"{base_url}/getChatAdministrators", params={
                    "chat_id": settings.FREE_CHANNEL_ID
                })
                if response.status_code == 200:
                    data = response.json()
                    if data['ok']:
                        admins = data['result']
                        bot_found = False
                        for admin in admins:
                            if admin['user']['is_bot'] and admin['user']['id'] == int(settings.TELEGRAM_TOKEN.split(':')[0]):
                                bot_found = True
                                print(f"   ✅ Бот найден среди администраторов")
                                print(f"   🔑 Права: {admin.get('status', 'N/A')}")
                                break
                        if not bot_found:
                            print(f"   ❌ Бот не найден среди администраторов")
                    else:
                        print(f"   ❌ Ошибка: {data.get('description', 'Unknown error')}")
                else:
                    print(f"   ❌ HTTP ошибка: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Исключение: {e}")
        
        print()
        
        # Проверяем платный канал
        if settings.PAID_CHANNEL_ID.startswith('-'):
            print(f"💰 Платный канал: {settings.PAID_CHANNEL_ID}")
            try:
                response = await client.get(f"{base_url}/getChatAdministrators", params={
                    "chat_id": settings.PAID_CHANNEL_ID
                })
                if response.status_code == 200:
                    data = response.json()
                    if data['ok']:
                        admins = data['result']
                        bot_found = False
                        for admin in admins:
                            if admin['user']['is_bot'] and admin['user']['id'] == int(settings.TELEGRAM_TOKEN.split(':')[0]):
                                bot_found = True
                                print(f"   ✅ Бот найден среди администраторов")
                                print(f"   🔑 Права: {admin.get('status', 'N/A')}")
                                break
                        if not bot_found:
                            print(f"   ❌ Бот не найден среди администраторов")
                    else:
                        print(f"   ❌ Ошибка: {data.get('description', 'Unknown error')}")
                else:
                    print(f"   ❌ HTTP ошибка: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Исключение: {e}")
        
        print()
        print("=" * 50)
        print("💡 Для добавления бота в канал:")
        print("   1. Откройте канал в Telegram")
        print("   2. Нажмите на название канала")
        print("   3. Выберите 'Управление каналом'")
        print("   4. Выберите 'Администраторы'")
        print("   5. Нажмите 'Добавить администратора'")
        print("   6. Найдите вашего бота и добавьте его")

if __name__ == "__main__":
    asyncio.run(check_bot_permissions())
