"""
Модуль аутентификации
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import AdminUser
from app.core.config import settings

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создание JWT токена"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    """Проверка JWT токена"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None


def authenticate_admin(db: Session, username: str, password: str):
    """Аутентификация администратора"""
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not admin:
        return False
    if not admin.verify_password(password):
        return False
    return admin


def get_token_from_cookies(request: Request) -> Optional[str]:
    """Получение токена из cookies"""
    token = request.cookies.get("access_token")
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Cookies received: {dict(request.cookies)}")
    logger.debug(f"Token from cookies: {token[:20] if token else 'None'}...")
    return token


def get_current_admin_from_cookies(request: Request, db: Session):
    """Получение текущего администратора из cookies"""
    import logging
    logger = logging.getLogger(__name__)
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = get_token_from_cookies(request)
    if not token:
        logger.debug("No token found in cookies")
        raise credentials_exception
    
    try:
        username = verify_token(token)
        if username is None:
            logger.debug("Token verification failed")
            raise credentials_exception
        
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if admin is None:
            logger.debug(f"Admin user {username} not found in database")
            raise credentials_exception
        
        logger.debug(f"Admin {username} authenticated successfully")
        return admin
    except Exception as e:
        logger.debug(f"Auth error: {e}")
        raise credentials_exception


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    db: Session = Depends(get_db)
):
    """Получение текущего администратора из заголовка Authorization"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    username = verify_token(token)
    if username is None:
        raise credentials_exception
    
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if admin is None:
        raise credentials_exception
    
    return admin


def create_default_admin(db: Session):
    """Создание администратора по умолчанию"""
    existing_admin = db.query(AdminUser).filter(AdminUser.username == "admin1").first()
    if existing_admin:
        return False
    
    admin = AdminUser(
        username="admin1",
        hashed_password=AdminUser.get_password_hash("admin123")
    )
    
    db.add(admin)
    db.commit()
    return True
