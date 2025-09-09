"""
Telegram Bot Module
"""
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ChatMemberHandler, ChatJoinRequestHandler
)
from telegram.ext import CallbackContext
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db_session
from app.core.utils import rate_limit, retry_on_failure, measure_performance
from app.models.models import User, Subscription, BotSettings, ChannelMembership

# Настройка логирования
logging.basicConfig(
    format=settings.LOG_FORMAT,
    level=getattr(logging, settings.LOG_LEVEL.upper())
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    FILLING_QUESTIONNAIRE,
    WAITING_FOR_CONSENT,
    MAIN_MENU,
    SETTINGS_MENU,
    PAYMENT_MENU
) = range(5)

# Структура для хранения временных данных пользователей
user_data_temp = {}

def get_bot_setting(key: str, default: str = "") -> str:
    """Получение настройки бота из БД"""
    try:
        with get_db_session() as db:
            setting = db.query(BotSettings).filter(BotSettings.key == key).first()
            return setting.value if setting else default
    except Exception as e:
        logger.error(f"Error getting bot setting {key}: {e}")
        return default

def generate_protected_link(base_url: str, user_id: int) -> str:
    """Генерация защищенной ссылки с невидимыми символами и пользовательским ID"""
    # Добавляем невидимые символы для затруднения копирования
    invisible_chars = ["\u200B", "\u200C", "\u200D", "\uFEFF", "\u2060"]  # Разные невидимые символы
    
    # Создаем уникальную защищенную ссылку на основе user_id
    protected_url = ""
    
    for i, char in enumerate(base_url):
        protected_url += char
        # Добавляем невидимые символы чаще и в зависимости от user_id
        if i % 2 == 1:  # Каждый второй символ
            char_index = (user_id + i) % len(invisible_chars)
            protected_url += invisible_chars[char_index]
    
    # Добавляем невидимые символы в конце для дополнительной защиты
    for _ in range(3):
        char_index = (user_id + _) % len(invisible_chars)
        protected_url += invisible_chars[char_index]
    
    return protected_url


class TelegramBot:
    """Telegram Bot Class"""
    
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков сообщений"""
        # Конфигурируем диалог и маршруты по callback-кнопкам корректно
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start_command)],
            states={
                FILLING_QUESTIONNAIRE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_questionnaire)
                ],
                WAITING_FOR_CONSENT: [
                    CallbackQueryHandler(self.handle_consent, pattern="^consent_")
                ],
                MAIN_MENU: [
                    CallbackQueryHandler(self.handle_profile, pattern="^profile$"),
                    CallbackQueryHandler(self.handle_settings, pattern="^settings$"),
                    CallbackQueryHandler(self.handle_private_chat, pattern="^private_chat$"),
                    CallbackQueryHandler(self.show_payment_menu, pattern="^payment$"),  # совместимость со старой кнопкой
                    CallbackQueryHandler(self.handle_update_profile, pattern="^update_profile$"),
                    CallbackQueryHandler(self.handle_main_menu, pattern="^main_back$")
                ],
                SETTINGS_MENU: [
                    CallbackQueryHandler(self.handle_settings_menu, pattern="^settings_"),
                    CallbackQueryHandler(self.show_payment_menu, pattern="^payment$"),
                    CallbackQueryHandler(self.handle_main_menu, pattern="^main_back$")
                ],
                PAYMENT_MENU: [
                    CallbackQueryHandler(self.handle_payment_menu, pattern="^payment_"),
                    CallbackQueryHandler(self.handle_settings_menu, pattern="^settings_back$")
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
            per_message=False
        )
        
        self.application.add_handler(conv_handler)
        
        # Обработчики статусов участников (для групп/супергрупп)
        self.application.add_handler(ChatMemberHandler(self.handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_chat_members))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, self.handle_left_chat_member))
        
        # Запросы на вступление (если включены в канале)
        self.application.add_handler(ChatJoinRequestHandler(self.handle_chat_join_request))
        
        # Отладка
        self.application.add_handler(MessageHandler(filters.ALL, self.handle_all_messages))
        
        logger.info("Handlers setup completed")
    
    async def error_handler(self, update: Update, context):
        """Обработчик ошибок"""
        logger.error(f"Произошла ошибка: {context.error}")
        
        # Отправляем сообщение пользователю об ошибке
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте использовать команду /start для перезапуска."
            )
        
        return ConversationHandler.END
    
    @measure_performance
    @rate_limit(requests_per_minute=30, requests_per_hour=300)
    async def profile_command(self, update: Update, context):
        """Обработчик команды /profile"""
        await self.handle_profile(update, context)
        return MAIN_MENU
    
    @measure_performance
    @rate_limit(requests_per_minute=30, requests_per_hour=300)
    async def settings_command(self, update: Update, context):
        """Обработчик команды /settings"""
        await self.handle_settings(update, context)
        return SETTINGS_MENU
    
    @measure_performance
    @rate_limit(requests_per_minute=10, requests_per_hour=100)
    async def start_command(self, update: Update, context):
        """Обработчик команды /start"""
        user = update.effective_user
        telegram_id = user.id
        
        # Очищаем временные данные при старте
        if user.id in user_data_temp:
            del user_data_temp[user.id]
        
        # Проверяем, зарегистрирован ли пользователь
        try:
            with get_db_session() as db:
                existing_user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if existing_user and existing_user.consent_given:
                    # Пользователь уже зарегистрирован, предлагаем обновить данные
                    keyboard = [
                        [InlineKeyboardButton("🔄 Обновить данные", callback_data="update_profile")],
                        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_back")]
                    ]
                    await update.message.reply_text(
                        "👋 С возвращением! Вы уже зарегистрированы в системе.\n\n"
                        "Выберите действие:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    return MAIN_MENU
                else:
                    # Начинаем регистрацию
                    await self.start_registration(update, context)
                    return FILLING_QUESTIONNAIRE
        except Exception as e:
            # В случае ошибки начинаем регистрацию заново
            logger.error(f"Ошибка при проверке пользователя: {e}")
            await self.start_registration(update, context)
            return FILLING_QUESTIONNAIRE
    
    async def start_registration(self, update: Update, context):
        """Начало процесса регистрации"""
        user = update.effective_user
        user_data_temp[user.id] = {
            'step': 0,
            'data': {}
        }
        
        questions = [
            "Введите фамилию и имя (через пробел):",
            "Введите сферу деятельности:",
            "Введите название компании:",
            "Введите вашу роль в компании:",
            "Введите контактный номер телефона (+7XXXXXXXXX или 8XXXXXXXXX):",
            "Введите цель участия:"
        ]
        
        await update.message.reply_text(
            f"Добро пожаловать! Для регистрации необходимо заполнить анкету.\n\n{questions[0]}"
        )
    
    @measure_performance
    async def handle_questionnaire(self, update: Update, context):
        """Обработка ответов на вопросы анкеты"""
        user = update.effective_user
        user_id = user.id
        
        if user_id not in user_data_temp:
            await update.message.reply_text("Произошла ошибка. Начните заново с команды /start")
            return ConversationHandler.END
        
        user_data = user_data_temp[user_id]
        step = user_data['step']
        
        # Сохраняем ответ
        fields = ['full_name', 'activity_field', 'company', 'role_in_company', 'contact_number', 'participation_purpose']
        value = update.message.text
        
        # Валидация фамилии и имени
        if fields[step] == 'full_name':
            if len(value.split()) < 2:
                await update.message.reply_text("Пожалуйста, введите фамилию и имя через пробел (например: Иванов Иван)")
                return FILLING_QUESTIONNAIRE
        
        # Валидация номера телефона
        if fields[step] == 'contact_number':
            phone_pattern = r'^(\+7|8)\d{10}$'
            if not re.match(phone_pattern, value):
                await update.message.reply_text("Пожалуйста, введите корректный номер телефона в формате +7XXXXXXXXX или 8XXXXXXXXX")
                return FILLING_QUESTIONNAIRE
        
        user_data['data'][fields[step]] = value
        user_data['step'] += 1
        
        questions = [
            "Введите фамилию и имя (через пробел):",
            "Введите сферу деятельности:",
            "Введите название компании:",
            "Введите вашу роль в компании:",
            "Введите контактный номер телефона (+7XXXXXXXXX или 8XXXXXXXXX):",
            "Введите цель участия:"
        ]
        
        if user_data['step'] < len(questions):
            await update.message.reply_text(questions[user_data['step']])
        else:
            # Анкета заполнена, проверяем тип операции
            user = update.effective_user
            telegram_id = user.id
            
            # Проверяем, есть ли уже пользователь в базе
            try:
                with get_db_session() as db:
                    existing_user = db.query(User).filter(User.telegram_id == telegram_id).first()
                    
                    if existing_user and existing_user.consent_given:
                        # Пользователь уже зарегистрирован - обновляем данные без согласия
                        await self.update_user_data(update, context, user_data)
                        return MAIN_MENU
                    else:
                        # Новый пользователь - запрашиваем согласие
                        await self.request_consent_for_update(update, context)
                        return WAITING_FOR_CONSENT
            except Exception as e:
                logger.error(f"Ошибка при проверке пользователя: {e}")
                # В случае ошибки запрашиваем согласие
                await self.request_consent_for_update(update, context)
            return WAITING_FOR_CONSENT
    
    async def update_user_data(self, update: Update, context, user_data):
        """Обновление данных пользователя без запроса согласия"""
        user = update.effective_user
        user_id = user.id
        
        try:
            with get_db_session() as db:
                existing_user = db.query(User).filter(User.telegram_id == user_id).first()
                
                if existing_user:
                    # Обновляем данные существующего пользователя
                    existing_user.full_name = user_data['data'].get('full_name', '')
                    existing_user.activity_field = user_data['data'].get('activity_field', '')
                    existing_user.company = user_data['data'].get('company', '')
                    existing_user.role_in_company = user_data['data'].get('role_in_company', '')
                    existing_user.contact_number = user_data['data'].get('contact_number', '')
                    existing_user.participation_purpose = user_data['data'].get('participation_purpose', '')
                    existing_user.last_activity = datetime.now(timezone.utc)
                    logger.info(f"Данные пользователя {user_id} обновлены")
                    
                    # Очищаем временные данные
                    if user_id in user_data_temp:
                        del user_data_temp[user_id]
                    
                    await update.message.reply_text(
                        "✅ Данные профиля успешно обновлены!"
                    )
                    
                    # Показываем главное меню
                    await self.show_main_menu(update, context)
                else:
                    await update.message.reply_text(
                        "❌ Пользователь не найден. Используйте /start для регистрации."
                    )
        except Exception as e:
            logger.error(f"Ошибка при обновлении данных пользователя: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обновлении данных. Попробуйте позже."
            )

    async def request_consent_for_update(self, update: Update, context):
        """Запрос согласия на обработку персональных данных при обновлении"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
                InlineKeyboardButton("❌ Не согласен", callback_data="consent_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Анкета заполнена! Теперь необходимо дать согласие на обработку персональных данных.\n\n"
            "📋 Ознакомьтесь с нашей политикой конфиденциальности:\n"
            f"{settings.PRIVACY_POLICY_URL}\n\n"
            "Нажимая 'Согласен', вы подтверждаете, что даете согласие на обработку ваших персональных данных в соответствии с указанной политикой.",
            reply_markup=reply_markup
        )
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def handle_consent(self, update: Update, context):
        """Обработка согласия на обработку персональных данных"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "consent_yes":
            # Сохраняем пользователя в базу данных
            user = update.effective_user
            user_id = user.id
            user_data = user_data_temp[user_id]
            
            try:
                with get_db_session() as db:
                    # Проверяем, существует ли пользователь
                    existing_user = db.query(User).filter(User.telegram_id == user_id).first()
                    
                    if existing_user:
                        # Обновляем существующего пользователя
                        existing_user.username = user.username
                        existing_user.full_name = user_data['data'].get('full_name', '')
                        existing_user.activity_field = user_data['data'].get('activity_field', '')
                        existing_user.company = user_data['data'].get('company', '')
                        existing_user.role_in_company = user_data['data'].get('role_in_company', '')
                        existing_user.contact_number = user_data['data'].get('contact_number', '')
                        existing_user.participation_purpose = user_data['data'].get('participation_purpose', '')
                        existing_user.consent_given = True
                        existing_user.consent_date = datetime.now(timezone.utc)
                        existing_user.last_activity = datetime.now(timezone.utc)
                        logger.info(f"Пользователь {user_id} обновлен")
                    else:
                        # Создаем нового пользователя
                        new_user = User(
                            telegram_id=user_id,
                            username=user.username,
                            full_name=user_data['data'].get('full_name', ''),
                            activity_field=user_data['data'].get('activity_field', ''),
                            company=user_data['data'].get('company', ''),
                            role_in_company=user_data['data'].get('role_in_company', ''),
                            contact_number=user_data['data'].get('contact_number', ''),
                            participation_purpose=user_data['data'].get('participation_purpose', ''),
                            consent_given=True,
                            consent_date=datetime.now(timezone.utc)
                        )
                        db.add(new_user)
                        logger.info(f"Новый пользователь {user_id} создан")
                    
                    # commit происходит автоматически в контекстном менеджере
            except Exception as e:
                logger.error(f"Ошибка при создании пользователя: {e}")
                await query.edit_message_text(
                    "❌ Произошла ошибка при регистрации. Попробуйте позже или используйте /start для повторной попытки."
                )
                return ConversationHandler.END
            
            # Очищаем временные данные
            del user_data_temp[user_id]
            
            await query.edit_message_text(
                "✅ Регистрация завершена! Добро пожаловать в систему!"
            )
            
            # Показываем главное меню
            await self.show_main_menu(update, context)
            return MAIN_MENU
        else:
            await query.edit_message_text(
                "❌ Без согласия на обработку персональных данных регистрация невозможна.\n"
                "Используйте /start для повторной попытки."
            )
            return ConversationHandler.END
    
    async def show_main_menu(self, update: Update, context):
        """Показ главного меню"""
        keyboard = [
            [InlineKeyboardButton("💬 Приватный чат", callback_data="private_chat")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
            [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Проверяем, откуда пришел запрос
        if hasattr(update, 'callback_query') and update.callback_query:
            # Это callback query (нажатие кнопки)
            await update.callback_query.edit_message_text(
                "🏠 Главное меню\n\nВыберите нужный раздел:",
                reply_markup=reply_markup
            )
        else:
            # Это обычное сообщение (команда /start)
            await update.message.reply_text(
                "🏠 Главное меню\n\nВыберите нужный раздел:",
                reply_markup=reply_markup
            )
    
    async def handle_main_menu(self, update: Update, context: CallbackContext) -> int:
        """Обработка главного меню"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "main_back":
            # Очищаем временные данные пользователя при возврате в главное меню
            user = update.effective_user
            if user.id in user_data_temp:
                del user_data_temp[user.id]
            
            # Показываем правильное главное меню с 3 кнопками
            await self.show_main_menu(update, context)
            return MAIN_MENU
    
        # Обработка старых callback'ов для совместимости
        if query.data == "payment":
            # Перенаправляем на меню настроек
            await self.handle_settings(update, context)
            return SETTINGS_MENU
        
        return MAIN_MENU

    async def handle_private_chat(self, update: Update, context):
        """Обработка запроса на приватный чат"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        telegram_id = user.id
        
        # Проверяем подписку пользователя
        try:
            with get_db_session() as db:
                db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if db_user and db_user.has_active_subscription():
                    # У пользователя есть активная подписка
                    # Создаем сообщение с прямой ссылкой на приватный чат
                    private_link = settings.PRIVATE_CHAT_LINK
                    
                    await query.edit_message_text(
                        "🎉 Добро пожаловать в платный канал!\n\n"
                        "Ваша подписка активирована!\n\n"
                        "Нажмите кнопку ниже для входа в приватный чат:",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔗 Войти в приватный чат", url=private_link)],
                            [InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")]
                        ])
                    )
                else:
                    # У пользователя нет подписки
                    await query.edit_message_text(
                        "❌ Для доступа к приватному чату необходима подписка.\n\n"
                        "Перейдите в раздел 'Настройки' → 'Оплата' для оформления подписки.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
                        ]])
                    )
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
                ]])
            )
    
    async def handle_settings(self, update: Update, context):
        """Обработка раздела настроек"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("📝 Заполнить анкету заново", callback_data="settings_refill")],
            [InlineKeyboardButton("💳 Оплата", callback_data="settings_payment")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="settings_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ Настройки\n\nВыберите действие:",
            reply_markup=reply_markup
        )
        return SETTINGS_MENU
    
    async def handle_settings_menu(self, update: Update, context: CallbackContext) -> int:
        """Обработка меню настроек"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "settings_back":
            await self.show_main_menu(update, context)
            return MAIN_MENU
        elif query.data == "settings_payment":
            # Переходим в меню оплаты
            await self.show_payment_menu(update, context)
            return PAYMENT_MENU
        elif query.data == "settings_refill":
            # Заполняем анкету заново
            await self.handle_update_profile(update, context)
            return FILLING_QUESTIONNAIRE
        
        return SETTINGS_MENU

    
    async def show_payment_menu(self, update: Update, context):
        """Показ меню оплаты"""
        query = update.callback_query
        user = update.effective_user
        telegram_id = user.id
        
        try:
            with get_db_session() as db:
                db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if db_user and db_user.has_active_subscription():
                    # У пользователя есть подписка
                    subscription = db_user.subscription
                    end_date = subscription.end_date.strftime("%d.%m.%Y")
                    
                    keyboard = [
                        [InlineKeyboardButton("🔄 Подключить автопродление", callback_data="payment_auto_renewal")],
                        [InlineKeyboardButton("❌ Отключить подписку", callback_data="payment_cancel")],
                        [InlineKeyboardButton("⬅️ Назад", callback_data="payment_back")]
                    ]
                    
                    await query.edit_message_text(
                        f"💳 Управление подпиской\n\n"
                        f"✅ У вас активная подписка\n"
                        f"📅 Действует до: {end_date}\n"
                        f"💰 Стоимость: {get_bot_setting('subscription_price', '999')} ₽/месяц\n\n"
                        f"Выберите действие:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    # У пользователя нет подписки
                    keyboard = [
                        [InlineKeyboardButton("💳 Оформить подписку", callback_data="payment_subscribe")],
                        [InlineKeyboardButton("⬅️ Назад", callback_data="payment_back")]
                    ]
                    
                    await query.edit_message_text(
                        f"💳 Оформление подписки\n\n"
                        f"💰 Стоимость: {get_bot_setting('subscription_price', '999')} ₽/месяц\n"
                        f"📅 Срок действия: {settings.SUBSCRIPTION_DURATION_DAYS} дней\n\n"
                        f"Выберите действие:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
        except Exception as e:
            logger.error(f"Ошибка при показе меню оплаты: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Назад", callback_data="payment_back")
                ]])
            )
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def handle_payment_menu(self, update: Update, context):
        """Обработка выбора в меню оплаты"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "payment_back":
            # Возвращаемся в настройки
            await self.handle_settings(update, context)
            return SETTINGS_MENU
        
        elif query.data == "payment_subscribe":
            # Ссылка на страницу оплаты на нашем сервере
            from app.core.config import settings as core_settings
            pay_link = f"http://81.177.135.121:8001/pay?user_id={update.effective_user.id}"

            await query.edit_message_text(
                "💳 Оформление подписки\n\n"
                "Нажмите кнопку ниже для перехода к оплате:\n\n"
                "После успешной оплаты ваша подписка будет активирована автоматически.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Перейти к оплате", url=pay_link)],
                    [InlineKeyboardButton("⬅️ Назад", callback_data="payment_back")]
                ])
            )
        
        elif query.data == "payment_auto_renewal":
            # Включаем автопродление
            user = update.effective_user
            try:
                with get_db_session() as db:
                    db_user = db.query(User).filter(User.telegram_id == user.id).first()
                    if db_user and db_user.subscription:
                        db_user.subscription.auto_renewal = True
                        # commit происходит автоматически
                        
                        await query.edit_message_text(
                            "✅ Автопродление подключено!\n\n"
                            "Ваша подписка будет автоматически продлеваться каждый месяц.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("⬅️ Назад", callback_data="payment_back")
                            ]])
                        )
            except Exception as e:
                logger.error(f"Ошибка при подключении автопродления: {e}")
                await query.edit_message_text(
                    "❌ Произошла ошибка. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Назад", callback_data="payment_back")
                    ]])
                )
        
        elif query.data == "payment_cancel":
            # Отключаем подписку
            user = update.effective_user
            try:
                with get_db_session() as db:
                    db_user = db.query(User).filter(User.telegram_id == user.id).first()
                    if db_user and db_user.subscription:
                        db_user.subscription.is_active = False
                        db_user.subscription.auto_renewal = False
                        # commit происходит автоматически
                        
                        await query.edit_message_text(
                            "❌ Подписка отключена!\n\n"
                            "Ваша подписка будет активна до конца оплаченного периода.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("⬅️ Назад", callback_data="payment_back")
                            ]])
                        )
            except Exception as e:
                logger.error(f"Ошибка при отключении подписки: {e}")
                await query.edit_message_text(
                    "❌ Произошла ошибка. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Назад", callback_data="payment_back")
                    ]])
                )
    
    async def handle_profile(self, update: Update, context):
        """Обработка просмотра профиля"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        telegram_id = user.id
        
        try:
            with get_db_session() as db:
                db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if not db_user:
                    await query.edit_message_text(
                        "❌ Профиль не найден. Используйте /start для регистрации.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
                        ]])
                    )
                    return MAIN_MENU
                
                # Формируем информацию о профиле
                profile_text = f"👤 Профиль пользователя\n\n"
                profile_text += f"📝 Фамилия и имя: {db_user.full_name or 'Не указано'}\n"
                profile_text += f"🏢 Сфера деятельности: {db_user.activity_field or 'Не указано'}\n"
                profile_text += f"🏭 Компания: {db_user.company or 'Не указано'}\n"
                profile_text += f"👔 Роль в компании: {db_user.role_in_company or 'Не указано'}\n"
                profile_text += f"📱 Контактный номер: {db_user.contact_number or 'Не указано'}\n"
                profile_text += f"🎯 Цель участия: {db_user.participation_purpose or 'Не указано'}\n"
                profile_text += f"📅 Дата регистрации: {db_user.registration_date.strftime('%d.%m.%Y')}\n\n"
                
                # Информация о подписке
                if db_user.has_active_subscription():
                    subscription = db_user.subscription
                    end_date = subscription.end_date.strftime("%d.%m.%Y")
                    days_left = (subscription.end_date - datetime.now(timezone.utc)).days
                    
                    profile_text += f"💳 Статус подписки: ✅ Активна\n"
                    profile_text += f"📅 Действует до: {end_date}\n"
                    profile_text += f"⏰ Осталось дней: {days_left}\n"
                    profile_text += f"🔄 Автопродление: {'Включено' if subscription.auto_renewal else 'Отключено'}"
                else:
                    profile_text += f"💳 Статус подписки: ❌ Нет подписки"
                
                keyboard = [
                    [InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")]
                ]
                
                await query.edit_message_text(
                    profile_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except Exception as e:
            logger.error(f"Ошибка при получении профиля: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка при получении профиля. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
                ]])
            )
    
    async def handle_update_profile(self, update: Update, context):
        """Обработка обновления профиля"""
        query = update.callback_query
        await query.answer()
        
        # Начинаем заполнение анкеты заново
        user = update.effective_user
        user_data_temp[user.id] = {
            'step': 0,
            'data': {}
        }
        
        # Удаляем старые кнопки и отправляем новое сообщение
        await query.edit_message_text(
            "📝 Обновление данных профиля\n\nВведите фамилию и имя (через пробел):"
        )
        return FILLING_QUESTIONNAIRE
    
    async def handle_back_to_main(self, update: Update, context):
        """Возврат в главное меню"""
        query = update.callback_query
        await query.answer()
        
        await self.show_main_menu(update, context)
        return MAIN_MENU
    
    async def cancel_command(self, update: Update, context: CallbackContext) -> int:
        """Отмена регистрации"""
        user = update.effective_user
        if user.id in user_data_temp:
            del user_data_temp[user.id]
        
        await update.message.reply_text(
            "❌ Регистрация отменена. Используйте /start для начала заново."
        )
        return ConversationHandler.END

    async def request_consent(self, update: Update, context: CallbackContext) -> int:
        """Запрос согласия на обработку данных"""
        user = update.effective_user
        user_id = user.id
        
        if user_id not in user_data_temp:
            await update.message.reply_text("Произошла ошибка. Начните заново с команды /start")
            return ConversationHandler.END
        
        user_data = user_data_temp[user_id]
        if user_data['step'] < 6:
            await update.message.reply_text("Пожалуйста, сначала заполните все поля анкеты.")
            return FILLING_QUESTIONNAIRE
        
        # Показываем согласие
        consent_text = (
            "📋 Согласие на обработку персональных данных\n\n"
            "Я даю согласие на обработку моих персональных данных в соответствии с "
            "Федеральным законом от 27.07.2006 N 152-ФЗ «О персональных данных».\n\n"
            f"📋 Ознакомьтесь с нашей политикой конфиденциальности:\n"
            f"{settings.PRIVACY_POLICY_URL}\n\n"
            "Согласны ли вы с условиями?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Согласен", callback_data="consent_yes")],
            [InlineKeyboardButton("❌ Не согласен", callback_data="consent_no")]
        ]
        
        await update.message.reply_text(
            consent_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return WAITING_FOR_CONSENT

    async def handle_chat_member_update(self, update: Update, context: CallbackContext) -> None:
        """Обработчик изменений участников чата"""
        try:
            if update.chat_member:
                chat_member = update.chat_member
                chat = chat_member.chat
                user = chat_member.new_chat_member.user
                old_status = chat_member.old_chat_member.status if chat_member.old_chat_member else None
                new_status = chat_member.new_chat_member.status
                
                logger.info(f"Chat member update: {user.username or user.first_name} in {chat.title}")
                logger.info(f"Status change: {old_status} -> {new_status}")
                logger.info(f"Chat type: {chat.type}, Chat ID: {chat.id}")
                
                # Обрабатываем вступление в канал
                if new_status in ['member', 'administrator', 'owner'] and old_status not in ['member', 'administrator', 'owner']:
                    await self.handle_user_joined_channel(chat, user, new_status)
                
                # Обрабатываем выход из канала
                elif old_status in ['member', 'administrator', 'owner'] and new_status not in ['member', 'administrator', 'owner']:
                    await self.handle_user_left_channel(chat, user, old_status)
                    
        except Exception as e:
            logger.error(f"Error in handle_chat_member_update: {e}")

    async def handle_new_chat_members(self, update: Update, context: CallbackContext) -> None:
        """Обработчик новых участников чата"""
        try:
            if update.message and update.message.new_chat_members:
                chat = update.message.chat
                for new_member in update.message.new_chat_members:
                    if not new_member.is_bot:
                        logger.info(f"New member joined via message: {new_member.username or new_member.first_name} in {chat.title}")
                        await self.handle_user_joined_channel(chat, new_member, 'member')
        except Exception as e:
            logger.error(f"Error in handle_new_chat_members: {e}")

    async def handle_left_chat_member(self, update: Update, context: CallbackContext) -> None:
        """Обработчик выхода участника из чата"""
        try:
            if update.message and update.message.left_chat_member:
                chat = update.message.chat
                left_member = update.message.left_chat_member
                if not left_member.is_bot:
                    logger.info(f"Member left via message: {left_member.username or left_member.first_name} from {chat.title}")
                    await self.handle_user_left_channel(chat, left_member, 'left')
        except Exception as e:
            logger.error(f"Error in handle_left_chat_member: {e}")

    async def handle_all_messages(self, update: Update, context: CallbackContext) -> None:
        """Обработчик всех сообщений для отладки"""
        try:
            if update.message:
                chat = update.message.chat
                user = update.message.from_user
                if chat.type == 'channel':
                    logger.info(f"Channel message: {user.username or user.first_name} in {chat.title}")
        except Exception as e:
            logger.error(f"Error in handle_all_messages: {e}")

    async def handle_user_joined_channel(self, chat, user, status: str) -> None:
        """Обработка вступления пользователя в канал"""
        try:
            from app.models.models import ChannelMembership
            from app.core.database import get_db
            from app.core.config import settings
            
            # Проверяем, что это наш бесплатный канал
            if str(chat.id) == settings.FREE_CHANNEL_ID.replace('@', '') or chat.username == settings.FREE_CHANNEL_ID.replace('@', ''):
                logger.info(f"User {user.username or user.first_name} joined FREE channel: {chat.title}")
                
                db = next(get_db())
                
                # Создаем или обновляем запись о членстве
                membership = db.query(ChannelMembership).filter(
                    ChannelMembership.user_id == user.id,
                    ChannelMembership.channel_type == 'free'
                ).first()
                
                if membership:
                    # Обновляем существующую запись
                    membership.is_current = True
                    membership.joined_at = datetime.now(timezone.utc)
                    membership.status = status
                    membership.updated_at = datetime.now(timezone.utc)
                else:
                    # Создаем новую запись
                    membership = ChannelMembership(
                        user_id=user.id,
                        username=user.username,
                        full_name=user.full_name,
                        channel_type='free',
                        channel_id=str(chat.id),
                        channel_title=chat.title,
                        status=status,
                        joined_at=datetime.now(timezone.utc),
                        is_current=True
                    )
                    db.add(membership)
                
                db.commit()
                logger.info(f"Channel membership recorded for user {user.id} in FREE channel")
                
        except Exception as e:
            logger.error(f"Error handling user joined channel: {e}")

    async def handle_user_left_channel(self, chat, user, old_status: str) -> None:
        """Обработка выхода пользователя из канала"""
        try:
            from app.models.models import ChannelMembership
            from app.core.database import get_db
            from app.core.config import settings
            
            # Проверяем, что это наш бесплатный канал
            if str(chat.id) == settings.FREE_CHANNEL_ID.replace('@', '') or chat.username == settings.FREE_CHANNEL_ID.replace('@', ''):
                logger.info(f"User {user.username or user.first_name} left FREE channel: {chat.title}")
                
                db = next(get_db())
                
                # Обновляем запись о членстве
                membership = db.query(ChannelMembership).filter(
                    ChannelMembership.user_id == user.id,
                    ChannelMembership.channel_type == 'free'
                ).first()
                
                if membership:
                    membership.is_current = False
                    membership.left_at = datetime.now(timezone.utc)
                    membership.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info(f"Channel membership updated for user {user.id} - left FREE channel")
                
        except Exception as e:
            logger.error(f"Error handling user left channel: {e}")
    
    async def handle_chat_join_request(self, update: Update, context: CallbackContext) -> None:
        """Обработчик запросов на вступление в канал (channels with Join Request)."""
        try:
            join_req = update.chat_join_request
            if not join_req:
                return
            chat = join_req.chat
            user = join_req.from_user
            
            # Принимаем запрос на вступление (если требуется автоприем)
            try:
                await context.bot.approve_chat_join_request(chat.id, user.id)
                logger.info(f"Approved join request for {user.id} to {chat.title}")
            except Exception as e:
                logger.warning(f"Approve join request failed: {e}")
            
            # Записываем вступление в ChannelMembership
            from app.models.models import ChannelMembership
            from app.core.database import get_db
            
            db = next(get_db())
            membership = db.query(ChannelMembership).filter(
                ChannelMembership.user_id == user.id,
                ChannelMembership.channel_type == 'free'
            ).first()
            now_utc = datetime.now(timezone.utc)
            if membership:
                membership.is_current = True
                membership.joined_at = now_utc
                membership.updated_at = now_utc
                membership.status = 'member'
            else:
                db.add(ChannelMembership(
                    user_id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                    channel_type='free',
                    channel_id=str(chat.id),
                    channel_title=chat.title,
                    status='member',
                    joined_at=now_utc,
                    is_current=True
                ))
            db.commit()
            logger.info(f"Join request recorded in DB for user {user.id} in FREE channel")
        except Exception as e:
            logger.error(f"Error in handle_chat_join_request: {e}")
    
    def run(self):
        """Запуск бота"""
        self.application.run_polling()


_bot_singleton = None

def create_bot():
    """Фабрика для создания бота (синглтон)"""
    global _bot_singleton
    if _bot_singleton is not None:
        return _bot_singleton
    if not settings.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN не установлен в переменных окружения")
    _bot_singleton = TelegramBot(settings.TELEGRAM_TOKEN)
    return _bot_singleton

    
def reset_bot_singleton():
    """Сброс синглтона бота (для корректного перезапуска после ошибок)."""
    global _bot_singleton
    _bot_singleton = None
