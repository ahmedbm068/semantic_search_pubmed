from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from src.app.core.security import decode_token
from src.app.deps.db import get_db
from src.app.repositories.user_repo import get_by_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except JWTError:
        raise credentials_exception

    if not isinstance(payload, dict):
        raise credentials_exception

    email = payload.get("sub")
    if not email or not isinstance(email, str):
        raise credentials_exception

    user = get_by_email(db, email)
    if not user:
        raise credentials_exception

    return user
