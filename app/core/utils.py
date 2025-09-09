"""
Утилиты для оптимизации производительности
"""
import time
from typing import Any, Optional, Dict, Callable
from functools import wraps
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    """Простое in-memory кэширование"""
    
    def __init__(self, ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        if key in self.cache:
            item = self.cache[key]
            if time.time() - item['timestamp'] < self.ttl:
                return item['value']
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Установка значения в кэш"""
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
    
    def delete(self, key: str) -> None:
        """Удаление значения из кэша"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self) -> None:
        """Очистка всего кэша"""
        self.cache.clear()
    
    def cleanup_expired(self) -> None:
        """Очистка истекших записей"""
        current_time = time.time()
        expired_keys = [
            key for key, item in self.cache.items()
            if current_time - item['timestamp'] >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]


class RateLimiter:
    """Rate limiting для API запросов"""
    
    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_requests: Dict[str, list] = defaultdict(list)
        self.hour_requests: Dict[str, list] = defaultdict(list)
    
    def is_allowed(self, identifier: str) -> bool:
        """Проверка, разрешен ли запрос"""
        current_time = time.time()
        
        # Очистка старых записей
        self._cleanup_old_requests(identifier, current_time)
        
        # Проверка лимита в минуту
        if len(self.minute_requests[identifier]) >= self.requests_per_minute:
            return False
        
        # Проверка лимита в час
        if len(self.hour_requests[identifier]) >= self.requests_per_hour:
            return False
        
        # Добавление текущего запроса
        self.minute_requests[identifier].append(current_time)
        self.hour_requests[identifier].append(current_time)
        
        return True
    
    def _cleanup_old_requests(self, identifier: str, current_time: float) -> None:
        """Очистка старых запросов"""
        # Очистка запросов старше 1 минуты
        self.minute_requests[identifier] = [
            req_time for req_time in self.minute_requests[identifier]
            if current_time - req_time < 60
        ]
        
        # Очистка запросов старше 1 часа
        self.hour_requests[identifier] = [
            req_time for req_time in self.hour_requests[identifier]
            if current_time - req_time < 3600
        ]


def rate_limit(requests_per_minute: int = 60, requests_per_hour: int = 1000):
    """Декоратор для rate limiting"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Получение идентификатора (например, IP адрес или user_id)
            identifier = "default"  # В реальном приложении здесь должен быть IP или user_id
            
            if not rate_limiter.is_allowed(identifier):
                logger.warning(f"Rate limit exceeded for {identifier}")
                raise Exception("Rate limit exceeded. Please try again later.")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Декоратор для повторных попыток при ошибках"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {e}")
            
            raise last_exception
        return wrapper
    return decorator


def measure_performance(func: Callable) -> Callable:
    """Декоратор для измерения производительности функций"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.4f} seconds: {e}")
            raise
    return wrapper


# Глобальные экземпляры
cache = SimpleCache()
rate_limiter = RateLimiter()


