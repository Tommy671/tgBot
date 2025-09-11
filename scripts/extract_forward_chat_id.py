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

from telegram import Bot, Update
from telegram.error import TelegramError


async def get_token() -> str:
    if Settings is not None:
        try:
            return Settings().TELEGRAM_TOKEN
        except Exception:
            return os.getenv("TELEGRAM_TOKEN", "")
    return os.getenv("TELEGRAM_TOKEN", "")


async def main() -> None:
    token = await get_token()
    if not token:
        print("TELEGRAM_TOKEN not found. Set it in .env or environment variables.")
        return
    bot = Bot(token=token)

    try:
        updates = await bot.get_updates(limit=100)
    except TelegramError as e:
        print(f"Failed to get updates (webhook or no updates?): {e}")
        return

    found = False
    for u in updates:
        msg = u.message or u.edited_message
        if not msg:
            continue
        fwd_chat = getattr(msg, "forward_from_chat", None)
        if fwd_chat:
            print("Found forwarded channel/group:")
            print(f"ID: {fwd_chat.id}")
            print(f"Type: {fwd_chat.type}")
            print(f"Title: {getattr(fwd_chat, 'title', None)}")
            print(f"Username: {getattr(fwd_chat, 'username', None)}")
            found = True
    if not found:
        print("No forwarded messages with forward_from_chat found in recent updates. Forward any post from the paid channel to the bot and rerun.")


if __name__ == "__main__":
    asyncio.run(main())


