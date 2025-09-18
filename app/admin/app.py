"""
FastAPI Admin Application
"""
from fastapi import FastAPI, Request, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os
import logging
from functools import lru_cache
import httpx

from app.core.config import settings
from app.core.database import get_db, create_tables, check_database_connection
from app.core.utils import rate_limit
from app.core.auth import get_current_admin, get_current_admin_from_cookies, create_default_admin, authenticate_admin, create_access_token
from app.models.models import User, Subscription, AdminUser, BotSettings, Payment, ChannelMembership
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

# HMAC helpers for Robokassa success/fail binding
import hmac
import hashlib
import base64
import time

def _sign_payment_token(message: str) -> str:
    secret = settings.SECRET_KEY.encode("utf-8")
    digest = hmac.new(secret, message.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

def _make_payment_cookie_value(payment_id: str) -> str:
    issued_at = str(int(time.time()))
    payload = f"{payment_id}.{issued_at}"
    sig = _sign_payment_token(payload)
    return f"{payload}.{sig}"

def _parse_and_verify_payment_cookie(cookie_value: str, max_age_seconds: int = 3600) -> Optional[str]:
    try:
        parts = cookie_value.split(".")
        if len(parts) != 3:
            return None
        payment_id, issued_at_str, sig = parts
        # verify signature
        payload = f"{payment_id}.{issued_at_str}"
        expected_sig = _sign_payment_token(payload)
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # verify age
        issued_at = int(issued_at_str)
        now = int(time.time())
        if now - issued_at > max_age_seconds or issued_at > now + 60:
            return None
        return payment_id
    except Exception:
        return None

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
            
            # Инициализируем настройки по умолчанию только если их нет
            if not db.query(BotSettings).filter(BotSettings.key == "subscription_price").first():
                set_setting_value(db, "subscription_price", "999", "system")
            if not db.query(BotSettings.key == "private_chat_link").first():
                set_setting_value(db, "private_chat_link", "https://t.me/private_chat_link", "system")
            if not db.query(BotSettings.key == "payment_link").first():
                set_setting_value(db, "payment_link", "https://payment.example.com", "system")
            logger.info("Bot settings checked/initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing bot settings: {e}")
        
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
            # cleanup_cache был удалён. Ничего не делаем, чтобы избежать ошибок.
            pass
    
    asyncio.create_task(cleanup_loop())


# Обработчик ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 403:
        return RedirectResponse(url="/login", status_code=302)
    elif exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    else:
        return JSONResponse({"error": exc.detail, "status_code": exc.status_code}, status_code=exc.status_code)


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
# Функция для получения количества участников канала
@lru_cache(maxsize=64)
async def _cached_member_count(channel_id: str, bucket: int) -> int:
    # bucket — это секундный слот для кэша
    return await _uncached_member_count(channel_id)

async def _uncached_member_count(channel_id: str) -> int:
    try:
        logger.info(f"Attempting to get member count for channel: {channel_id}")
        from app.bot.bot import create_bot
        bot = create_bot()
        logger.info(f"Bot created successfully, attempting to get chat info...")
        chat = await bot.application.bot.get_chat(channel_id)
        if chat.type == "channel":
            try:
                member_count = await bot.application.bot.get_chat_member_count(channel_id)
                logger.info(f"Channel {channel_id} has {member_count} members (via getChatMemberCount)")
                return member_count
            except Exception as e:
                logger.error(f"Error getting member count via getChatMemberCount: {e}")
                return 0
        elif chat.type in ["group", "supergroup"]:
            if hasattr(chat, 'member_count'):
                return chat.member_count
            return 0
        return 0
    except Exception as e:
        logger.error(f"Error getting channel member count for {channel_id}: {e}")
        return 0

# Кэш на 10 секунд для количества участников
_member_count_cache = {"value": None, "ts": 0}

async def get_channel_member_count(channel_id: str) -> int:
    """Асинхронный запрос к Telegram API без использования объекта бота (избегаем конфликтов event loop)."""
    try:
        import time
        now = int(time.time())
        if _member_count_cache["value"] is not None and now - _member_count_cache["ts"] <= 10:
            return _member_count_cache["value"]
        
        token = settings.TELEGRAM_TOKEN
        api_base = f"https://api.telegram.org/bot{token}"
        
        async with httpx.AsyncClient(timeout=10) as client:
            # Проверим чат для логов (не критично)
            try:
                chat_resp = await client.post(f"{api_base}/getChat", json={"chat_id": channel_id})
                chat_resp.raise_for_status()
                chat_json = chat_resp.json()
                if chat_json.get("ok"):
                    chat = chat_json.get("result", {})
                    logger.info(f"Chat info received: {chat}")
            except Exception as e:
                logger.warning(f"getChat failed: {e}")
            
            # Получим количество участников
            resp = await client.post(f"{api_base}/getChatMemberCount", json={"chat_id": channel_id})
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                count = int(data.get("result", 0))
                _member_count_cache["value"] = count
                _member_count_cache["ts"] = now
                logger.info(f"Channel {channel_id} has {count} members (via httpx)")
                return count
            return 0
    except Exception as e:
        logger.error(f"Error getting channel member count for {channel_id}: {e}")
        return 0

async def get_channel_members_with_dates(channel_id: str) -> list:
    """Получение списка участников канала с датами вступления"""
    try:
        logger.info(f"Getting channel members with dates for {channel_id}")
        
        from app.bot.bot import create_bot
        bot = create_bot()
        
        # Получаем информацию о канале
        chat = await bot.application.bot.get_chat(channel_id)
        logger.info(f"Channel info: {chat.title} ({chat.type})")
        
        # Получаем общее количество участников
        total_members = await bot.application.bot.get_chat_member_count(channel_id)
        logger.info(f"Total members: {total_members}")
        
        # Пытаемся получить список администраторов (это доступно)
        try:
            admins = await bot.application.bot.get_chat_administrators(channel_id)
            logger.info(f"Admins count: {len(admins)}")
            
            # Создаем временные записи для администраторов
            members_data = []
            for admin in admins:
                if not admin.user.is_bot:  # Исключаем ботов
                    # Получаем правильную дату в зависимости от типа администратора
                    join_date = None
                    
                    if hasattr(admin, 'date'):
                        join_date = admin.date
                    elif hasattr(admin, 'joined_date'):
                        join_date = admin.joined_date
                    else:
                        # Если нет даты, используем текущее время
                        join_date = datetime.now(timezone.utc)
                    
                    members_data.append({
                        "user_id": admin.user.id,
                        "username": admin.user.username,
                        "full_name": admin.user.full_name,
                        "joined_at": join_date,
                        "status": admin.status
                    })
            
            logger.info(f"Found {len(members_data)} admin members with dates")
            
            # Если у нас есть данные об участниках, используем их
            if members_data:
                return members_data
                
        except Exception as e:
            logger.warning(f"Could not get admins: {e}")
        
        # Fallback: используем данные из базы ChannelMembership
        logger.info("Using database fallback for channel members")
        return []
        
    except Exception as e:
        logger.error(f"Error getting channel members: {e}")
        return []

async def get_channel_join_stats(channel_id: str, days: int = 7) -> dict:
    """Статистика вступлений в канал: всего, за неделю и за сегодня.
    Основано на реальных webhook-событиях, записанных в ChannelMembership.
    """
    try:
        # Временные границы
        now_utc = datetime.now(timezone.utc)
        start_week = now_utc - timedelta(days=days)
        start_today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

        # Реальное текущее количество участников
        total_members = await get_channel_member_count(channel_id)

        # Подсчет вступлений по БД (канал: free)
        from app.models.models import ChannelMembership
        from app.core.database import get_db
        db = next(get_db())

        week_joins = db.query(ChannelMembership).filter(
            ChannelMembership.channel_type == 'free',
            ChannelMembership.joined_at >= start_week
        ).count()

        today_joins = db.query(ChannelMembership).filter(
            ChannelMembership.channel_type == 'free',
            ChannelMembership.joined_at >= start_today
        ).count()

        return {
            "total_members": total_members,
            "week_joins": week_joins,
            "today_joins": today_joins,
            "source": "webhook_events"
        }
    except Exception as e:
        logger.error(f"Error in get_channel_join_stats: {e}")
        return {
            "total_members": 0,
            "week_joins": 0,
            "today_joins": 0,
            "source": "error"
        }

@app.get("/api/dashboard")
async def get_dashboard_data(
    request: Request,
    db: Session = Depends(get_db)
):
    """Получение данных для дашборда"""
    try:
        # Реальное количество участников бесплатного канала
        free_channel_members = await get_channel_member_count(settings.FREE_CHANNEL_ID)

        # Общая статистика по пользователям
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()

        # Временные границы
        now_utc = datetime.now(timezone.utc)
        week_start = now_utc - timedelta(days=7)
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

        # Новые регистрации в боте
        new_users_week = db.query(User).filter(User.registration_date >= week_start).count()
        new_users_today = db.query(User).filter(User.registration_date >= today_start).count()

        # Пользователи с активными подписками (заглушка: успешные платежи)
        users_with_subscription = db.query(User).join(Payment).filter(
            Payment.status == 'success',
            Payment.completed_at >= (now_utc - timedelta(days=365))
        ).count()

        # Новые с подпиской за период (по платежам)
        new_paid_week = db.query(User).join(Payment).filter(
            Payment.status == 'success',
            Payment.completed_at >= (now_utc - timedelta(days=7))
        ).count()
        new_paid_today = db.query(User).join(Payment).filter(
            Payment.status == 'success',
            Payment.completed_at >= today_start
        ).count()

        logger.info(
            f"Dashboard stats(reg): total={free_channel_members}, active={active_users}, "
            f"week_reg={new_users_week}, today_reg={new_users_today}"
        )

        return {
            "total_free_channel_users": free_channel_members,
            "active_users": active_users,
            "users_with_subscription": users_with_subscription,
            "new_users_week": new_users_week,
            "new_users_today": new_users_today,
            "new_paid_week": new_paid_week,
            "new_paid_today": new_paid_today
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении данных дашборда"
        )

@app.get("/api/dashboard/force-refresh")
async def force_refresh_dashboard(
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Принудительное обновление статистики дашборда"""
    try:
        logger.info("Force refresh dashboard requested")
        
        # Получаем актуальную статистику
        free_channel_members = await get_channel_member_count(settings.FREE_CHANNEL_ID)
        channel_stats = await get_channel_join_stats(settings.FREE_CHANNEL_ID, days=7)
        
        # Общая статистика по пользователям
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        
        # Пользователи с активными подписками
        users_with_subscription = db.query(User).join(Payment).filter(
            Payment.status == 'success',
            Payment.completed_at >= (datetime.now(timezone.utc) - timedelta(days=365))
        ).count()
        
        # Определяем начало сегодняшнего дня
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Статистика по бесплатному каналу
        new_users_week = channel_stats.get("week_joins", 0)
        new_users_today = channel_stats.get("today_joins", 0)
        
        # Новые пользователи с подпиской
        new_paid_week = db.query(User).join(Payment).filter(
            Payment.status == 'success',
            Payment.completed_at >= (datetime.now(timezone.utc) - timedelta(days=7))
        ).count()
        
        new_paid_today = db.query(User).join(Payment).filter(
            Payment.status == 'success',
            Payment.completed_at >= today_start
        ).count()
        
        logger.info(f"Force refresh stats: total={free_channel_members}, active={active_users}, "
                   f"week={new_users_week}, today={new_users_today}, source={channel_stats.get('source', 'unknown')}")
        
        return {
            "message": "Статистика принудительно обновлена",
            "total_free_channel_users": free_channel_members,
            "active_users": active_users,
            "users_with_subscription": users_with_subscription,
            "new_users_week": new_users_week,
            "new_users_today": new_users_today,
            "new_paid_week": new_paid_week,
            "new_paid_today": new_paid_today,
            "refresh_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in force refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка принудительного обновления: {str(e)}"
        )


@app.get("/api/users")
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
                subscription_status=user.get_subscription_status(),
                is_active=user.is_active
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
async def get_subscriptions(
    skip: int = 0,
    limit: int = 20,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Получение списка подписок"""
    try:
        # Временно убираем аутентификацию для отладки
        # current_admin = get_current_admin_from_cookies(request, db)
        
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


@app.post("/api/subscriptions/{subscription_id}/extend")
@rate_limit(requests_per_minute=10, requests_per_hour=100)
async def extend_subscription(
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


@app.post("/api/subscriptions/{subscription_id}/activate")
@rate_limit(requests_per_minute=10, requests_per_hour=100)
async def activate_subscription(
    subscription_id: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Активация подписки и добавление пользователя в платный канал"""
    try:
        current_admin = get_current_admin_from_cookies(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        user = subscription.user
        
        # Активируем подписку
        subscription.is_active = True
        subscription.start_date = datetime.now(timezone.utc)
        subscription.end_date = datetime.now(timezone.utc) + timedelta(days=30)  # По умолчанию 30 дней
        
        # Добавляем пользователя в платный канал
        from app.core.subscription_manager import subscription_manager
        await subscription_manager.add_user_to_paid_channel(user, db)
        
        logger.info(f"Subscription {subscription_id} activated and user {user.id} added to paid channel by admin {current_admin.username}")
        return {"message": "Подписка активирована, пользователь добавлен в платный канал"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating subscription: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при активации подписки"
        )


@app.post("/api/subscriptions/{subscription_id}/deactivate")
@rate_limit(requests_per_minute=10, requests_per_hour=100)
async def deactivate_subscription(
    subscription_id: int,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Деактивация подписки и удаление пользователя из платного канала"""
    try:
        current_admin = get_current_admin_from_cookies(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    try:
        subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            raise HTTPException(status_code=404, detail="Подписка не найдена")
        
        user = subscription.user
        
        # Деактивируем подписку
        subscription.is_active = False
        
        # Удаляем пользователя из платного канала
        from app.core.subscription_manager import subscription_manager
        await subscription_manager.remove_user_from_paid_channel(user.telegram_id)
        
        # Обновляем статус пользователя
        user.is_in_paid_channel = False
        user.paid_channel_join_date = None
        
        db.commit()
        
        logger.info(f"Subscription {subscription_id} deactivated and user {user.id} removed from paid channel by admin {current_admin.username}")
        return {"message": "Подписка деактивирована, пользователь удален из платного канала"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating subscription: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при деактивации подписки"
        )


@app.delete("/api/subscriptions/{subscription_id}")
@rate_limit(requests_per_minute=10, requests_per_hour=100)
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

@app.get("/api/subscriptions/stats")
async def get_subscriptions_stats(db: Session = Depends(get_db)):
    """Получение статистики подписок"""
    try:
        # Пользователи с подпиской
        users_with_subscription = db.query(User).join(Subscription).distinct().count()
        
        return {
            "users_with_subscription": users_with_subscription
        }
    except Exception as e:
        logger.error(f"Error getting subscriptions stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении статистики подписок"
        )


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    """Получение значения настройки из БД"""
    try:
        setting = db.query(BotSettings).filter(BotSettings.key == key).first()
        return setting.value if setting else default
    except Exception as e:
        logger.error(f"Error getting setting {key}: {e}")
        return default

def set_setting_value(db: Session, key: str, value: str, updated_by: str = "admin"):
    """Установка значения настройки в БД"""
    try:
        setting = db.query(BotSettings).filter(BotSettings.key == key).first()
        if setting:
            setting.value = str(value)
            setting.updated_at = datetime.now(timezone.utc)
            setting.updated_by = updated_by
        else:
            setting = BotSettings(
                key=key,
                value=str(value),
                updated_by=updated_by
            )
            db.add(setting)
        db.commit()
        logger.info(f"Setting {key} updated to {value} by {updated_by}")
    except Exception as e:
        logger.error(f"Error setting {key}: {e}")
        db.rollback()
        raise

@app.get("/api/subscriptions/settings")
async def get_subscription_settings(db: Session = Depends(get_db)):
    """Получение настроек подписки"""
    try:
        return {
            "subscription_price": int(get_setting_value(db, "subscription_price", "999")),
            "private_chat_link": get_setting_value(db, "private_chat_link", "https://t.me/private_chat_link"),
            "robokassa_encoded_invoice_id": get_setting_value(db, "robokassa_encoded_invoice_id", "pfV41IHNOEeWk9illbWUNQ")
        }
    except Exception as e:
        logger.error(f"Error getting subscription settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении настроек подписки"
        )


@app.get("/pay", response_class=HTMLResponse)
async def payment_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Промежуточная страница оплаты со встроенной Robokassa-формой.

    Параметры:
    - user_id: Telegram ID пользователя (передается из бота).
    """
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        price_str = get_setting_value(db, "subscription_price", str(settings.SUBSCRIPTION_PRICE))
        try:
            price = int(price_str)
        except Exception:
            price = settings.SUBSCRIPTION_PRICE

        # Создаём Payment со статусом pending
        from uuid import uuid4
        payment_id = f"ORD-{uuid4().hex[:12]}"
        payment = Payment(
            user_id=user.id,
            payment_id=payment_id,
            amount=price * 100,
            currency="RUB",
            status="pending",
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Deep link для возврата в бота (если указан username бота)
        bot_username = os.getenv("BOT_USERNAME", "")
        deep_link = f"https://t.me/{bot_username}?start=paid_order_{payment.payment_id}" if bot_username else None

        # EncodedInvoiceId (статический, от заказчика) + возможность задать в настройках
        encoded_invoice_id = get_setting_value(db, "robokassa_encoded_invoice_id", "pfV41IHNOEeWk9illbWUNQ")

        context = {
            "request": request,
            "user": user,
            "amount": price,
            "duration": settings.SUBSCRIPTION_DURATION_DAYS,
            "payment": payment,
            "robokassa_script_url": f"https://auth.robokassa.ru/Merchant/PaymentForm/FormSS.js?EncodedInvoiceId={encoded_invoice_id}",
            "bot_deep_link": deep_link,
        }
        response = templates.TemplateResponse("payment_standalone.html", context)
        # Set secure cookie binding to this payment (valid 60 minutes)
        cookie_value = _make_payment_cookie_value(payment.payment_id)
        response.set_cookie(
            key="rk_pay",
            value=cookie_value,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=3600,
            path="/"
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rendering payment page: {e}")
        raise HTTPException(status_code=500, detail="Ошибка отображения страницы оплаты")


@app.get("/robokassa/success", response_class=HTMLResponse)
async def robokassa_success(request: Request, db: Session = Depends(get_db)):
    """Обработка успешной оплаты (редирект со стороны Robokassa).

    Без подписи Robokassa. Привязка к платежу через HttpOnly cookie (HMAC).
    """
    try:
        now = datetime.now(timezone.utc)
        # Read and validate cookie
        cookie_value = request.cookies.get("rk_pay")
        payment_id = _parse_and_verify_payment_cookie(cookie_value) if cookie_value else None
        if not payment_id:
            response = templates.TemplateResponse(
                "payment_success_standalone.html",
                {
                    "request": request,
                    "message": "Сессия оплаты не найдена или устарела. Обратитесь в поддержку.",
                    "bot_deep_link": f"https://t.me/{os.getenv('BOT_USERNAME', '')}" if os.getenv('BOT_USERNAME') else None
                },
            )
            response.delete_cookie("rk_pay", path="/")
            return response

        # Find specific pending payment within 60 minutes
        sixty_minutes_ago = now - timedelta(minutes=60)
        payment = (
            db.query(Payment)
            .filter(
                Payment.payment_id == payment_id,
                Payment.status == "pending",
                Payment.created_at >= sixty_minutes_ago,
            )
            .order_by(Payment.created_at.desc())
            .first()
        )
        if not payment:
            response = templates.TemplateResponse(
                "payment_success_standalone.html",
                {
                    "request": request,
                    "message": "Подходящий платёж не найден или уже обработан.",
                    "bot_deep_link": f"https://t.me/{os.getenv('BOT_USERNAME', '')}" if os.getenv('BOT_USERNAME') else None
                },
            )
            response.delete_cookie("rk_pay", path="/")
            return response

        # Mark success
        payment.status = "success"
        payment.completed_at = now
        db.commit()
        db.refresh(payment)

        user = db.query(User).filter(User.id == payment.user_id).first()
        if user:
            # Extend/create subscription by duration
            subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
            if subscription and subscription.end_date and subscription.end_date > now:
                subscription.end_date += timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
                subscription.is_active = True
            else:
                if not subscription:
                    subscription = Subscription(
                        user_id=user.id,
                        start_date=now,
                        end_date=now + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS),
                        is_active=True,
                        auto_renewal=False,
                        payment_amount=int(payment.amount / 100) if payment.amount else None,
                    )
                    db.add(subscription)
                else:
                    subscription.start_date = now
                    subscription.end_date = now + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
                    subscription.is_active = True
            db.commit()

            # Add user to paid channel
            try:
                from app.core.subscription_manager import subscription_manager
                await subscription_manager.add_user_to_paid_channel(user, db)
            except Exception as e:
                logger.warning(f"Failed to add user {user.id} to paid channel after success: {e}")

        # Deep-link back to bot
        bot_username = os.getenv("BOT_USERNAME", "")
        deep_link = f"https://t.me/{bot_username}" if bot_username else None

        response = templates.TemplateResponse(
            "payment_success_standalone.html",
            {
                "request": request,
                "message": "Оплата успешно подтверждена. Подписка активирована.",
                "bot_deep_link": deep_link,
            },
        )
        response.delete_cookie("rk_pay", path="/")
        return response
    except Exception as e:
        logger.error(f"Robokassa success handler error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обработки успешной оплаты")


@app.get("/robokassa/fail", response_class=HTMLResponse)
async def robokassa_fail(request: Request, db: Session = Depends(get_db)):
    """Обработка неуспешной оплаты (редирект со стороны Robokassa)."""
    try:
        now = datetime.now(timezone.utc)
        cookie_value = request.cookies.get("rk_pay")
        payment_id = _parse_and_verify_payment_cookie(cookie_value) if cookie_value else None

        if payment_id:
            sixty_minutes_ago = now - timedelta(minutes=60)
            payment = (
                db.query(Payment)
                .filter(
                    Payment.payment_id == payment_id,
                    Payment.status == "pending",
                    Payment.created_at >= sixty_minutes_ago,
                )
                .order_by(Payment.created_at.desc())
                .first()
            )
            if payment:
                payment.status = "failed"
                payment.completed_at = now
                db.commit()

        bot_username = os.getenv("BOT_USERNAME", "")
        deep_link = f"https://t.me/{bot_username}" if bot_username else None

        response = templates.TemplateResponse(
            "payment_fail_standalone.html",
            {
                "request": request,
                "message": "Оплата не была завершена. Попробуйте ещё раз.",
                "bot_deep_link": deep_link,
            },
        )
        response.delete_cookie("rk_pay", path="/")
        return response
    except Exception as e:
        logger.error(f"Robokassa fail handler error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обработки неуспешной оплаты")

@app.post("/api/subscriptions/settings")
async def update_subscription_settings(
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Обновление настроек подписки"""
    try:
        # Временно убираем аутентификацию для отладки
        # current_admin = get_current_admin_from_cookies(request, db)
        
        # Получаем данные из тела запроса
        body = await request.json()
        subscription_price = body.get("subscription_price")
        private_chat_link = body.get("private_chat_link")
        robokassa_encoded_invoice_id = body.get("robokassa_encoded_invoice_id")
        
        # Валидация
        if subscription_price is not None and subscription_price < 0:
            raise HTTPException(status_code=400, detail="Цена подписки не может быть отрицательной")
        
        # Сохраняем настройки в БД
        if subscription_price is not None:
            set_setting_value(db, "subscription_price", str(subscription_price), "admin")
        
        if private_chat_link is not None:
            set_setting_value(db, "private_chat_link", private_chat_link, "admin")
        
        if robokassa_encoded_invoice_id is not None:
            set_setting_value(db, "robokassa_encoded_invoice_id", robokassa_encoded_invoice_id, "admin")
        
        logger.info(f"Subscription settings updated: price={subscription_price}, chat_link={private_chat_link}, robokassa_id={robokassa_encoded_invoice_id}")
        
        return {"message": "Настройки подписки успешно обновлены"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subscription settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении настроек подписки"
        )

@app.get("/api/users/stats")
async def get_users_stats(
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Получение статистики пользователей по каналам"""
    try:
        # Временно убираем аутентификацию для отладки
        # current_admin = get_current_admin_from_cookies(request, db)
        
        # Получаем реальное количество участников бесплатного канала
        free_channel_members = await get_channel_member_count(settings.FREE_CHANNEL_ID)
        
        # Статистика по пользователям
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        
        # Пользователи с активными подписками
        users_with_subscription = db.query(User).join(Subscription).filter(
            Subscription.is_active == True,
            Subscription.end_date > datetime.now(timezone.utc)
        ).count()
        
        # Новые пользователи за сегодня
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        new_users_today = db.query(User).filter(
            User.registration_date >= today_start,
            User.registration_date < today_end
        ).count()
        
        return {
            "total_free_channel": free_channel_members,  # Реальное количество участников канала
            "active_users": active_users,  # Активные пользователи (зарегистрированные в боте)
            "users_with_subscription": users_with_subscription,  # С подпиской
            "new_users_today": new_users_today
        }
    except Exception as e:
        logger.error(f"Error getting users stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении статистики пользователей"
        )

@app.post("/api/channel/refresh-stats")
async def refresh_channel_stats(
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Принудительное обновление статистики канала"""
    try:
        logger.info("Manual channel stats refresh requested")
        
        # Получаем актуальную статистику
        channel_stats = await get_channel_join_stats(settings.FREE_CHANNEL_ID, days=7)
        
        # Получаем количество участников
        total_members = await get_channel_member_count(settings.FREE_CHANNEL_ID)
        
        # Получаем участников с датами
        members_data = await get_channel_members_with_dates(settings.FREE_CHANNEL_ID)
        
        logger.info(f"Refreshed stats: total={total_members}, members_data={len(members_data)}")
        logger.info(f"Channel stats: {channel_stats}")
        
        return {
            "message": "Статистика обновлена",
            "total_members": total_members,
            "channel_stats": channel_stats,
            "members_data": members_data
        }
        
    except Exception as e:
        logger.error(f"Error refreshing channel stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления статистики: {str(e)}"
        )
