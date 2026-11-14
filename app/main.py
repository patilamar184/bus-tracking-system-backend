
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import models  # noqa: F401
from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.routers import admin, device, parent

# Load environment variables
load_dotenv()


def get_cors_origins():
    raw = os.getenv("CORS_ORIGINS", "").strip()

    if not raw:
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    if raw == "*":
        return ["*"]

    return [
        origin.strip().rstrip("/")
        for origin in raw.split(",")
        if origin.strip()
    ]


def create_default_admin() -> None:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")

    if not username or not password:
        print("WARNING: ADMIN_USERNAME / ADMIN_PASSWORD not set")
        return

    with SessionLocal() as db:
        existing_admin = db.scalar(
            select(models.Admin).where(
                models.Admin.username == username
            )
        )

        if existing_admin is None:
            db.add(
                models.Admin(
                    username=username,
                    hashed_password=hash_password(password),
                )
            )
            db.commit()
            print("Default admin created successfully.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    print("Starting School Bus Tracking API...")

    Base.metadata.create_all(bind=engine)
    create_default_admin()

    print("Database initialized successfully.")

    yield

    print("School Bus Tracking API shutting down.")


app = FastAPI(
    title="School Bus Tracking API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(admin.router)
app.include_router(device.router)
app.include_router(parent.router)


@app.get("/")
def root():
    return {
        "message": "School Bus Tracking API is running",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "School Bus Tracking API",
    }
