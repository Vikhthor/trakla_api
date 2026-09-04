from pydantic import BaseModel, Field
from typing import Annotated, Literal
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
from .db import Session, get_db, select, col, or_
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class FilterParams(BaseModel):
    model_config = {"extra": "forbid"} # optionally restrict the query parameters that you want to receive. Here, if a client tries to send some extra data in the query parameters, they will receive an error response.
    limit: int | None = Field(100, gt=0, le=100)
    offset: int | None = Field(0, ge=0)
    page: int | None = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] | None = "created_at"
    tags: list[str] | None = []
    search: str | None = None

# openssl rand -hex 32
SECRET_KEY = "4463234cf682cd70cdc0e87601d321e1dd0474741db08e9379d8a82c9324c4dd"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    statement = select(User).where(User.email == email)
    user = db.exec(statement).first()
    if user is None:
        raise credentials_exception
    if user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user