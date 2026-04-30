from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas

SECRET_KEY = "CAMBIA_ESTO_EN_PRODUCCION_32chars!!"
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

bearer = HTTPBearer()


# ── PASSWORDS ─────────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> schemas.TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        return schemas.TokenData(user_id=user_id)
    except (JWTError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── DEPENDENCIES ──────────────────────────────────────────────────────────────
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.User:
    token_data = decode_token(credentials.credentials)
    user = db.get(models.User, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario inactivo o no encontrado")
    return user

def require_admin(current: models.User = Depends(get_current_user)) -> models.User:
    if current.role != models.RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Se requiere rol admin")
    return current

def require_profesor_or_admin(current: models.User = Depends(get_current_user)) -> models.User:
    if current.role == models.RoleEnum.estudiante:
        raise HTTPException(status_code=403, detail="Acceso no autorizado")
    return current