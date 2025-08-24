"""
Telegram Bot Module
"""
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db_session
from app.core.utils import cache_result, rate_limit, retry_on_failure, measure_performance
from app.models.models import User, Subscription

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


class TelegramBot:
    """Telegram Bot Class"""
    
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        # Обработчик ошибок
        self.application.add_error_handler(Exception, self.error_handler)
        
        # Основной ConversationHandler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start_command)],
            per_message=False,
            states={
                FILLING_QUESTIONNAIRE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_questionnaire)
                ],
                WAITING_FOR_CONSENT: [
                    CallbackQueryHandler(self.handle_consent, pattern='^consent_')
                ],
                MAIN_MENU: [
                    CallbackQueryHandler(self.handle_main_menu, pattern='^main_'),
                    CallbackQueryHandler(self.handle_private_chat, pattern='^private_chat'),
                    CallbackQueryHandler(self.handle_settings, pattern='^settings'),
                    CallbackQueryHandler(self.handle_profile, pattern='^profile'),
                    CallbackQueryHandler(self.handle_update_profile, pattern='^update_profile'),
                    CallbackQueryHandler(self.handle_back_to_main, pattern='^main_back')
                ],
                SETTINGS_MENU: [
                    CallbackQueryHandler(self.handle_settings_menu, pattern='^settings_'),
                    CallbackQueryHandler(self.handle_back_to_main, pattern='^main_back')
                ],
                PAYMENT_MENU: [
                    CallbackQueryHandler(self.handle_payment_menu, pattern='^payment_'),
                    CallbackQueryHandler(self.handle_back_to_main, pattern='^main_back')
                ]
            },
            fallbacks=[CommandHandler('start', self.start_command)]
        )
        
        self.application.add_handler(conv_handler)
        
        # Обработчики команд
        self.application.add_handler(CommandHandler('profile', self.profile_command))
        self.application.add_handler(CommandHandler('settings', self.settings_command))
    
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
            "Введите ваше ФИО (фамилия и имя через пробел):",
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
        
        # Валидация ФИО
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
            "Введите сферу деятельности:",
            "Введите название компании:",
            "Введите вашу роль в компании:",
            "Введите контактный номер телефона (+7XXXXXXXXX или 8XXXXXXXXX):",
            "Введите цель участия:"
        ]
        
        if user_data['step'] < len(questions):
            await update.message.reply_text(questions[user_data['step']])
        else:
            # Анкета заполнена, запрашиваем согласие
            await self.request_consent(update, context)
            return WAITING_FOR_CONSENT
    
    async def request_consent(self, update: Update, context):
        """Запрос согласия на обработку персональных данных"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
                InlineKeyboardButton("❌ Не согласен", callback_data="consent_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Анкета заполнена! Теперь необходимо дать согласие на обработку персональных данных.\n\n"
            "Нажимая 'Согласен', вы подтверждаете, что даете согласие на обработку ваших персональных данных.",
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
    
    async def handle_main_menu(self, update: Update, context):
        """Обработка выбора в главном меню"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "main_back":
            await self.show_main_menu(update, context)
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
                    await query.edit_message_text(
                        f"✅ У вас есть активная подписка!\n\n"
                        f"🔗 Ссылка на приватный чат: {settings.PRIVATE_CHAT_LINK}\n\n"
                        f"Используйте эту ссылку для входа в закрытый чат.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
                        ]])
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
            [InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ Настройки\n\nВыберите действие:",
            reply_markup=reply_markup
        )
        return SETTINGS_MENU
    
    async def handle_settings_menu(self, update: Update, context):
        """Обработка выбора в меню настроек"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "settings_refill":
            # Начинаем заполнение анкеты заново
            user = update.effective_user
            user_data_temp[user.id] = {
                'step': 0,
                'data': {}
            }
            
            await query.edit_message_text(
                "📝 Заполнение анкеты заново\n\nВведите ваше ФИО (фамилия и имя через пробел):"
            )
            return FILLING_QUESTIONNAIRE
        
        elif query.data == "settings_payment":
            await self.show_payment_menu(update, context)
            return PAYMENT_MENU
    
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
                        [InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")]
                    ]
                    
                    await query.edit_message_text(
                        f"💳 Управление подпиской\n\n"
                        f"✅ У вас активная подписка\n"
                        f"📅 Действует до: {end_date}\n"
                        f"💰 Стоимость: {settings.SUBSCRIPTION_PRICE} ₽/месяц\n\n"
                        f"Выберите действие:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    # У пользователя нет подписки
                    keyboard = [
                        [InlineKeyboardButton("💳 Оформить подписку", callback_data="payment_subscribe")],
                        [InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")]
                    ]
                    
                    await query.edit_message_text(
                        f"💳 Оформление подписки\n\n"
                        f"💰 Стоимость: {settings.SUBSCRIPTION_PRICE} ₽/месяц\n"
                        f"📅 Срок действия: {settings.SUBSCRIPTION_DURATION_DAYS} дней\n\n"
                        f"Выберите действие:",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
        except Exception as e:
            logger.error(f"Ошибка при показе меню оплаты: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="back_main")
                ]])
            )
    
    @retry_on_failure(max_retries=3, delay=1.0)
    async def handle_payment_menu(self, update: Update, context):
        """Обработка выбора в меню оплаты"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "payment_subscribe":
            # Здесь должна быть интеграция с платежной системой
            await query.edit_message_text(
                "💳 Оформление подписки\n\n"
                "🔗 Ссылка для оплаты: https://example.com/payment\n\n"
                "После успешной оплаты ваша подписка будет активирована автоматически.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
                ]])
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
                                InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
                            ]])
                        )
            except Exception as e:
                logger.error(f"Ошибка при подключении автопродления: {e}")
                await query.edit_message_text(
                    "❌ Произошла ошибка. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
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
                                InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
                            ]])
                        )
            except Exception as e:
                logger.error(f"Ошибка при отключении подписки: {e}")
                await query.edit_message_text(
                    "❌ Произошла ошибка. Попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Вернуться в главное меню", callback_data="main_back")
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
                profile_text += f"📝 ФИО: {db_user.full_name or 'Не указано'}\n"
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
        
        await query.edit_message_text(
            "📝 Обновление данных профиля\n\nВведите ваше ФИО (фамилия и имя через пробел):"
        )
        return FILLING_QUESTIONNAIRE
    
    async def handle_back_to_main(self, update: Update, context):
        """Возврат в главное меню"""
        query = update.callback_query
        await query.answer()
        
        await self.show_main_menu(update, context)
        return MAIN_MENU
    
    def run(self):
        """Запуск бота"""
        self.application.run_polling()


def create_bot():
    """Фабрика для создания бота"""
    if not settings.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN не установлен в переменных окружения")
    
    return TelegramBot(settings.TELEGRAM_TOKEN)
