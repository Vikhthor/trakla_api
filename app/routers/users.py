from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header, Form, Body
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
from fastapi.security import OAuth2PasswordRequestForm
from pwdlib import PasswordHash
import jwt
from datetime import datetime, timedelta, timezone
from uuid import UUID
import secrets, math, random
from ..db import engine, Session, get_db, select, col, or_
from ..models import User, Organization
from ..utils import FilterParams, get_current_user, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

class UserFilterParams(FilterParams):
    organization_id: UUID

class UserModel(BaseModel):
    model_config = {"extra": "forbid"}
    email: str | None = None
    phone: str
    first_name: str | None = None
    last_name: str | None = None
    disabled: bool | None = None
    password: str | None = None
    otp: str | None = None
    tmp_id: str | None = None

class OrganizationModel(BaseModel):
    organization_name: str
    address: str
    city: str
    state: str
    country: str

class SignUpData(BaseModel):
    email: str
    phone: str | None = None
    first_name: str
    last_name: str
    otp: str
    tmp_id: str
    password: str
    user_type: str | None = "system"
    address: str | None = None
    organization_id: str | None = None
    organization: OrganizationModel | None = None

class InviteData(BaseModel):
    email: str
    phone: str | None = None
    first_name: str
    last_name: str
    password: str | None
    user_type: str | None = "system"
    address: str | None = None
    organization_id: str


router = APIRouter(
    prefix="/v1/users",
    tags=["users"],
    # dependencies=[Depends(get_token_header)],
    responses={404: {"description": "User not found"}},
)

password_hash = PasswordHash.recommended()

def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)

def get_password_hash(password):
    if password:
        return password_hash.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)]
):
    statement = select(User).where(User.email == form_data.username)
    user = db.exec(statement).first()
    if not user:
        # Prevent timing attacks that could be used to enumerate existing usernames.
        DUMMY_HASH = password_hash.hash("dummypassword")
        verify_password(form_data.password, DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user.password):
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user}

@router.get("/me")
async def get_session_user(current_user: Annotated[UserModel, Depends(get_current_user)]):
    return current_user

@router.get("/otp")
async def request_otp(email: Annotated[str, Query(title="User email")]):
    """
    Generate and send OTP to user email
    """
    tmp_id_length = 10
    tmp_id = secrets.token_hex(math.ceil(tmp_id_length / 2))[:tmp_id_length]
    otp = ''.join(random.sample(['1','2','3','4','5','6','7','8','9','0'],6))
    return {'tmp_id': tmp_id, 'otp': otp} # TODO set OTP in cache and do not return it

@router.post("/signup")
async def signup_user(
    form_data: Annotated[SignUpData, Body()],
    db: Annotated[Session, Depends(get_db)]
):
    """
        Create new customer
    """
    # TODO verify form_data.otp with form_data.tmp_id
    full_name = form_data.first_name
    if form_data.last_name:
        full_name = f"{form_data.first_name} {form_data.last_name}"
    user = User(
        first_name = form_data.first_name,
        last_name = form_data.last_name,
        full_name = full_name,
        email = form_data.email,
        phone = form_data.phone,
        address = form_data.address,
        user_type = form_data.user_type,
        organization_id = form_data.organization_id,
        organization = Organization(**form_data.organization.model_dump()),
        password = get_password_hash(form_data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "address": user.address,
        "user_type": user.user_type,
        "organization_id": user.organization_id,
        "disabled": user.disabled,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }
    return user_data

@router.post("/invite")
async def invite_user(
    form_data: Annotated[InviteData, Form()],
    db: Annotated[Session, Depends(get_db)]
):
    """
        Create new customer
    """
    # TODO verify form_data.otp with form_data.tmp_id
    user = User(
        first_name = form_data.first_name,
        last_name = form_data.last_name,
        email = form_data.email,
        phone = form_data.phone,
        address = form_data.address,
        user_type = form_data.user_type,
        organization_id = form_data.organization_id,
        password = get_password_hash(form_data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "address": user.address,
        "user_type": user.user_type,
        "organization_id": user.organization_id,
        "active": False,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }
    return user_data

@router.get("/")
async def get_users(
    filter_query: Annotated[UserFilterParams, Query()],
    db: Annotated[Session, Depends(get_db)]
):
    """
        Get filtered users
    """
    limit = filter_query.limit
    offset = filter_query.offset
    if filter_query.page and not offset:
        offset = limit*(filter_query.page - 1)
    statement = select(User).offset(offset).limit(limit)
    users = db.exec(statement).all()
    users_data = [{
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "address": user.address,
        "user_type": user.user_type,
        "organization_id": user.organization_id,
        "disabled": user.disabled,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    } for user in users]
    return users_data

@router.get("/{user_id}")
async def get_user(
    user_id: Annotated[UUID, Path(title="The ID of the user to get")],
    db: Annotated[Session, Depends(get_db)]
):
    """
        Get single user
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user_data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "address": user.address,
        "user_type": user.user_type,
        "organization_id": user.organization_id,
        "disabled": user.disabled,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }
    return user_data

@router.put("/{user_id}")
async def update_user(
    user_id: Annotated[int, Path(title="The ID of the user to update")],
    user: UserModel,
    db: Annotated[Session, Depends(get_db)]
):
    """
        Update single user
    """
    current_user = db.get(User, user_id)
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
    user_dict = user.model_dump(exclude_unset=True)
    otp = user_dict.pop('otp', None)
    tmp_id = user_dict.pop('tmp_id', None)

    for k, v in user_dict.items():
        if k == 'organization_id':
            continue
        if k in ['email', 'phone']:
            pass # TODO verify user.otp with user.tmp_id
        if k == 'password_reset_id':
            continue
        if k == 'password':
            pass # TODO check password_reset_id embedded in email link is valid (email can be sent in OTP request)
        current_user.sqlmodel_update({k: v})

    full_name = user_dict.get("first_name")
    if user_dict.get("last_name"):
        full_name = f"{user_dict.get("first_name")} {user_dict.get("last_name")}"
    current_user.full_name = full_name
    current_user.updated_at = str(datetime.now())
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user