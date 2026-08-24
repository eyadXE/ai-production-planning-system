"""FastAPI application entrypoint.

Run: .venv/bin/uvicorn finalproject.api.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finalproject.api.auth_routes import router as auth_router
from finalproject.api.board_routes import router as board_router
from finalproject.db.database import init_db

app = FastAPI(title="Ousus Production Platform", version="0.1.0")
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


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
