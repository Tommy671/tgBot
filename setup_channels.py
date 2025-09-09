#!/usr/bin/env python3
"""
Простой скрипт для настройки каналов (для заказчика)
"""
import asyncio
import sys
import os
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from telegram import Bot

async def setup_channels():
    """Настройка каналов"""
    print("🚀 НАСТРОЙКА КАНАЛОВ ДЛЯ CRM СИСТЕМЫ")
    print("=" * 60)
    
    try:
        bot = Bot(token=settings.TELEGRAM_TOKEN)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"🤖 Ваш бот: {bot_info.first_name} (@{bot_info.username})")
        print(f"🆔 ID бота: {bot_info.id}")
        
        print(f"\n📋 ЧТО НУЖНО СДЕЛАТЬ:")
        print("=" * 60)
        print("1. Создайте 2 канала в Telegram:")
        print("   📺 Бесплатный канал (для регистрации)")
        print("   💰 Платный канал (для подписчиков)")
        print()
        print("2. Добавьте бота в ОБА канала как администратора")
        print("3. Дайте боту права:")
        print("   ✅ Удаление участников")
        print("   ✅ Приглашение пользователей")
        print("   ✅ Просмотр участников")
        print()
        print("4. Запустите этот скрипт")
        
        input("\n⏸️ Нажмите Enter когда будете готовы...")
        
        # Проверяем текущие настройки
        print(f"\n🔍 ПРОВЕРЯЕМ ТЕКУЩИЕ НАСТРОЙКИ:")
        print("=" * 60)
        
        channels_to_check = [
            ("Бесплатный канал", settings.FREE_CHANNEL_ID),
            ("Платный канал", settings.PAID_CHANNEL_ID),
        ]
        
        found_channels = {}
        
        for name, channel_id in channels_to_check:
            try:
                print(f"\n🔍 Проверяем {name}: {channel_id}")
                chat_info = await bot.get_chat(channel_id)
                member_count = await bot.get_chat_member_count(channel_id)
                
                print(f"✅ Канал найден!")
                print(f"📺 Название: {chat_info.title}")
                print(f"🆔 ID: {chat_info.id}")
                print(f"👥 Участников: {member_count}")
                
                if hasattr(chat_info, 'username') and chat_info.username:
                    print(f"🔗 Username: @{chat_info.username}")
                
                # Проверяем права бота
                try:
                    admins = await bot.get_chat_administrators(channel_id)
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
                        if bot_permissions.get('can_restrict_members'):
                            print(f"✅ Может удалять участников")
                        else:
                            print(f"❌ НЕ может удалять участников")
                    else:
                        print("❌ Бот НЕ является администратором")
                        
                except Exception as e:
                    print(f"⚠️ Не удалось проверить права: {e}")
                
                # Сохраняем информацию
                found_channels[name] = {
                    'id': chat_info.id,
                    'title': chat_info.title,
                    'username': getattr(chat_info, 'username', None),
                    'member_count': member_count,
                    'bot_is_admin': bot_is_admin,
                    'can_remove': bot_permissions.get('can_restrict_members', False)
                }
                
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                print(f"💡 Убедитесь, что бот добавлен в канал")
        
        # Анализируем результаты
        print(f"\n📊 РЕЗУЛЬТАТЫ:")
        print("=" * 60)
        
        if len(found_channels) == 0:
            print("❌ Каналы не найдены!")
            print("💡 Убедитесь, что бот добавлен в каналы")
            
        elif len(found_channels) == 1:
            print("⚠️ Найден только 1 канал!")
            print("💡 Создайте второй канал или используйте один для обеих целей")
            
        else:
            print("✅ Найдено 2 канала!")
            
            all_good = True
            for name, info in found_channels.items():
                status = "✅" if info['bot_is_admin'] and info['can_remove'] else "❌"
                print(f"{status} {name}: {info['title']}")
                if not (info['bot_is_admin'] and info['can_remove']):
                    all_good = False
            
            if all_good:
                print(f"\n🎉 ВСЕ ГОТОВО! Система настроена правильно!")
            else:
                print(f"\n⚠️ Нужно исправить права бота в каналах")
        
        # Генерируем конфигурацию
        print(f"\n🔧 КОНФИГУРАЦИЯ:")
        print("=" * 60)
        
        if 'Бесплатный канал' in found_channels and 'Платный канал' in found_channels:
            free_id = found_channels['Бесплатный канал']['id']
            paid_id = found_channels['Платный канал']['id']
            
            print(f"FREE_CHANNEL_ID={free_id}")
            print(f"PAID_CHANNEL_ID={paid_id}")
            
            print(f"\n📝 Скопируйте эти строки в ваш .env файл")
            
        elif len(found_channels) == 1:
            channel_id = list(found_channels.values())[0]['id']
            print(f"# Один канал для обеих целей")
            print(f"FREE_CHANNEL_ID={channel_id}")
            print(f"PAID_CHANNEL_ID={channel_id}")
            
        # Сохраняем отчет
        report_file = f"setup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("ОТЧЕТ О НАСТРОЙКЕ КАНАЛОВ\n")
            f.write("=" * 60 + "\n")
            f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Бот: {bot_info.first_name} (@{bot_info.username})\n\n")
            
            for name, info in found_channels.items():
                f.write(f"{name}:\n")
                f.write(f"  Название: {info['title']}\n")
                f.write(f"  ID: {info['id']}\n")
                f.write(f"  Username: @{info['username']}\n")
                f.write(f"  Участников: {info['member_count']}\n")
                f.write(f"  Бот админ: {'Да' if info['bot_is_admin'] else 'Нет'}\n")
                f.write(f"  Может удалять: {'Да' if info['can_remove'] else 'Нет'}\n\n")
        
        print(f"\n📄 Отчет сохранен в файл: {report_file}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(setup_channels())
