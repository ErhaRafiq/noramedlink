"""Alembic environment for the Nora MedLink FastAPI backend.

The database URL comes from backend/database.py (FASTAPI_DATABASE_URL / DATABASE_URL in
the .env files); it is never stored in alembic.ini and never printed.

Optional: `-x database=<name>` targets another database on the same localhost server
(e.g. a scratch database for checking migrations). Only the database name is swapped.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

import models  # noqa: F401  (registers every model on Base.metadata)
from database import DATABASE_URL, Base

config = context.config

# Configure logging only for the alembic CLI; when the app runs migrations at startup,
# fileConfig would disable uvicorn's loggers.
if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Duplicate indexes that the old startup ensure_schema_compatibility() created alongside
# the models' ix_* indexes. They are kept (migrations are additive only) but ignored
# when comparing the database with the models.
LEGACY_INDEXES = {
    "patient_reports_validation_status_idx",
    "medical_ai_analyses_patient_report_id_idx",
}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "index" and reflected and compare_to is None and name in LEGACY_INDEXES:
        return False
    return True


def database_url() -> str:
    url = make_url(DATABASE_URL)
    override = context.get_x_argument(as_dictionary=True).get("database")
    if override:
        if url.get_backend_name() != "postgresql" or url.host not in LOCAL_HOSTS:
            raise RuntimeError("-x database=... is only allowed for a local PostgreSQL server.")
        url = url.set(database=override)
    return url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is not None:
        # Called programmatically with an existing connection (see database.run_migrations).
        _run_with_connection(connectable)
        return

    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        _run_with_connection(connection)


def _run_with_connection(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
