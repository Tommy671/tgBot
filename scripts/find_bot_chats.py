import asyncio
import os
import sys
from typing import Dict, Set

# Ensure project root is in sys.path
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


async def main() -> None:
    # Load token
    token: str
    if Settings is not None:
        try:
            settings = Settings()
            token = settings.TELEGRAM_TOKEN
        except Exception:
            token = os.getenv("TELEGRAM_TOKEN", "")
    else:
        token = os.getenv("TELEGRAM_TOKEN", "")

    if not token:
        print("❌ TELEGRAM_TOKEN не найден. Укажите его в .env или переменных окружения.")
        return

    bot = Bot(token=token)

    found_chat_ids: Set[int] = set()
    chat_meta: Dict[int, dict] = {}

    # Try to fetch recent updates to discover chats the bot interacted with
    try:
        updates = await bot.get_updates(limit=100)
    except TelegramError as e:
        print(f"⚠️ Не удалось получить обновления (возможно, используется webhook): {e}")
        updates = []

    def collect_chat(chat) -> None:
        if not chat:
            return
        if chat.id in found_chat_ids:
            return
        found_chat_ids.add(chat.id)
        chat_meta[chat.id] = {"type": chat.type, "title": getattr(chat, "title", None), "username": getattr(chat, "username", None)}

    for u in updates:
        if u.message and u.message.chat:
            collect_chat(u.message.chat)
        if u.edited_message and u.edited_message.chat:
            collect_chat(u.edited_message.chat)
        if u.channel_post and u.channel_post.chat:
            collect_chat(u.channel_post.chat)
        if u.edited_channel_post and u.edited_channel_post.chat:
            collect_chat(u.edited_channel_post.chat)
        if u.my_chat_member and u.my_chat_member.chat:
            collect_chat(u.my_chat_member.chat)
        if u.chat_member and u.chat_member.chat:
            collect_chat(u.chat_member.chat)
        if u.chat_join_request and u.chat_join_request.chat:
            collect_chat(u.chat_join_request.chat)

    if not found_chat_ids:
        print("⚠️ Не найдено чатов через getUpdates.\nПодсказка: отправьте любое сообщение в нужных каналах/группах или удалите/добавьте бота, затем перезапустите скрипт. Либо используйте username в другом скрипте.")

    # Enrich info for each chat id
    print("\n👀 Обнаруженные чаты, где бот получал события:")
    print("=" * 50)
    for chat_id in sorted(found_chat_ids):
        try:
            chat = await bot.get_chat(chat_id)
            # member count
            member_count = None
            try:
                member_count = await bot.get_chat_member_count(chat_id)
            except TelegramError:
                pass

            # admin status
            is_admin = False
            admin_rights = None
            try:
                admins = await bot.get_chat_administrators(chat_id)
                for adm in admins:
                    if adm.user and adm.user.is_bot:
                        me = await bot.get_me()
                        if adm.user.id == me.id:
                            is_admin = True
                            admin_rights = adm.can_manage_chat
                            break
            except TelegramError:
                pass

            print(f"ID: {chat.id}\nТип: {chat.type}\nНазвание: {getattr(chat, 'title', None)}\nUsername: {getattr(chat, 'username', None)}\nУчастников: {member_count}\nБот админ: {'✅' if is_admin else '❌'}\n---")
        except TelegramError as e:
            meta = chat_meta.get(chat_id, {})
            print(f"ID: {chat_id} (тип: {meta.get('type')}, название: {meta.get('title')}) — ошибка получения данных: {e}")

    print("\n💡 Если нужные чаты не появились: \n- Напишите сообщение в этих каналах/группах или измените права бота, чтобы появилась запись в обновлениях.\n- Либо используйте скрипт check_bot_permissions.py, указав @username канала (для публичных). Приватные можно проверить после того, как бот добавлен и появились обновления.")


if __name__ == "__main__":
    asyncio.run(main())


