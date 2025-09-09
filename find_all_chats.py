#!/usr/bin/env python3
"""
Скрипт для поиска всех чатов и каналов, куда добавлен бот
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram import Bot

async def find_all_chats():
    """Поиск всех чатов и каналов"""
    print("🔍 ПОИСК ВСЕХ ЧАТОВ И КАНАЛОВ")
    print("=" * 50)
    
    try:
        token = os.getenv('TELEGRAM_TOKEN', '8301019500:AAHrP6XBi9l5cCRuQxCmRA3Ny-kFDhxO_NI')
        bot = Bot(token=token)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"🤖 Бот: {bot_info.first_name} (@{bot_info.username})")
        print(f"🆔 ID бота: {bot_info.id}")
        
        print(f"\n📋 Ищем все чаты и каналы, куда добавлен бот...")
        
        # Подход 1: Проверить известные ID каналов
        print(f"\n🔍 Подход 1: Проверка известных ID")
        
        # Список возможных ID для проверки
        possible_ids = []
        
        # Генерируем возможные ID (это не очень эффективно, но может помочь)
        base_id = 1000000000000  # Базовый ID для каналов
        
        # Проверяем несколько возможных ID
        for i in range(10):  # Проверяем первые 10 возможных ID
            test_id = f"-{base_id + i}"
            possible_ids.append(test_id)
        
        # Добавляем известные ID
        possible_ids.append("-1002776416062")
        possible_ids.append("-1002765866900")
        
        found_chats = []
        
        for chat_id in possible_ids:
            try:
                print(f"Проверяем ID: {chat_id}")
                chat_info = await bot.get_chat(chat_id)
                
                print(f"✅ Найден чат/канал:")
                print(f"   📺 Название: {chat_info.title}")
                print(f"   🆔 ID: {chat_info.id}")
                print(f"   📝 Тип: {chat_info.type}")
                
                if hasattr(chat_info, 'username') and chat_info.username:
                    print(f"   🔗 Username: @{chat_info.username}")
                
                # Получаем количество участников
                try:
                    member_count = await bot.get_chat_member_count(chat_id)
                    print(f"   👥 Участников: {member_count}")
                except Exception as e:
                    print(f"   👥 Участников: Не удалось получить")
                
                # Проверяем права бота
                try:
                    admins = await bot.get_chat_administrators(chat_id)
                    bot_is_admin = False
                    bot_permissions = {}
                    
                    for admin in admins:
                        if admin.user.id == bot_info.id:
                            bot_is_admin = True
                            bot_permissions = {
                                'can_restrict_members': admin.can_restrict_members,
                                'can_invite_users': admin.can_invite_users,
                                'can_delete_messages': admin.can_delete_messages,
                            }
                            break
                    
                    if bot_is_admin:
                        print(f"   ✅ Бот является администратором")
                        print(f"   🔧 Может удалять участников: {'✅' if bot_permissions.get('can_restrict_members') else '❌'}")
                    else:
                        print(f"   ❌ Бот НЕ является администратором")
                        
                except Exception as e:
                    print(f"   ⚠️ Не удалось проверить права: {e}")
                
                found_chats.append({
                    'id': chat_info.id,
                    'title': chat_info.title,
                    'type': chat_info.type,
                    'username': getattr(chat_info, 'username', None),
                    'member_count': member_count if 'member_count' in locals() else 0,
                    'bot_is_admin': bot_is_admin,
                    'can_remove': bot_permissions.get('can_restrict_members', False)
                })
                
                print()  # Пустая строка для разделения
                
            except Exception as e:
                # Игнорируем ошибки для несуществующих чатов
                pass
        
        # Подход 2: Попытка использовать getUpdates (если бот получает обновления)
        print(f"\n🔍 Подход 2: Проверка обновлений")
        try:
            updates = await bot.get_updates(limit=10)
            if updates:
                print(f"✅ Получено {len(updates)} обновлений")
                
                chat_ids = set()
                for update in updates:
                    if update.message and update.message.chat:
                        chat_ids.add(update.message.chat.id)
                    elif update.callback_query and update.callback_query.message:
                        chat_ids.add(update.callback_query.message.chat.id)
                
                print(f"📋 Найдено {len(chat_ids)} уникальных чатов в обновлениях:")
                for chat_id in chat_ids:
                    try:
                        chat_info = await bot.get_chat(chat_id)
                        print(f"   📺 {chat_info.title} (ID: {chat_id})")
                    except:
                        print(f"   ❓ Неизвестный чат (ID: {chat_id})")
            else:
                print("❌ Нет обновлений")
                
        except Exception as e:
            print(f"❌ Ошибка при получении обновлений: {e}")
        
        # Анализируем результаты
        print(f"\n📊 РЕЗУЛЬТАТЫ ПОИСКА:")
        print("=" * 50)
        
        if found_chats:
            print(f"✅ Найдено {len(found_chats)} чатов/каналов:")
            
            for i, chat in enumerate(found_chats, 1):
                print(f"\n{i}. 📺 {chat['title']}")
                print(f"   🆔 ID: {chat['id']}")
                print(f"   📝 Тип: {chat['type']}")
                if chat['username']:
                    print(f"   🔗 Username: @{chat['username']}")
                print(f"   👥 Участников: {chat['member_count']}")
                print(f"   🤖 Бот админ: {'✅' if chat['bot_is_admin'] else '❌'}")
                print(f"   🗑️ Может удалять: {'✅' if chat['can_remove'] else '❌'}")
            
            # Генерируем конфигурацию
            print(f"\n🔧 ВОЗМОЖНЫЕ КОНФИГУРАЦИИ:")
            print("=" * 50)
            
            if len(found_chats) >= 2:
                print("✅ Найдено 2+ чата/канала!")
                print("Выберите подходящие ID для FREE_CHANNEL_ID и PAID_CHANNEL_ID:")
                
                for i, chat in enumerate(found_chats, 1):
                    print(f"{i}. {chat['title']} (ID: {chat['id']})")
                
                print(f"\nПример конфигурации:")
                if len(found_chats) >= 2:
                    print(f"FREE_CHANNEL_ID={found_chats[0]['id']}")
                    print(f"PAID_CHANNEL_ID={found_chats[1]['id']}")
                    
            elif len(found_chats) == 1:
                print("⚠️ Найден только 1 чат/канал!")
                print("Используйте его для обеих целей:")
                print(f"FREE_CHANNEL_ID={found_chats[0]['id']}")
                print(f"PAID_CHANNEL_ID={found_chats[0]['id']}")
                
        else:
            print("❌ Чаты/каналы не найдены!")
            print("💡 Убедитесь, что бот добавлен в каналы")
        
        # Сохраняем отчет
        report_file = f"all_chats_report_{asyncio.get_event_loop().time():.0f}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("ОТЧЕТ О ВСЕХ ЧАТАХ И КАНАЛАХ\n")
            f.write("=" * 50 + "\n")
            f.write(f"Бот: {bot_info.first_name} (@{bot_info.username})\n\n")
            
            for i, chat in enumerate(found_chats, 1):
                f.write(f"{i}. {chat['title']}\n")
                f.write(f"   ID: {chat['id']}\n")
                f.write(f"   Тип: {chat['type']}\n")
                if chat['username']:
                    f.write(f"   Username: @{chat['username']}\n")
                f.write(f"   Участников: {chat['member_count']}\n")
                f.write(f"   Бот админ: {'Да' if chat['bot_is_admin'] else 'Нет'}\n")
                f.write(f"   Может удалять: {'Да' if chat['can_remove'] else 'Нет'}\n\n")
        
        print(f"\n📄 Отчет сохранен в файл: {report_file}")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(find_all_chats())
