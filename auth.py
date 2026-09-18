# auth.py — secure login: password hashing (bcrypt) + tokens (JWT)
# Users are now stored in Supabase (a real cloud database).

from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

import db   # our Supabase connection

SECRET = "change-me-to-a-long-random-string"
ALGORITHM = "HS256"
TOKEN_MINUTES = 60

oauth2 = OAuth2PasswordBearer(tokenUrl="/login", auto_error=False)


def _hash(pw):
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(plain, hashed):
    try:
        return bcrypt.checkpw(plain.encode()[:72], hashed.encode())
    except Exception:
        return False


def register_user(username, password, role):
    """Add a brand-new user to the database. Returns (ok, message)."""
    username = (username or "").strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(password or "") < 6:
        return False, "Password must be at least 6 characters"
    if role not in ("issuer", "investor"):
        return False, "Role must be issuer or investor"
    if db.get_user(username):
        return False, "That username is already taken"
    db.create_user(username, _hash(password), role)
    return True, "Account created"


def login_user(username, password):
    """Check credentials against the database. Returns the user row or None."""
    user = db.get_user(username)
    if not user or not verify_password(password, user["password_hash"]):
        return None
    return user


def create_token(username, role):
    now = datetime.now(timezone.utc)
    payload = {"sub": username, "role": role, "exp": now + timedelta(minutes=TOKEN_MINUTES)}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2)):
    """FastAPI dependency: rejects anyone without a valid token."""
    err = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not logged in or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise err
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise err
    username = payload.get("sub")
    if not username:
        raise err
    return {"username": username, "role": payload.get("role")}