import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import demo_mode_enabled
from backend.app.routers.matches import router as matches_router
from backend.app.routers.ai import router as ai_router
from backend.app.services.fantasy_points import FantasyPointsRequest, calculate_fantasy_points

app = FastAPI(title="FantasyEdge AI API", version="0.1.0")

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if origin.strip()
]
if "*" in frontend_origins:
    raise RuntimeError(
        "FRONTEND_ORIGINS must contain explicit origins; wildcard origins are not allowed."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(matches_router)
app.include_router(ai_router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "FantasyEdge AI backend is ready"}


@app.post("/api/fantasy/calculate")
async def calculate_fantasy(request: FantasyPointsRequest) -> dict:
    return calculate_fantasy_points(request)
