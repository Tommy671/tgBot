"""
Миграции базы данных
"""
from sqlalchemy import create_engine, text
from app.core.database import Base, SessionLocal
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def upgrade_database():
    """Обновление базы данных до последней версии"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Проверяем существование таблицы channel_memberships
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='channel_memberships'
        """))
        
        if not result.fetchone():
            logger.info("Creating channel_memberships table...")
            conn.execute(text("""
                CREATE TABLE channel_memberships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_type VARCHAR NOT NULL,
                    joined_at DATETIME NOT NULL,
                    left_at DATETIME,
                    is_current BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """))
            conn.execute(text("CREATE INDEX ix_channel_memberships_user_id ON channel_memberships (user_id)"))
            conn.execute(text("CREATE INDEX ix_channel_memberships_channel_type ON channel_memberships (channel_type)"))
            logger.info("channel_memberships table created successfully")
        
        # Проверяем существование таблицы payments
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='payments'
        """))
        
        if not result.fetchone():
            logger.info("Creating payments table...")
            conn.execute(text("""
                CREATE TABLE payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    payment_id VARCHAR NOT NULL UNIQUE,
                    amount INTEGER NOT NULL,
                    currency VARCHAR NOT NULL DEFAULT 'RUB',
                    status VARCHAR NOT NULL,
                    payment_method VARCHAR,
                    created_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """))
            conn.execute(text("CREATE INDEX ix_payments_user_id ON payments (user_id)"))
            conn.execute(text("CREATE INDEX ix_payments_payment_id ON payments (payment_id)"))
            conn.execute(text("CREATE INDEX ix_payments_status ON payments (status)"))
            logger.info("payments table created successfully")
        
        # Проверяем существование новых колонок в таблице users
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'is_in_free_channel' not in columns:
            logger.info("Adding is_in_free_channel column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN is_in_free_channel BOOLEAN DEFAULT 0"))
            logger.info("is_in_free_channel column added successfully")
        
        if 'is_in_paid_channel' not in columns:
            logger.info("Adding is_in_paid_channel column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN is_in_paid_channel BOOLEAN DEFAULT 0"))
            logger.info("is_in_paid_channel column added successfully")
        
        if 'free_channel_join_date' not in columns:
            logger.info("Adding free_channel_join_date column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN free_channel_join_date DATETIME"))
            logger.info("free_channel_join_date column added successfully")
        
        if 'paid_channel_join_date' not in columns:
            logger.info("Adding paid_channel_join_date column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN paid_channel_join_date DATETIME"))
            logger.info("paid_channel_join_date column added successfully")
        
        conn.commit()
        logger.info("Database upgrade completed successfully")
