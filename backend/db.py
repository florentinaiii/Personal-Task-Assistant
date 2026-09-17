import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

# Local development uses SQLite.
# Production uses DATABASE_URL from Render (Neon PostgreSQL).
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./database.db"
)


# ============================================================
# DATABASE ENGINE
# ============================================================

if DATABASE_URL.startswith("sqlite"):
    # Local SQLite database
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

else:
    # Neon / PostgreSQL
    #
    # Force SQLAlchemy to use psycopg 3.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql+psycopg://",
            1
        )

    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1
        )

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )


# ============================================================
# DATABASE SESSION
# ============================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ============================================================
# CREATE TABLES
# ============================================================

def create_tables():
    Base.metadata.create_all(bind=engine)


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()