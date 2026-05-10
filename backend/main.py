import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from database import Base, check_database_connection, engine, ensure_runtime_dirs, ensure_schema_compatibility, get_upload_root_path
from routers import admin, appointments, auth, doctor, medical_ai, nlp, ocr, patient, payments, reminders, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_runtime_dirs()
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    yield


app = FastAPI(
    title="Nora MedLink API",
    description="FastAPI backend for Nora MedLink authentication, OCR, summaries, and patient documents.",
    version="0.3.0",
    lifespan=lifespan,
)

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
allowed_origins = {
    frontend_origin,
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

ensure_runtime_dirs()
app.mount("/uploads", StaticFiles(directory=get_upload_root_path()), name="uploads")

app.include_router(auth.router)
app.include_router(auth.router, prefix="/api")
app.include_router(admin.router)
app.include_router(patient.router)
app.include_router(reports.router)
app.include_router(doctor.router)
app.include_router(ocr.router)
app.include_router(nlp.router)
app.include_router(appointments.router)
app.include_router(payments.router)
app.include_router(reminders.router)
app.include_router(medical_ai.router)


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
def health_check():
    return {"status": "ok", "service": "Nora MedLink API"}


@app.get("/health/database")
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
