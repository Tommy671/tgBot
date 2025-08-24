"""
FastAPI Admin Application
"""
from fastapi import FastAPI, Request, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os
import logging

from app.core.config import settings
from app.core.database import get_db, create_tables, check_database_connection
from app.core.utils import cache_result, rate_limit, measure_performance, cleanup_cache
from app.core.auth import get_current_admin, get_current_admin_from_cookies, create_default_admin, authenticate_admin, create_access_token
from app.models.models import User, Subscription, AdminUser
from app.schemas.schemas import UserExport, Subscription as SubscriptionSchema, Token, LoginRequest

# Настройка логирования
logging.basicConfig(
    format=settings.LOG_FORMAT,
    level=getattr(logging, settings.LOG_LEVEL.upper())
)
logger = logging.getLogger(__name__)

# Создаем FastAPI приложение
app = FastAPI(
    title="Telegram CRM Admin",
    description="Админ панель для управления Telegram ботом",
    version="1.0.0"
)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене ограничить конкретными доменами
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Создаем таблицы при запуске
@app.on_event("startup")
async def startup_event():
    try:
        create_tables()
        # Проверяем соединение с БД
        if not check_database_connection():
            logger.error("Failed to connect to database during startup")
            raise Exception("Database connection failed")
        
        # Создаем админа по умолчанию
        db = next(get_db())
        try:
            create_default_admin(db)
            logger.info("Default admin user created successfully")
        finally:
            db.close()
        
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

# Периодическая очистка кэша
@app.on_event("startup")
async def start_cache_cleanup():
    import asyncio
    async def cleanup_loop():
        while True:
            await asyncio.sleep(300)  # Каждые 5 минут
            cleanup_cache()
    
    asyncio.create_task(cleanup_loop())


# Обработчик ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 403:
        # Перенаправляем на страницу входа при ошибке доступа
        return RedirectResponse(url="/login", status_code=302)
    elif exc.status_code == 404:
        # Обработка 404 ошибок
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    else:
        # Для других ошибок возвращаем JSON ответ
        return {"error": exc.detail, "status_code": exc.status_code}


# Health check endpoint
@app.get("/health")
async def health_check():
    """Проверка состояния приложения"""
    try:
        db_status = check_database_connection()
        return {
            "status": "healthy" if db_status else "unhealthy",
            "timestamp": datetime.now(timezone.utc),
            "database": "connected" if db_status else "disconnected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc),
            "error": str(e)
        }

# Тестовый endpoint для проверки API
@app.get("/api/test")
async def test_api():
    """Тестовый endpoint для проверки работы API"""
    try:
        return {"message": "API работает", "timestamp": datetime.now(timezone.utc)}
    except Exception as e:
        logger.error(f"Test API error: {e}")
        return {"error": str(e)}

# Тестовый endpoint для проверки данных без аутентификации
@app.get("/api/test-data")
async def test_data_api(db: Session = Depends(get_db)):
    """Тестовый endpoint для проверки получения данных из БД"""
    try:
        total_users = db.query(User).count()
        return {
            "message": "Данные получены успешно",
            "total_users": total_users,
            "timestamp": datetime.now(timezone.utc)
        }
    except Exception as e:
        logger.error(f"Test data API error: {e}")
        return {"error": str(e)}


# Аутентификация
@app.post("/api/login", response_model=Token)
@rate_limit(requests_per_minute=5, requests_per_hour=50)
def login(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Аутентификация администратора"""
    try:
        admin = authenticate_admin(db, login_data.username, login_data.password)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": admin.username}, expires_delta=access_token_expires
        )
        
        # Устанавливаем cookie с токеном
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,  # False для HTTP, True для HTTPS
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/"  # Добавляем path для всех путей
        )
        
        logger.debug(f"Cookie set: access_token={access_token[:20]}..., max_age={settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}, path=/")
        
        logger.info(f"Admin {admin.username} logged in successfully")
        logger.debug(f"Token created: {access_token[:20]}...")
        logger.debug(f"Cookie settings: httponly=True, secure=False, samesite=lax, path=/")
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


# Страницы
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def statistics_page(request: Request, db: Session = Depends(get_db)):
    try:
        current_admin = get_current_admin_from_cookies(request, db)
        logger.info(f"Admin {current_admin.username} accessed dashboard")
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except HTTPException as e:
        logger.debug(f"Unauthorized access to dashboard: {e}")
        return RedirectResponse(url="/login", status_code=302)
    except Exception as e:
        logger.error(f"Error accessing dashboard: {e}")
        return RedirectResponse(url="/login", status_code=302)


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: Session = Depends(get_db)):
    try:
        current_admin = get_current_admin_from_cookies(request, db)
        return templates.TemplateResponse("users.html", {"request": request})
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)


@app.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail_page(
    request: Request, 
    user_id: int, 
    db: Session = Depends(get_db)
):
    try:
        current_admin = get_current_admin_from_cookies(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return templates.TemplateResponse(
        "user_detail.html", 
        {
            "request": request, 
            "user": user,
            "now": datetime.now(timezone.utc),
            "timedelta": timedelta,
            "moment": datetime.now
        }
    )


@app.get("/subscriptions", response_class=HTMLResponse)
async def subscriptions_page(request: Request, db: Session = Depends(get_db)):
    try:
        current_admin = get_current_admin_from_cookies(request, db)
        return templates.TemplateResponse(
            "subscriptions.html", 
            {
                "request": request,
                "now": datetime.now(timezone.utc),
                "timedelta": timedelta
            }
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)


# API endpoints
@app.get("/api/dashboard")
# @cache_result(ttl=60, key_prefix="dashboard")
# @measure_performance
def get_dashboard_data(
    request: Request,
    db: Session = Depends(get_db)
):
    """Получение данных для дашборда"""
    try:
        # Временно убираем аутентификацию для отладки
        # current_admin = get_current_admin_from_cookies(request, db)
        
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        total_subscriptions = db.query(Subscription).count()
        active_subscriptions = db.query(Subscription).filter(Subscription.is_active == True).count()
        
        # Пользователи за последние 7 дней
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        new_users_week = db.query(User).filter(User.registration_date >= week_ago).count()
        
        # Подписки, истекающие в ближайшие 7 дней
        week_later = datetime.now(timezone.utc) + timedelta(days=7)
        expiring_subscriptions = db.query(Subscription).filter(
            Subscription.end_date <= week_later,
            Subscription.is_active == True
        ).count()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "new_users_week": new_users_week,
            "expiring_subscriptions": expiring_subscriptions
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении данных дашборда"
        )


@app.get("/api/users")
# @cache_result(ttl=30, key_prefix="users_list")
# @measure_performance
def get_users(
    skip: int = 0,
    limit: int = 20,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Получение списка пользователей"""
    try:
        # Временно убираем аутентификацию для отладки
        # current_admin = get_current_admin_from_cookies(request, db)
        
        # Валидация параметров
        if skip < 0:
            skip = 0
        if limit < 1 or limit > 100:
            limit = 20
        
        query = db.query(User)
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        
        # Преобразуем в схему для экспорта
        user_exports = []
        for user in users:
            user_export = UserExport(
                id=user.id,
                telegram_id=user.telegram_id,
                username=user.username,
                full_name=user.full_name,
                activity_field=user.activity_field,
                company=user.company,
                role_in_company=user.role_in_company,
                contact_number=user.contact_number,
                participation_purpose=user.participation_purpose,
                registration_date=user.registration_date,
                subscription_status=user.get_subscription_status()
            )
            user_exports.append(user_export)
        
        return {
            "users": user_exports,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка пользователей"
        )


@app.get("/api/subscriptions")
@cache_result(ttl=30, key_prefix="subscriptions_list")
@measure_performance
async def get_subscriptions(
    skip: int = 0,
    limit: int = 20,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Получение списка подписок"""
    try:
        current_admin = get_current_admin_from_cookies(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        # Валидация параметров
        if skip < 0:
            skip = 0
        if limit < 1 or limit > 100:
            limit = 20
        
        query = db.query(Subscription).join(User)
        total = query.count()
        subscriptions = query.offset(skip).limit(limit).all()
        
        subscription_schemas = []
        for subscription in subscriptions:
            subscription_schema = SubscriptionSchema(
                id=subscription.id,
                user_id=subscription.user_id,
                start_date=subscription.start_date,
                end_date=subscription.end_date,
                is_active=subscription.is_active,
                auto_renewal=subscription.auto_renewal,
                payment_amount=subscription.payment_amount
            )
            subscription_schemas.append(subscription_schema)
        
        return {
            "subscriptions": subscription_schemas,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error getting subscriptions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка подписок"
        )


@app.post("/api/subscriptions")
@rate_limit(requests_per_minute=10, requests_per_hour=100)
@measure_performance
async def create_subscription(
    user_id: int,
    days: int = 30,
    amount: int = 999,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Создание новой подписки"""
    try:
        current_admin = get_current_admin_from_cookies(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        # Валидация входных данных
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Количество дней должно быть от 1 до 365")
        if amount < 0:
            raise HTTPException(status_code=400, detail="Сумма не может быть отрицательной")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Создаем подписку
        subscription = Subscription(
            user_id=user_id,
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=days),
            is_active=True,
            auto_renewal=False,
            payment_amount=amount
        )
        
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        
        logger.info(f"Subscription created for user {user_id} by admin {current_admin.username}")
        return {"message": "Подписка создана", "subscription_id": subscription.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании подписки"
        )


@app.put("/api/subscriptions/{subscription_id}")
@rate_limit(requests_per_minute=10, requests_per_hour=100)
@measure_performance
async def update_subscription(
    subscription_id: int,
    days: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Продление подписки"""
    try:
        current_admin = get_current_admin_from_cookies(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        # Валидация входных данных
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Количество дней должно быть от 1 до 365")
        
        subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        # Продлеваем подписку
        if subscription.end_date > datetime.now(timezone.utc):
            subscription.end_date += timedelta(days=days)
        else:
            subscription.end_date = datetime.now(timezone.utc) + timedelta(days=days)
        
        subscription.is_active = True
        db.commit()
        
        logger.info(f"Subscription {subscription_id} extended by {days} days by admin {current_admin.username}")
        return {"message": "Подписка продлена"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subscription: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при продлении подписки"
        )


@app.delete("/api/subscriptions/{subscription_id}")
@rate_limit(requests_per_minute=10, requests_per_hour=100)
@measure_performance
async def cancel_subscription(
    subscription_id: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Отмена подписки"""
    try:
        current_admin = get_current_admin_from_cookies(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        subscription.is_active = False
        subscription.auto_renewal = False
        db.commit()
        
        logger.info(f"Subscription {subscription_id} cancelled by admin {current_admin.username}")
        return {"message": "Подписка отменена"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при отмене подписки"
        )


@app.delete("/api/users/{user_id}")
@rate_limit(requests_per_minute=10, requests_per_hour=100)
@measure_performance
async def delete_user(
    user_id: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Удаление пользователя из системы и канала"""
    try:
        current_admin = get_current_admin_from_cookies(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Удаляем пользователя из Telegram канала
        try:
            from app.bot.bot import bot
            # Получаем ID канала из переменных окружения или используем дефолтное значение
            channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "@your_channel_username")
            
            # Удаляем пользователя из канала
            await bot.ban_chat_member(
                chat_id=channel_id,
                user_id=user.telegram_id
            )
            logger.info(f"User {user.telegram_id} banned from channel {channel_id}")
        except Exception as e:
            logger.warning(f"Failed to ban user {user.telegram_id} from channel: {e}")
            # Продолжаем удаление из БД даже если не удалось удалить из канала
        
        # Удаляем пользователя из базы данных
        db.delete(user)
        db.commit()
        
        logger.info(f"User {user_id} deleted by admin {current_admin.username}")
        return {"message": "Пользователь успешно удален"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при удалении пользователя"
        )
