"""
Модели базы данных
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from passlib.context import CryptContext
from app.core.database import Base

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, index=True)  # Убираем unique=True
    username = Column(String, unique=True, nullable=True, index=True)  # Добавляем unique=True
    full_name = Column(String, nullable=True)  # ФИО
    activity_field = Column(String, nullable=True)  # Сфера деятельности
    company = Column(String, nullable=True)  # Компания
    role_in_company = Column(String, nullable=True)  # Роль в компании
    contact_number = Column(String, unique=True, nullable=True, index=True)  # Контактный номер
    participation_purpose = Column(Text, nullable=True)  # Цель участия
    registration_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime, nullable=True)
    offer_consent_given = Column(Boolean, default=False)
    offer_consent_date = Column(DateTime, nullable=True)
    
    # Связь с подпиской
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    
    # Связь с платежами
    payments = relationship("Payment", back_populates="user")
    
    # Участие в каналах
    is_in_free_channel = Column(Boolean, default=False)  # Участник бесплатного канала
    is_in_paid_channel = Column(Boolean, default=False)  # Участник платного канала
    free_channel_join_date = Column(DateTime, nullable=True)  # Дата вступления в бесплатный канал
    paid_channel_join_date = Column(DateTime, nullable=True)  # Дата вступления в платный канал
    
    # Связь с участием в каналах
    channel_memberships = relationship("ChannelMembership", back_populates="user")

    def has_active_subscription(self):
        """Проверка наличия активной подписки"""
        if not self.subscription:
            return False
        return self.subscription.check_active()

    def get_subscription_status(self):
        """Получение статуса подписки"""
        if not self.subscription:
            return "Нет подписки"
        if self.subscription.check_active():
            days_left = (self.subscription.end_date - datetime.now(timezone.utc)).days
            return f"Активна ({days_left} дн.)"
        return "Истекла"


class Subscription(Base):
    """Модель подписки"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    start_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    auto_renewal = Column(Boolean, default=False)
    payment_amount = Column(Integer)
    
    # Связь с пользователем
    user = relationship("User", back_populates="subscription")

    def check_active(self):
        """Проверка активности подписки"""
        if not self.is_active or not self.end_date:
            return False
        
        # Убеждаемся что end_date имеет timezone
        end_date = self.end_date
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        return datetime.now(timezone.utc) < end_date

    def days_left(self):
        """Количество дней до истечения подписки"""
        if not self.check_active():
            return 0
        return (self.end_date - datetime.now(timezone.utc)).days


class AdminUser(Base):
    """Модель администратора"""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

    def verify_password(self, password: str) -> bool:
        """Проверка пароля"""
        return pwd_context.verify(password, self.hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Хеширование пароля"""
        return pwd_context.hash(password)


class BotSettings(Base):
    """Модель настроек бота"""
    __tablename__ = "bot_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)  # Ключ настройки
    value = Column(String)  # Значение настройки
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_by = Column(String, nullable=True)  # Кто обновил настройку


class ChannelMembership(Base):
    """Модель участия в каналах"""
    __tablename__ = "channel_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    channel_type = Column(String, index=True)  # 'free' или 'paid'
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    left_at = Column(DateTime, nullable=True)  # Дата выхода (если вышел)
    is_current = Column(Boolean, default=True)  # Текущий участник
    
    # Связь с пользователем
    user = relationship("User", back_populates="channel_memberships")

    def __repr__(self):
        return f"<ChannelMembership(user_id={self.user_id}, channel={self.channel_type}, joined={self.joined_at})>"


class Payment(Base):
    """Модель платежа"""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    payment_id = Column(String, unique=True, index=True)  # ID платежа в Робокассе
    amount = Column(Integer)  # Сумма в копейках
    currency = Column(String, default="RUB")
    status = Column(String, index=True)  # 'pending', 'success', 'failed'
    payment_method = Column(String, nullable=True)  # Способ оплаты
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)  # Время завершения платежа
    
    # Связь с пользователем
    user = relationship("User", back_populates="payments")

    def __repr__(self):
        return f"<Payment(user_id={self.user_id}, amount={self.amount}, status={self.status})>"
