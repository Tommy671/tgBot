"""
Pydantic схемы для валидации данных
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    telegram_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    activity_field: Optional[str] = None
    company: Optional[str] = None
    role_in_company: Optional[str] = None
    contact_number: Optional[str] = None
    participation_purpose: Optional[str] = None


class User(UserBase):
    """Схема пользователя с ID"""
    id: int
    registration_date: datetime
    last_activity: datetime
    is_active: bool
    consent_given: bool
    consent_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserExport(UserBase):
    """Схема для экспорта пользователей"""
    id: int
    registration_date: datetime
    subscription_status: str

    class Config:
        from_attributes = True


class SubscriptionBase(BaseModel):
    """Базовая схема подписки"""
    start_date: datetime
    end_date: datetime
    is_active: bool
    auto_renewal: bool
    payment_amount: int


class Subscription(SubscriptionBase):
    """Схема подписки с ID"""
    id: int
    user_id: int

    class Config:
        from_attributes = True


class AdminUserBase(BaseModel):
    """Базовая схема администратора"""
    username: str
    is_active: bool = True


class AdminUser(AdminUserBase):
    """Схема администратора с ID"""
    id: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Схема токена"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Схема данных токена"""
    username: Optional[str] = None


class LoginRequest(BaseModel):
    """Схема запроса авторизации"""
    username: str
    password: str
