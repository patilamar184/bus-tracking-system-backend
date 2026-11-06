import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Admin, Device

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "")
if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY is missing or too short (min 32 chars). Set it in .env. "
        'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

bearer_scheme = HTTPBearer(auto_error=False)


# ---------- Admin passwords ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:  # e.g. password longer than bcrypt's 72-byte limit
        return False


# ---------- Admin JWT ----------
def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise unauthorized
    username = payload.get("sub")
    admin = db.scalar(select(Admin).where(Admin.username == username)) if username else None
    if admin is None:
        raise unauthorized
    return admin


# ---------- Device API keys ----------
def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    # API keys are long random strings, so a fast SHA-256 hash is appropriate here.
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def authenticate_device(db: Session, device_id: str, api_key: str | None) -> Device:
    """Return the device if the key is valid and the device is active, else raise."""
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if (
        device is None
        or not api_key
        or not hmac.compare_digest(device.api_key_hash, hash_api_key(api_key))
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device credentials")
    if not device.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Device is inactive")
    return device


# ---------- Public tracking tokens ----------
def generate_public_token() -> str:
    return secrets.token_urlsafe(16)
