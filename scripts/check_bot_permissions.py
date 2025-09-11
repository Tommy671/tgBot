import asyncio
import os
import sys
from typing import Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from app.core.config import Settings
except Exception:
    Settings = None

from telegram import Bot
from telegram.error import TelegramError


async def get_token() -> str:
    if Settings is not None:
        try:
            return Settings().TELEGRAM_TOKEN
        except Exception:
            return os.getenv("TELEGRAM_TOKEN", "")
    return os.getenv("TELEGRAM_TOKEN", "")


async def check_chat(bot: Bot, chat_identifier: str) -> None:
    try:
        chat = await bot.get_chat(chat_identifier)
        print(f"\nChat: {getattr(chat, 'title', None)} ({chat.id}) type={chat.type} username={getattr(chat, 'username', None)}")
        try:
            count = await bot.get_chat_member_count(chat.id)
        except TelegramError:
            count = None
        print(f"Members: {count}")

        is_admin = False
        me = await bot.get_me()
        try:
            admins = await bot.get_chat_administrators(chat.id)
            for adm in admins:
                if adm.user.id == me.id:
                    is_admin = True
                    print("Bot is admin: YES")
                    print(f"Rights: can_manage_chat={adm.can_manage_chat}, can_invite_users={adm.can_invite_users}, can_delete_messages={adm.can_delete_messages}")
                    break
        except TelegramError as e:
            print(f"Failed to get administrators: {e}")
        if not is_admin:
            print("Bot is admin: NO")
    except TelegramError as e:
        print(f"Error accessing chat '{chat_identifier}': {e}")


async def main() -> None:
    token = await get_token()
    if not token:
        print("TELEGRAM_TOKEN not found. Set it in .env or environment variables.")
        return
    bot = Bot(token=token)

    chat = os.getenv("CHECK_CHAT", "")
    if not chat:
        print("Set CHECK_CHAT env var (e.g., @username or -1001234567890)")
        return
    await check_chat(bot, chat)


if __name__ == "__main__":
    asyncio.run(main())

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
