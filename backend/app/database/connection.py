from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings


def build_engine():
    database_url = settings.DATABASE_URL
    if database_url.startswith("sqlite"):
        return create_engine(database_url, pool_pre_ping=True, connect_args={"check_same_thread": False})

    try:
        import psycopg2  # noqa: F401
    except ModuleNotFoundError:
        return create_engine("sqlite:///modelverse_local.db", pool_pre_ping=True, connect_args={"check_same_thread": False})

    return create_engine(database_url, pool_pre_ping=True)


engine = build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
