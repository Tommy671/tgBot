"""
Конфигурация приложения
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot
    TELEGRAM_TOKEN: str
    
    # Database
    DATABASE_URL: str = "sqlite:///./bot_database.db"
    
    # FastAPI
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Bot Configuration
    PRIVATE_CHAT_LINK: str = "https://t.me/private_chat_link"
    PAYMENT_LINK: str = "https://payment.example.com"
    SUBSCRIPTION_PRICE: int = 999
    SUBSCRIPTION_DURATION_DAYS: int = 30
    
    # Performance settings
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_RECYCLE: int = 3600
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Cache settings
    CACHE_TTL: int = 300  # 5 minutes
    ENABLE_CACHE: bool = True
    
    @validator('TELEGRAM_TOKEN')
    def validate_telegram_token(cls, v):
        if not v or v == "your_telegram_bot_token_here":
            raise ValueError("TELEGRAM_TOKEN должен быть установлен")
        return v
    
    @validator('SECRET_KEY')
    def validate_secret_key(cls, v):
        if not v or len(v) < 32:
            raise ValueError("SECRET_KEY должен быть не менее 32 символов")
        return v
    
    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("DATABASE_URL должен быть установлен")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Создаем экземпляр настроек
settings = Settings()


class Config:
    """Конфигурация для обратной совместимости"""
    TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN
    SECRET_KEY = settings.SECRET_KEY
    DATABASE_URL = settings.DATABASE_URL
    HOST = settings.HOST
    PORT = settings.PORT
    ALGORITHM = settings.ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    PRIVATE_CHAT_LINK = settings.PRIVATE_CHAT_LINK
    PAYMENT_LINK = settings.PAYMENT_LINK
    SUBSCRIPTION_PRICE = settings.SUBSCRIPTION_PRICE
    SUBSCRIPTION_DURATION_DAYS = settings.SUBSCRIPTION_DURATION_DAYS
