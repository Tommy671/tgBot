#!/usr/bin/env python3
"""
Скрипт для поиска ID каналов по username и ссылке-приглашению
"""
import asyncio
import sys
import os
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from telegram import Bot

async def find_channel_ids():
    """Поиск ID каналов"""
    print("🔍 ПОИСК ID КАНАЛОВ")
    print("=" * 50)
    
    try:
        bot = Bot(token=settings.TELEGRAM_TOKEN)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"🤖 Бот: {bot_info.first_name} (@{bot_info.username})")
        print(f"🆔 ID бота: {bot_info.id}")
        
        print(f"\n📋 ИСХОДНЫЕ ДАННЫЕ:")
        print(f"FREE_CHANNEL_ID: {settings.FREE_CHANNEL_ID}")
        print(f"PAID_CHANNEL_ID: {settings.PAID_CHANNEL_ID}")
        
        found_channels = {}
        
        # 1. Ищем бесплатный канал по username
        print(f"\n🔍 Поиск бесплатного канала по username...")
        try:
            free_channel_username = settings.FREE_CHANNEL_ID
            if free_channel_username.startswith('@'):
                free_channel_username = free_channel_username[1:]  # Убираем @
            
            print(f"Ищем канал: @{free_channel_username}")
            
            chat_info = await bot.get_chat(f"@{free_channel_username}")
            member_count = await bot.get_chat_member_count(f"@{free_channel_username}")
            
            print(f"✅ Бесплатный канал найден!")
            print(f"📺 Название: {chat_info.title}")
            print(f"🆔 ID: {chat_info.id}")
            print(f"👥 Участников: {member_count}")
            print(f"📝 Тип: {chat_info.type}")
            
            # Проверяем права бота
            try:
                admins = await bot.get_chat_administrators(chat_info.id)
                bot_is_admin = False
                bot_permissions = {}
                
                for admin in admins:
                    if admin.user.id == bot_info.id:
                        bot_is_admin = True
                        bot_permissions = {
                            'can_restrict_members': admin.can_restrict_members,
                            'can_invite_users': admin.can_invite_users,
                        }
                        break
                
                if bot_is_admin:
                    print(f"✅ Бот является администратором")
                    print(f"🔧 Может удалять участников: {'✅' if bot_permissions.get('can_restrict_members') else '❌'}")
                else:
                    print("❌ Бот НЕ является администратором")
                    
            except Exception as e:
                print(f"⚠️ Не удалось проверить права: {e}")
            
            found_channels['FREE'] = {
                'id': chat_info.id,
                'title': chat_info.title,
                'username': getattr(chat_info, 'username', None),
                'member_count': member_count,
                'type': chat_info.type,
                'bot_is_admin': bot_is_admin,
                'can_remove': bot_permissions.get('can_restrict_members', False)
            }
            
        except Exception as e:
            print(f"❌ Ошибка при поиске бесплатного канала: {e}")
            print(f"💡 Убедитесь, что:")
            print(f"   - Канал существует")
            print(f"   - Бот добавлен в канал")
            print(f"   - Username указан правильно")
        
        # 2. Ищем платный канал по ссылке-приглашению
        print(f"\n🔍 Поиск платного канала по ссылке-приглашению...")
        try:
            invite_link = settings.PAID_CHANNEL_ID
            print(f"Ищем канал по ссылке: {invite_link}")
            
            # Пытаемся получить информацию о канале по ссылке-приглашению
            chat_info = await bot.get_chat(invite_link)
            member_count = await bot.get_chat_member_count(invite_link)
            
            print(f"✅ Платный канал найден!")
            print(f"📺 Название: {chat_info.title}")
            print(f"🆔 ID: {chat_info.id}")
            print(f"👥 Участников: {member_count}")
            print(f"📝 Тип: {chat_info.type}")
            
            if hasattr(chat_info, 'username') and chat_info.username:
                print(f"🔗 Username: @{chat_info.username}")
            
            # Проверяем права бота
            try:
                admins = await bot.get_chat_administrators(chat_info.id)
                bot_is_admin = False
                bot_permissions = {}
                
                for admin in admins:
                    if admin.user.id == bot_info.id:
                        bot_is_admin = True
                        bot_permissions = {
                            'can_restrict_members': admin.can_restrict_members,
                            'can_invite_users': admin.can_invite_users,
                        }
                        break
                
                if bot_is_admin:
                    print(f"✅ Бот является администратором")
                    print(f"🔧 Может удалять участников: {'✅' if bot_permissions.get('can_restrict_members') else '❌'}")
                else:
                    print("❌ Бот НЕ является администратором")
                    
            except Exception as e:
                print(f"⚠️ Не удалось проверить права: {e}")
            
            found_channels['PAID'] = {
                'id': chat_info.id,
                'title': chat_info.title,
                'username': getattr(chat_info, 'username', None),
                'member_count': member_count,
                'type': chat_info.type,
                'bot_is_admin': bot_is_admin,
                'can_remove': bot_permissions.get('can_restrict_members', False)
            }
            
        except Exception as e:
            print(f"❌ Ошибка при поиске платного канала: {e}")
            print(f"💡 Убедитесь, что:")
            print(f"   - Ссылка-приглашение действительна")
            print(f"   - Бот добавлен в канал")
            print(f"   - Ссылка не истекла")
        
        # Анализируем результаты
        print(f"\n📊 РЕЗУЛЬТАТЫ ПОИСКА:")
        print("=" * 50)
        
        if len(found_channels) == 0:
            print("❌ Каналы не найдены!")
            print("💡 Проверьте настройки в .env файле")
            
        elif len(found_channels) == 1:
            print("⚠️ Найден только 1 канал!")
            for channel_type, info in found_channels.items():
                print(f"✅ {channel_type} канал: {info['title']} (ID: {info['id']})")
            
        else:
            print("✅ Найдены оба канала!")
            for channel_type, info in found_channels.items():
                print(f"✅ {channel_type} канал: {info['title']} (ID: {info['id']})")
        
        # Генерируем конфигурацию
        print(f"\n🔧 КОНФИГУРАЦИЯ ДЛЯ .env:")
        print("=" * 50)
        
        if 'FREE' in found_channels and 'PAID' in found_channels:
            free_id = found_channels['FREE']['id']
            paid_id = found_channels['PAID']['id']
            
            print(f"FREE_CHANNEL_ID={free_id}")
            print(f"PAID_CHANNEL_ID={paid_id}")
            
            print(f"\n📝 Скопируйте эти строки в ваш .env файл")
            
            # Проверяем, что каналы разные
            if free_id == paid_id:
                print(f"\n⚠️ ВНИМАНИЕ: Оба канала имеют одинаковый ID!")
                print(f"Это означает, что FREE_CHANNEL_ID и PAID_CHANNEL_ID указывают на один канал")
            else:
                print(f"\n✅ Каналы разные - конфигурация корректна!")
                
        elif len(found_channels) == 1:
            channel_id = list(found_channels.values())[0]['id']
            print(f"# Найден только один канал")
            print(f"FREE_CHANNEL_ID={channel_id}")
            print(f"PAID_CHANNEL_ID={channel_id}")
        
        # Проверяем права для удаления
        print(f"\n🔐 ПРОВЕРКА ПРАВ ДЛЯ УДАЛЕНИЯ:")
        print("=" * 50)
        
        can_remove_from_paid = False
        for channel_type, info in found_channels.items():
            if channel_type == 'PAID' and info['bot_is_admin'] and info['can_remove']:
                can_remove_from_paid = True
                print(f"✅ Платный канал: бот может удалять участников")
            elif channel_type == 'PAID':
                print(f"❌ Платный канал: бот НЕ может удалять участников")
        
        if not can_remove_from_paid:
            print(f"\n⚠️ ВНИМАНИЕ: Бот не может удалять участников из платного канала!")
            print("💡 Необходимо дать боту права:")
            print("   - Удаление участников")
            print("   - Ограничение участников")
        
        # Сохраняем отчет
        report_file = f"channel_ids_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("ОТЧЕТ О ПОИСКЕ ID КАНАЛОВ\n")
            f.write("=" * 50 + "\n")
            f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Бот: {bot_info.first_name} (@{bot_info.username})\n\n")
            
            f.write("ИСХОДНЫЕ ДАННЫЕ:\n")
            f.write(f"FREE_CHANNEL_ID: {settings.FREE_CHANNEL_ID}\n")
            f.write(f"PAID_CHANNEL_ID: {settings.PAID_CHANNEL_ID}\n\n")
            
            for channel_type, info in found_channels.items():
                f.write(f"{channel_type} КАНАЛ:\n")
                f.write(f"  Название: {info['title']}\n")
                f.write(f"  ID: {info['id']}\n")
                f.write(f"  Username: @{info['username']}\n")
                f.write(f"  Участников: {info['member_count']}\n")
                f.write(f"  Тип: {info['type']}\n")
                f.write(f"  Бот админ: {'Да' if info['bot_is_admin'] else 'Нет'}\n")
                f.write(f"  Может удалять: {'Да' if info['can_remove'] else 'Нет'}\n\n")
            
            f.write("КОНФИГУРАЦИЯ ДЛЯ .env:\n")
            if 'FREE' in found_channels and 'PAID' in found_channels:
                f.write(f"FREE_CHANNEL_ID={found_channels['FREE']['id']}\n")
                f.write(f"PAID_CHANNEL_ID={found_channels['PAID']['id']}\n")
        
        print(f"\n📄 Отчет сохранен в файл: {report_file}")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(find_channel_ids())
