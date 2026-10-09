"""
AI-Driven Intelligent Academic Assessment and Performance Analytics System
FastAPI Application Entry Point — Phase 1

Run with:
    cd backend
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assessments as assessments_router
from app.api import assignments as assignments_router
from app.api import auth as auth_router
from app.api import enrollments as enrollments_router
from app.api import faculty_analytics as faculty_analytics_router
from app.api import materials as materials_router
from app.api import protected as protected_router
from app.api import questions as questions_router
from app.api import rubrics as rubrics_router
from app.api import student_analytics as student_analytics_router
from app.api import subjects as subjects_router
from app.api import submissions as submissions_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers




@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    Runs startup logic before the app begins serving requests.
    Database tables are managed via Alembic migrations — NOT created here.
    """
    settings = get_settings()
    print(f"🚀  Starting {settings.app_name} v{settings.app_version}")
    yield
    print("🛑  Shutting down application.")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend API for the AI-Driven Intelligent Academic Assessment System. "
            "Phase 1: Authentication and role-based access control."
        ),
        lifespan=lifespan,
        # Swagger UI available at /docs, ReDoc at /redoc
    )

    # ---------------------------------------------------------------------------
    # CORS — permissive for development; restrict in production
    # ---------------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],  # React dev servers
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------------------
    # Exception handlers
    # ---------------------------------------------------------------------------
    register_exception_handlers(app)

    # ---------------------------------------------------------------------------
    # Routers
    # ---------------------------------------------------------------------------
    app.include_router(auth_router.router)
    app.include_router(enrollments_router.router)
    app.include_router(protected_router.router)
    app.include_router(subjects_router.router)
    app.include_router(materials_router.router)
    app.include_router(assignments_router.router)
    app.include_router(questions_router.router)
    app.include_router(rubrics_router.router)
    app.include_router(submissions_router.router)
    app.include_router(assessments_router.router)
    app.include_router(student_analytics_router.router)
    app.include_router(faculty_analytics_router.router)



    # ---------------------------------------------------------------------------
    # Health check
    # ---------------------------------------------------------------------------
    @app.get("/health", tags=["Health"])
    def health_check() -> dict:
        return {"status": "ok", "version": settings.app_version}

    return app


app = create_app()
