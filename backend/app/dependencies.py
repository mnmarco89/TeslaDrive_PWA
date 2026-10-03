from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import UserToken


def get_current_token(db: Session = Depends(get_db)):
    token = db.query(UserToken).order_by(UserToken.id.desc()).first()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token
