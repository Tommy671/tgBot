#!/usr/bin/env python3
"""
Скрипт для получения ID каналов Telegram
Использование: python scripts/get_channel_id.py
"""

import asyncio
import httpx
from app.core.config import settings

async def get_channel_info():
    """Получение информации о каналах"""
    
    # Создаем клиент для Telegram API
    async with httpx.AsyncClient() as client:
        base_url = f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}"
        
        print("🔍 Поиск информации о каналах...")
        print("=" * 50)
        
        # Проверяем бесплатный канал
        if settings.FREE_CHANNEL_ID.startswith('@'):
            print(f"📢 Бесплатный канал: {settings.FREE_CHANNEL_ID}")
            try:
                response = await client.get(f"{base_url}/getChat", params={
                    "chat_id": settings.FREE_CHANNEL_ID
                })
                if response.status_code == 200:
                    data = response.json()
                    if data['ok']:
                        chat = data['result']
                        print(f"   ✅ ID: {chat['id']}")
                        print(f"   📝 Название: {chat.get('title', 'N/A')}")
                        print(f"   👥 Тип: {chat.get('type', 'N/A')}")
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
                response = await client.get(f"{base_url}/getChat", params={
                    "chat_id": settings.PAID_CHANNEL_ID
                })
                if response.status_code == 200:
                    data = response.json()
                    if data['ok']:
                        chat = data['result']
                        print(f"   ✅ ID: {chat['id']}")
                        print(f"   📝 Название: {chat.get('title', 'N/A')}")
                        print(f"   👥 Тип: {chat.get('type', 'N/A')}")
                    else:
                        print(f"   ❌ Ошибка: {data.get('description', 'Unknown error')}")
                else:
                    print(f"   ❌ HTTP ошибка: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Исключение: {e}")
        
        print()
        print("=" * 50)
        print("💡 Для получения ID канала:")
        print("   1. Добавьте бота в канал как администратора")
        print("   2. Отправьте любое сообщение в канал")
        print("   3. Получите updates через getUpdates")
        print("   4. Найдите chat.id в ответе")

if __name__ == "__main__":
    asyncio.run(get_channel_info())
