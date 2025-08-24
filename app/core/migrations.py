"""
Миграции базы данных
"""
from sqlalchemy import text
from app.core.database import engine, SessionLocal
import logging

logger = logging.getLogger(__name__)


def run_migrations():
    """Запуск всех миграций"""
    try:
        with engine.connect() as conn:
            # Создаем таблицу для отслеживания миграций
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        
        # Получаем список примененных миграций
        with SessionLocal() as db:
            applied_migrations = db.execute(text("SELECT version FROM migrations")).fetchall()
            applied_versions = [row[0] for row in applied_migrations]
        
        # Список всех миграций
        migrations = [
            ("001_initial_schema", initial_schema_migration),
            ("002_add_indexes", add_indexes_migration),
            ("003_add_constraints", add_constraints_migration),
        ]
        
        # Применяем миграции
        for version, migration_func in migrations:
            if version not in applied_versions:
                logger.info(f"Applying migration: {version}")
                try:
                    migration_func()
                    # Отмечаем миграцию как примененную
                    with SessionLocal() as db:
                        db.execute(
                            text("INSERT INTO migrations (version) VALUES (:version)"),
                            {"version": version}
                        )
                        db.commit()
                    logger.info(f"Migration {version} applied successfully")
                except Exception as e:
                    logger.error(f"Failed to apply migration {version}: {e}")
                    raise
            else:
                logger.info(f"Migration {version} already applied")
        
        logger.info("All migrations completed successfully")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise


def initial_schema_migration():
    """Первоначальная схема базы данных"""
    with engine.connect() as conn:
        # Создаем таблицы если они не существуют
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                activity_field TEXT,
                company TEXT,
                role_in_company TEXT,
                contact_number TEXT,
                participation_purpose TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                consent_given BOOLEAN DEFAULT 0,
                consent_date TIMESTAMP
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                auto_renewal BOOLEAN DEFAULT 0,
                payment_amount INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        """))
        
        conn.commit()


def add_indexes_migration():
    """Добавление индексов для улучшения производительности"""
    with engine.connect() as conn:
        # Индексы для таблицы users
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_registration_date ON users(registration_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)"))
        
        # Индексы для таблицы subscriptions
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_end_date ON subscriptions(end_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_is_active ON subscriptions(is_active)"))
        
        # Индексы для таблицы admin_users
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username)"))
        
        conn.commit()


def add_constraints_migration():
    """Добавление ограничений для целостности данных"""
    with engine.connect() as conn:
        # Ограничения для таблицы users
        conn.execute(text("""
            ALTER TABLE users ADD CONSTRAINT chk_users_telegram_id 
            CHECK (telegram_id > 0)
        """))
        
        # Ограничения для таблицы subscriptions
        conn.execute(text("""
            ALTER TABLE subscriptions ADD CONSTRAINT chk_subscriptions_amount 
            CHECK (payment_amount >= 0)
        """))
        
        conn.execute(text("""
            ALTER TABLE subscriptions ADD CONSTRAINT chk_subscriptions_dates 
            CHECK (end_date > start_date)
        """))
        
        conn.commit()


def rollback_migration(version: str):
    """Откат конкретной миграции"""
    try:
        with SessionLocal() as db:
            # Удаляем запись о миграции
            db.execute(
                text("DELETE FROM migrations WHERE version = :version"),
                {"version": version}
            )
            db.commit()
        
        logger.info(f"Migration {version} rolled back successfully")
        
    except Exception as e:
        logger.error(f"Failed to rollback migration {version}: {e}")
        raise


def get_migration_status():
    """Получение статуса миграций"""
    try:
        with SessionLocal() as db:
            migrations = db.execute(text("SELECT * FROM migrations ORDER BY applied_at")).fetchall()
            return [
                {
                    "version": row[1],
                    "applied_at": row[2]
                }
                for row in migrations
            ]
    except Exception as e:
        logger.error(f"Failed to get migration status: {e}")
        return []
