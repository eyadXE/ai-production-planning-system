"""FastAPI application entrypoint.

Run: .venv/bin/uvicorn finalproject.api.main:app --reload

Reads .env from the project root if python-dotenv is available.
"""

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finalproject.api.auth_routes import router as auth_router
from finalproject.api.board_routes import router as board_router
from finalproject.api.intake_chat import router as intake_chat_router
from finalproject.api.intake_routes import router as intake_router
from finalproject.db.database import init_db

app = FastAPI(title="Ousus Production Platform", version="0.1.0")

# uploaded custom-object photos & product catalogue PDFs
from pathlib import Path

from fastapi.staticfiles import StaticFiles

(Path("data/uploads")).mkdir(parents=True, exist_ok=True)
Path("frontend/public/catalogs").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")
app.mount("/catalogs", StaticFiles(directory="frontend/public/catalogs"),
          name="catalogs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3100",
        "http://127.0.0.1:3100",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(board_router)
app.include_router(intake_router)
app.include_router(intake_chat_router)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
