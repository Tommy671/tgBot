"""
Главный файл запуска системы Telegram Bot + FastAPI CRM
"""
import os
import sys
import threading
import asyncio
import uvicorn
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv('.env')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверяем наличие токена
if not os.environ.get('TELEGRAM_TOKEN') or os.environ.get('TELEGRAM_TOKEN') == 'your_telegram_bot_token_here':
    logger.error("TELEGRAM_TOKEN не установлен в переменных окружения")
    print("❌ ОШИБКА: TELEGRAM_TOKEN не установлен в переменных окружения")
    print("📝 Создайте файл .env на основе .env.example и добавьте ваш токен")
    print("🔑 Получить токен: https://t.me/BotFather")
    sys.exit(1)


def check_dependencies():
    """Проверка зависимостей"""
    required_packages = {
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'sqlalchemy': 'sqlalchemy',
        'python-telegram-bot': 'telegram',
        'pydantic-settings': 'pydantic_settings'
    }
    
    missing_packages = []
    for package, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Отсутствуют зависимости: {missing_packages}")
        print(f"❌ Отсутствуют зависимости: {', '.join(missing_packages)}")
        print("📦 Установите зависимости: pip install -r requirements.txt")
        return False
    
    logger.info("Все зависимости установлены")
    print("✅ Все зависимости установлены")
    return True


def run_bot():
    """Запуск Telegram бота с ретраями"""
    import time
    attempt = 0
    while True:
        try:
            # Сбрасываем event loop перед каждой попыткой (Windows compatibility)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    asyncio.set_event_loop(asyncio.new_event_loop())
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())

            from app.bot.bot import create_bot, reset_bot_singleton
            reset_bot_singleton()
            bot = create_bot()
            logger.info("Запуск Telegram бота...")
            print("🤖 Запуск Telegram бота...")
            bot.run()
            # Если run() завершился (обычно по Ctrl+C), выходим из цикла
            break
        except Exception as e:
            attempt += 1
            wait_seconds = min(60, 5 * attempt)
            logger.error(f"Ошибка запуска бота: {e}")
            print(f"❌ Ошибка запуска бота: {e}")
            print(f"⏳ Повторный запуск через {wait_seconds} сек...")
            time.sleep(wait_seconds)


def run_admin():
    """Запуск FastAPI админки"""
    try:
        from app.admin.app import app
        from app.core.database import check_database_connection
        
        # Проверяем соединение с БД перед запуском
        if not check_database_connection():
            logger.error("Не удалось подключиться к базе данных")
            print("❌ Не удалось подключиться к базе данных")
            return
        
        logger.info("Запуск FastAPI админки...")
        print("🌐 Запуск FastAPI админки...")
        
        uvicorn.run(
            app,
            host=os.environ.get('HOST', '0.0.0.0'),
            port=int(os.environ.get('PORT', 8001)),
            log_level="info",
            access_log=True
        )
    except Exception as e:
        logger.error(f"Ошибка запуска админки: {e}")
        print(f"❌ Ошибка запуска админки: {e}")


def run_subscription_checker():
    """Запуск периодической проверки подписок"""
    try:
        import asyncio
        from app.core.subscription_manager import subscription_manager
        from app.core.database import get_db
        
        async def check_subscriptions_loop():
            """Цикл проверки подписок"""
            while True:
                try:
                    # Получаем сессию БД
                    db = next(get_db())
                    try:
                        # Проверяем истекающие подписки
                        await subscription_manager.check_expiring_subscriptions(db)
                        
                        # Удаляем пользователей с истекшими подписками
                        await subscription_manager.remove_expired_subscriptions(db)
                        
                        logger.info("Subscription check completed successfully")
                        
                    finally:
                        db.close()
                        
                except Exception as e:
                    logger.error(f"Error in subscription check loop: {e}")
                
                # Ждем 1 час до следующей проверки
                await asyncio.sleep(3600)  # 1 час
        
        # Запускаем цикл проверки
        asyncio.run(check_subscriptions_loop())
        
    except Exception as e:
        logger.error(f"Error in subscription checker: {e}")
        print(f"❌ Ошибка в проверке подписок: {e}")


def main():
    """Главная функция запуска"""
    logger.info("Запуск системы Telegram Bot + FastAPI CRM...")
    print("🚀 Запуск системы Telegram Bot + FastAPI CRM...")
    print("=" * 50)
    
    # Проверяем зависимости
    if not check_dependencies():
        sys.exit(1)
    
    # Для Windows запускаем админку в отдельном потоке, бота в основном
    admin_thread = threading.Thread(target=run_admin, daemon=True)
    subscription_thread = threading.Thread(target=run_subscription_checker, daemon=True)
    
    try:
        # Запускаем админку в фоне
        logger.info("Запуск FastAPI админки в отдельном потоке...")
        print("🌐 Запуск FastAPI админки в отдельном потоке...")
        admin_thread.start()
        
        # Запускаем проверку подписок в фоне
        logger.info("Запуск проверки подписок в отдельном потоке...")
        print("⏰ Запуск проверки подписок в отдельном потоке...")
        subscription_thread.start()
        
        # Небольшая задержка для запуска админки
        import time
        time.sleep(3)
        
        # Проверяем, что админка запустилась
        if admin_thread.is_alive():
            logger.info("Админка запущена успешно")
            print("✅ Админка запущена!")
            print("=" * 50)
            print("🌐 FastAPI Admin: http://localhost:8001")
            print("📚 API Docs: http://localhost:8001/docs")
            print("🔍 Health Check: http://localhost:8001/health")
            print("=" * 50)
        else:
            logger.warning("Админка не запустилась")
            print("⚠️ Админка не запустилась, но продолжаем работу...")
        
        # Запускаем бота в основном потоке (для Windows)
        logger.info("Запуск Telegram бота в основном потоке...")
        print("🤖 Запуск Telegram бота в основном потоке...")
        run_bot()
            
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
        print("\n🛑 Остановка системы...")
        print("👋 До свидания!")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        print(f"❌ Критическая ошибка: {e}")
    finally:
        logger.info("Завершение работы системы")
        sys.exit(0)


if __name__ == "__main__":
    main()
