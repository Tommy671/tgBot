"""
Менеджер подписок для автоматического управления
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.models import User, Subscription
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """Менеджер для автоматического управления подписками"""
    
    def __init__(self):
        self.notification_intervals = [7, 3, 1]  # Дни до истечения для уведомлений
        self._bot = None
    
    @property
    def bot(self):
        """Получение экземпляра бота"""
        if self._bot is None:
            from app.bot.bot import create_bot
            self._bot = create_bot()
        return self._bot
    
    async def check_expiring_subscriptions(self, db: Session):
        """Проверка истекающих подписок и отправка уведомлений"""
        try:
            now = datetime.now(timezone.utc)
            
            for days in self.notification_intervals:
                # Находим подписки, которые истекают через указанное количество дней
                target_date = now + timedelta(days=days)
                start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
                
                expiring_subscriptions = db.query(Subscription).join(User).filter(
                    Subscription.is_active == True,
                    Subscription.end_date >= start_date,
                    Subscription.end_date < end_date
                ).all()
                
                for subscription in expiring_subscriptions:
                    await self.send_expiration_notification(subscription, days)
            
            logger.info(f"Checked expiring subscriptions for {len(self.notification_intervals)} intervals")
            
        except Exception as e:
            logger.error(f"Error checking expiring subscriptions: {e}")
    
    async def send_expiration_notification(self, subscription: Subscription, days_left: int):
        """Отправка уведомления об истечении подписки"""
        try:
            user = subscription.user
            
            if days_left == 1:
                message = (
                    "⚠️ **ВНИМАНИЕ!** ⚠️\n\n"
                    "Ваша подписка истекает **ЗАВТРА**!\n\n"
                    "Чтобы продолжить доступ к платному контенту, "
                    "необходимо продлить подписку.\n\n"
                    "💰 Стоимость: {price} руб.\n"
                    "Оплатите через раздел Настройки → Оплата в боте.\n\n"
                    "Подписка активируется автоматически после оплаты."
                ).format(
                    price=settings.SUBSCRIPTION_PRICE
                )
            elif days_left == 3:
                message = (
                    "📅 **Напоминание о подписке**\n\n"
                    "Ваша подписка истекает через **{days} дня**.\n\n"
                    "💰 Стоимость: {price} руб.\n"
                    "Оплатите через раздел Настройки → Оплата в боте.\n\n"
                    "Не забудьте продлить подписку, чтобы сохранить доступ!"
                ).format(
                    days=days_left,
                    price=settings.SUBSCRIPTION_PRICE
                )
            else:
                message = (
                    "📅 **Напоминание о подписке**\n\n"
                    "Ваша подписка истекает через **{days} дней**.\n\n"
                    "💰 Стоимость: {price} руб.\n"
                    "Оплатите через раздел Настройки → Оплата в боте.\n\n"
                    "Рекомендуем продлить подписку заранее!"
                ).format(
                    days=days_left,
                    price=settings.SUBSCRIPTION_PRICE
                )
            
            await self.bot.application.bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Sent expiration notification to user {user.telegram_id} for {days_left} days")
            
        except Exception as e:
            logger.error(f"Error sending expiration notification to user {subscription.user_id}: {e}")
    
    async def remove_expired_subscriptions(self, db: Session):
        """Удаление пользователей с истекшими подписками из платного канала"""
        try:
            now = datetime.now(timezone.utc)
            
            # Находим пользователей с истекшими подписками
            expired_subscriptions = db.query(Subscription).join(User).filter(
                Subscription.is_active == True,
                Subscription.end_date < now
            ).all()
            
            removed_count = 0
            
            for subscription in expired_subscriptions:
                try:
                    user = subscription.user
                    
                    # Убираем пользователя из платного канала
                    await self.remove_user_from_paid_channel(user.telegram_id)
                    
                    # Обновляем статус подписки
                    subscription.is_active = False
                    
                    # Обновляем статус пользователя в канале
                    user.is_in_paid_channel = False
                    user.paid_channel_join_date = None
                    
                    # Отправляем уведомление об удалении
                    await self.send_removal_notification(user)
                    
                    removed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error removing user {subscription.user_id} from paid channel: {e}")
                    continue
            
            if removed_count > 0:
                db.commit()
                logger.info(f"Removed {removed_count} users with expired subscriptions from paid channel")
            
        except Exception as e:
            logger.error(f"Error removing expired subscriptions: {e}")
            db.rollback()
    
    async def remove_user_from_paid_channel(self, telegram_id: int):
        """Удаление пользователя из платного канала"""
        try:
            # Получаем ID платного канала из настроек
            paid_channel_id = settings.PAID_CHANNEL_ID
            
            # Удаляем пользователя из канала
            await self.bot.application.bot.ban_chat_member(
                chat_id=paid_channel_id,
                user_id=telegram_id
            )
            
            logger.info(f"User {telegram_id} removed from paid channel {paid_channel_id}")
            
        except Exception as e:
            logger.error(f"Error removing user {telegram_id} from paid channel: {e}")
            raise
    
    async def send_removal_notification(self, user: User):
        """Отправка уведомления об удалении из платного канала"""
        try:
            message = (
                "❌ **Доступ к платному контенту закрыт**\n\n"
                "Ваша подписка истекла, и вы были удалены из платного канала.\n\n"
                "Для восстановления доступа:\n"
                "1. 💰 Оплатить подписку (Настройки → Оплата в боте)\n"
                "2. ✅ Подписка активируется автоматически\n\n"
                "Спасибо за использование нашего сервиса!"
            )
            
            await self.bot.application.bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Sent removal notification to user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error sending removal notification to user {user.telegram_id}: {e}")
    
    async def add_user_to_paid_channel(self, user: User, db: Session):
        """Добавление пользователя в платный канал при покупке подписки"""
        try:
            paid_channel_id = settings.PAID_CHANNEL_ID
            
            # Приглашаем пользователя в платный канал
            invite_link = await self.bot.application.bot.create_chat_invite_link(
                chat_id=paid_channel_id,
                expire_date=datetime.now(timezone.utc) + timedelta(hours=24),
                creates_join_request=False
            )
            
            # Отправляем приглашение пользователю
            message = (
                "🎉 **Добро пожаловать в платный канал!**\n\n"
                "Ваша подписка активирована!\n"
                "🔗 Приглашение: {invite_link}\n\n"
                "Теперь у вас есть доступ к эксклюзивному контенту.\n"
                "Приятного использования!"
            ).format(invite_link=invite_link.invite_link)
            
            await self.bot.application.bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode='Markdown'
            )
            
            # Обновляем статус пользователя
            user.is_in_paid_channel = True
            user.paid_channel_join_date = datetime.now(timezone.utc)
            
            db.commit()
            
            logger.info(f"User {user.telegram_id} added to paid channel {paid_channel_id}")
            
        except Exception as e:
            logger.error(f"Error adding user {user.telegram_id} to paid channel: {e}")
            db.rollback()
            raise


# Создаем глобальный экземпляр менеджера
subscription_manager = SubscriptionManager()
