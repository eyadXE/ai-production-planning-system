"""FastAPI application entrypoint.

Run: .venv/bin/uvicorn finalproject.api.main:app --reload
"""

from fastapi import FastAPI

from finalproject.api.auth_routes import router as auth_router
from finalproject.api.board_routes import router as board_router
from finalproject.db.database import init_db

app = FastAPI(title="Ousus Production Platform", version="0.1.0")
app.include_router(auth_router)
app.include_router(board_router)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
