import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
LOCAL_DEPS_DIR = BACKEND_DIR / ".testdeps"
DEV_DATABASE_PATH = BACKEND_DIR / "runtime-dev.db"


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def configure_import_paths() -> None:
    paths = [BACKEND_DIR]
    if LOCAL_DEPS_DIR.exists():
        paths.insert(0, LOCAL_DEPS_DIR)

    for path in reversed(paths):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)

    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath_parts = [str(path) for path in paths]
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    os.environ["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)


def main() -> None:
    configure_import_paths()
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND_DIR.parent / ".env")
        load_dotenv(BACKEND_DIR / ".env", override=True)
    except ImportError:
        pass

    configured_database_url = (
        os.environ.get("FASTAPI_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )
    if configured_database_url:
        os.environ["FASTAPI_DATABASE_URL"] = configured_database_url
    else:
        os.environ.setdefault("FASTAPI_DATABASE_URL", sqlite_url(DEV_DATABASE_PATH))

    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        app_dir=str(BACKEND_DIR),
    )


if __name__ == "__main__":
    main()
