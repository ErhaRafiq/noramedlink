from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from config import settings
from database import check_database_connection, ensure_runtime_dirs, run_migrations
from logging_config import configure_logging
from rate_limit import limiter, rate_limit_exceeded_handler
from routers import (
    admin,
    appointments,
    auth,
    clinical_summary,
    dashboard_access,
    doctor,
    emergency,
    files,
    medical_ai,
    medications,
    medicine_reminders,
    nlp,
    ocr,
    patient,
    patient_insights,
    patient_medicines,
    payments,
    reminders,
    reports,
    vitals,
)

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_runtime_dirs()
    # Schema changes go through Alembic migrations (backend/migrations), not create_all.
    run_migrations()
    yield


app = FastAPI(
    title="Nora MedLink API",
    description="FastAPI backend for Nora MedLink authentication, OCR, summaries, and patient documents.",
    version="0.3.0",
    lifespan=lifespan,
)

allowed_origins = {
    settings.frontend_origin,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limits: per-route limits are set with @limiter.limit in the routers; every other
# route gets the default limit through the middleware. See rate_limit.py.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Uploaded files are not served publicly; see routers/files.py (GET /files/...).

app.include_router(auth.router)
app.include_router(auth.router, prefix="/api")
app.include_router(admin.router)
app.include_router(patient.router)
app.include_router(patient_medicines.router)
app.include_router(patient_insights.router)
app.include_router(reports.router)
app.include_router(doctor.router)
app.include_router(clinical_summary.router)
app.include_router(ocr.router)
app.include_router(nlp.router)
app.include_router(appointments.router)
app.include_router(payments.router)
app.include_router(reminders.router)
app.include_router(medical_ai.router)
app.include_router(vitals.router)
app.include_router(medications.router)
app.include_router(medicine_reminders.router)
app.include_router(dashboard_access.router)
app.include_router(emergency.router)
app.include_router(files.router)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc: SQLAlchemyError):
    status_code = 503 if isinstance(exc, OperationalError) else 500
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": "Database operation failed. Check PostgreSQL connectivity, migrations, and foreign key data.",
        },
    )


@app.get("/health")
@limiter.exempt
def health_check():
    return {"status": "ok", "service": "Nora MedLink API"}


@app.get("/health/database")
@limiter.exempt
def database_health_check():
    try:
        return check_database_connection()
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "postgresql",
                "connection": "failed",
                "detail": f"Database connection failed: {exc.__class__.__name__}. Verify PostgreSQL is running, credentials are valid, and migrations are applied.",
            },
        )
