from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router as api_router
from .sse_routes import router as sse_router


def create_app() -> FastAPI:
    app = FastAPI(title="cc3 chat api", version="0.1.0")

    # MVP CORS for Vite dev server.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(sse_router)
    return app


app = create_app()
