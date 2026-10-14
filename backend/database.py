import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import BACKEND_DIR, PROJECT_ROOT, settings

DEFAULT_SQLITE_PATH = BACKEND_DIR / "dev.db"
logger = logging.getLogger("nora.database")


def _sqlite_url_for_path(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _normalize_database_url(configured_url: str) -> str:
    if configured_url.startswith("file:"):
        sqlite_path = Path(configured_url.removeprefix("file:"))
        if not sqlite_path.is_absolute():
            sqlite_path = PROJECT_ROOT / sqlite_path
        return _sqlite_url_for_path(sqlite_path)

    parsed_url = make_url(configured_url)
    if parsed_url.get_backend_name() == "sqlite" and parsed_url.database:
        sqlite_database = parsed_url.database
        if sqlite_database != ":memory:":
            sqlite_path = Path(sqlite_database)
            if not sqlite_path.is_absolute():
                return _sqlite_url_for_path(BACKEND_DIR / sqlite_path)

    return configured_url


def get_database_url() -> str:
    configured_url = settings.database_url
    if not configured_url:
        logger.warning("No PostgreSQL URL configured; using local SQLite fallback for development only.")
        return _sqlite_url_for_path(DEFAULT_SQLITE_PATH)

    try:
        normalized_url = _normalize_database_url(configured_url)
        parsed_url = make_url(normalized_url)
    except Exception as exc:
        raise RuntimeError("Configured database URL is not a valid SQLAlchemy database URL.") from exc

    backend_name = parsed_url.get_backend_name()
    if backend_name not in {"postgresql", "sqlite"}:
        raise RuntimeError("Nora MedLink backend requires PostgreSQL in production.")

    return normalized_url


DATABASE_URL = get_database_url()
DATABASE_BACKEND = make_url(DATABASE_URL).get_backend_name()

engine_options = {
    "pool_pre_ping": True,
    "pool_recycle": settings.db_pool_recycle_seconds,
}

if DATABASE_BACKEND == "postgresql":
    engine_options.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout_seconds,
        }
    )
else:
    engine_options["connect_args"] = {"check_same_thread": False}

# hide_parameters: a failed statement is logged without its values (report text, names), only the SQL.
engine = create_engine(DATABASE_URL, hide_parameters=True, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database transaction rolled back after SQLAlchemy error.")
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> dict[str, str]:
    parsed_url = make_url(DATABASE_URL)
    database_name = "postgresql" if parsed_url.get_backend_name() == "postgresql" else "sqlite"
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": database_name,
        "connection": "successful",
    }


def get_upload_root_path() -> Path:
    upload_root = Path(settings.upload_dir)
    if not upload_root.is_absolute():
        upload_root = BACKEND_DIR / upload_root
    return upload_root


def ensure_runtime_dirs() -> None:
    get_upload_root_path().mkdir(parents=True, exist_ok=True)


def run_migrations() -> None:
    """Bring the database schema to the latest Alembic revision (backend/migrations).

    Every migration is additive and checks what already exists, so this is safe on
    fresh databases and on ones created earlier by create_all or Prisma.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
