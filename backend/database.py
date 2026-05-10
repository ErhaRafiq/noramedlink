import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)

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
    configured_url = (
        os.getenv("FASTAPI_DATABASE_URL", "").strip().strip('"').strip("'")
        or os.getenv("DATABASE_URL", "").strip().strip('"').strip("'")
    )
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
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
}

if DATABASE_BACKEND == "postgresql":
    engine_options.update(
        {
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30")),
        }
    )
else:
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
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
    configured_path = os.getenv("UPLOAD_DIR", "uploads")
    upload_root = Path(configured_path)
    if not upload_root.is_absolute():
        upload_root = BACKEND_DIR / upload_root
    return upload_root


def ensure_runtime_dirs() -> None:
    get_upload_root_path().mkdir(parents=True, exist_ok=True)


def ensure_schema_compatibility() -> None:
    """Keep local/dev databases compatible; PostgreSQL production should still use Prisma migrations."""
    with engine.begin() as connection:
        if DATABASE_BACKEND == "postgresql":
            connection.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true
                    """
                )
            )
            connection.execute(
                text(
                    """
                    ALTER TABLE signup_otps
                    ADD COLUMN IF NOT EXISTS payload_json JSONB NOT NULL DEFAULT '{}'::jsonb
                    """
                )
            )
            connection.execute(
                text(
                    """
                    ALTER TABLE patient_reports
                    ADD COLUMN IF NOT EXISTS extracted_entities JSONB NOT NULL DEFAULT '[]'::jsonb,
                    ADD COLUMN IF NOT EXISTS rule_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
                    ADD COLUMN IF NOT EXISTS validation_status TEXT NOT NULL DEFAULT 'SAFE',
                    ADD COLUMN IF NOT EXISTS validation_results JSONB NOT NULL DEFAULT '{}'::jsonb,
                    ADD COLUMN IF NOT EXISTS clinical_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    ADD COLUMN IF NOT EXISTS llm_self_check JSONB NOT NULL DEFAULT '{}'::jsonb,
                    ADD COLUMN IF NOT EXISTS summary_source TEXT NOT NULL DEFAULT 'rule_based'
                    """
                )
            )
            connection.execute(text("ALTER TABLE medical_ai_analyses ADD COLUMN IF NOT EXISTS patient_report_id INTEGER"))
            connection.execute(
                text(
                    'CREATE INDEX IF NOT EXISTS patient_reports_validation_status_idx ON patient_reports("validation_status")'
                )
            )
            connection.execute(
                text(
                    'CREATE INDEX IF NOT EXISTS medical_ai_analyses_patient_report_id_idx ON medical_ai_analyses("patient_report_id")'
                )
            )
            return

        if DATABASE_BACKEND == "sqlite":
            user_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(users)")).fetchall()
            }
            if "is_active" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))

            otp_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(signup_otps)")).fetchall()
            }
            if "payload_json" not in otp_columns:
                connection.execute(text("ALTER TABLE signup_otps ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}'"))

            report_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(patient_reports)")).fetchall()
            }
            sqlite_report_columns = {
                "extracted_entities": "TEXT NOT NULL DEFAULT '[]'",
                "rule_warnings": "TEXT NOT NULL DEFAULT '[]'",
                "validation_status": "TEXT NOT NULL DEFAULT 'SAFE'",
                "validation_results": "TEXT NOT NULL DEFAULT '{}'",
                "clinical_summary_json": "TEXT NOT NULL DEFAULT '{}'",
                "llm_self_check": "TEXT NOT NULL DEFAULT '{}'",
                "summary_source": "TEXT NOT NULL DEFAULT 'rule_based'",
            }
            for column, ddl in sqlite_report_columns.items():
                if column not in report_columns:
                    connection.execute(text(f"ALTER TABLE patient_reports ADD COLUMN {column} {ddl}"))

            analysis_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(medical_ai_analyses)")).fetchall()
            }
            if "patient_report_id" not in analysis_columns:
                connection.execute(text("ALTER TABLE medical_ai_analyses ADD COLUMN patient_report_id INTEGER"))
