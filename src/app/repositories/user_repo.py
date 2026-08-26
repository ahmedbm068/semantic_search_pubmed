from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.app.models.user import User


def get_by_email(db: Session, email: str):
    res = db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


def create(db: Session, email: str, hashed_password: str):
    user = User(email=email, password_hash=hashed_password)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise
