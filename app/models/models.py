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
    
    # Связь с подпиской
    subscription = relationship("Subscription", back_populates="user", uselist=False)

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
        return self.is_active and datetime.now(timezone.utc) < self.end_date

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
