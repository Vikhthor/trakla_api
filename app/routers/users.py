from fastapi import FastAPI, Query, Path, Depends, HTTPException, status, APIRouter, Header, Form, Body, File, UploadFile
from pydantic import BaseModel, AfterValidator, Field
from enum import Enum
from typing import Annotated, Literal
from fastapi.security import OAuth2PasswordRequestForm
from pwdlib import PasswordHash
import json
import jwt
from datetime import datetime, timedelta, timezone
from uuid import UUID
import secrets, math, random
from ..db import engine, Session, get_db, select, col, or_
from ..models import User, Organization, UserRole, Department, File as FileUpload
from ..utils import FilterParams, get_current_user, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, upload_file, get_datetime
from ..email import sendmail
from ..config import get_settings
from ..redis import RedisWrapper

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
cache = RedisWrapper()
settings = get_settings()

class UserFilterParams(FilterParams):
    organization_id: UUID

class UserModel(BaseModel):
    model_config = {"extra": "forbid"}
    email: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    disabled: bool | None = None
    active: bool | None = None
    customer_id: UUID | None = None
    department_name: str | None = None
    department_id: UUID | None = None
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
    organization_id: UUID | None = None
    organization: OrganizationModel | None = None

class RoleData(BaseModel):
    id: UUID
    role_name: str | None = None

class InviteData(BaseModel):
    email: str
    phone: str | None = None
    first_name: str
    last_name: str
    password: str | None = None
    user_type: str | None = "system"
    image: str | None = None
    address: str | None = None
    active: bool | None = None
    disabled: bool | None = None
    customer_id: UUID | None = None
    department_name: str | None = None
    organization_id: UUID
    roles: list[RoleData] | None = None


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
    user.last_login = get_datetime()
    user.is_online = True # TODO: Use websocket
    db.add(user)
    db.commit()
    db.refresh(user)
    user_data = {
        **user.model_dump(),
        "image": "" if not user.image else user.image.file_name
    }
    return {"access_token": access_token, "token_type": "bearer", "user": user_data}

@router.get("/me")
async def get_session_user(current_user: Annotated[UserModel, Depends(get_current_user)]):
    user_data = {
        **current_user.model_dump(),
        "image": "" if not current_user.image else current_user.image.file_name
    }
    return user_data

@router.get("/otp")
async def request_otp(email: Annotated[str, Query(title="User email")]):
    """
    Generate and send OTP to user email
    """
    tmp_id_length = 10
    tmp_id = secrets.token_hex(math.ceil(tmp_id_length / 2))[:tmp_id_length]
    otp = ''.join(random.sample(['1','2','3','4','5','6','7','8','9','0'],6))

    cache.set_value(f"otp:{tmp_id}", otp, expires_in_sec=300)

    sendmail(
        recipients=email,
        subject="Trakla OTP",
        message=f"Your verification OTP is {otp}", 
        delayed=False
    )
    return {'tmp_id': tmp_id}

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
    user_data: Annotated[InviteData, Body()],
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
        Create new user
    """
    roles = []
    user_roles = user_data.roles or []
    for user_role in user_roles:
        role = db.exec(select(UserRole).where(UserRole.id == user_role.id).first())
        if role:
            roles.append(role)

    department = None
    if user_data.department_name:
        statement = select(Department).where(
            Department.organization_id == current_user.organization_id,
            Department.department_name == user_data.department_name
        )
        department = db.exec(statement).first()
        if not department:
            department = Department(
                department_name = user_data.department_name,
                organization_id = current_user.organization_id,
                owner_id=current_user.id,
                modifier_id=current_user.id,
                created_at=get_datetime(),
                updated_at=get_datetime()
            )

    full_name = user_data.first_name
    if user_data.last_name:
        full_name = f"{user_data.first_name} {user_data.last_name}"
    
    user = User(
        first_name = user_data.first_name,
        last_name = user_data.last_name,
        full_name = full_name,
        email = user_data.email,
        phone = user_data.phone,
        address = user_data.address,
        image = user_data.image,
        user_type = user_data.user_type,
        disabled = user_data.disabled,
        active = user_data.active or False,
        roles = roles,
        customer_id = user_data.customer_id,
        department = department,
        organization_id = user_data.organization_id,
        password = get_password_hash(user_data.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        email_args = {
            "app_name": "Trakla",
            "organization_name": current_user.organization.organization_name,
            "invitee_name": full_name,
            "inviter_name": current_user.full_name,
            "invite_url": f"{settings.app_url}/auth/password-reset?user_id={user_data.email}",
            "expires_in": "48 hours",
            "company_address": current_user.organization.address or "",
        }
        sendmail(
            recipients=user_data.email,
            subject=f"You're invited to join {current_user.organization.organization_name}",
            template="user_invite",
            args=email_args,
            delayed=False
        )
    except Exception as e:
        pass

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
    #TODO: Send invite email to user
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
        **user.model_dump(),
        "image": "" if not user.image else user.image.file_name,
        "department": user.department,
        "roles": user.roles,
        "created_by": user.created_by
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
    user_id: Annotated[str, Path(title="The ID of the user to update")],
    user: UserModel,
    db: Annotated[Session, Depends(get_db)]
):
    """
        Update single user
    """
    current_user = None
    try:
        current_user = db.get(User, UUID(user_id))
    except ValueError:
        current_user = db.exec(select(User).where(or_(
            User.email == user_id,
            User.phone == user_id
        ))).first()

    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
    user_dict = user.model_dump(exclude_unset=True)
    otp = user_dict.pop('otp', None)
    tmp_id = user_dict.pop('tmp_id', None)
    is_verified = False
    if otp and tmp_id:
        stored_otp = cache.get_value(f"otp:{tmp_id}")
        if stored_otp != otp:
            raise HTTPException(status_code=403, detail="Invalid OTP")
        is_verified = True

    for k, v in user_dict.items():
        if k == 'organization_id':
            continue
        if k in ['email', 'phone', 'password'] and not is_verified:
            continue
        if k == 'password':
            v = get_password_hash(v)
        if k == 'roles':
            roles = []
            user_roles = v or []
            for user_role in user_roles:
                role = db.exec(select(UserRole).where(UserRole.id == user_role.id).first())
                if role:
                    roles.append(role)
            v = roles
        if k == "department_name":
            statement = select(Department).where(
                Department.organization_id == current_user.organization_id,
                Department.department_name == v
            )
            department = db.exec(statement).first()
            if not department:
                department = Department(
                    department_name = v,
                    organization_id = current_user.organization_id,
                    owner_id=current_user.id,
                    modifier_id=current_user.id,
                    created_at=get_datetime(),
                    updated_at=get_datetime()
                )
            current_user.department = department
            continue
        current_user.sqlmodel_update({k: v})

    full_name = f"{current_user.first_name} {current_user.last_name}"
    current_user.full_name = full_name
    current_user.updated_at = get_datetime()
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    resp_data = {
        **current_user.model_dump(),
        "image": "" if not current_user.image else current_user.image.file_name,
        "department": current_user.department,
        "roles": current_user.roles,
        "created_by": current_user.created_by
    }
    
    return resp_data

@router.put("/upload-image/{user_id}", status_code=status.HTTP_200_OK)
async def upload_profile_image(
    user_id: Annotated[UUID, Path(title="The ID of the user to update")],
    image: Annotated[UploadFile, File(description="User profile image")],
    session_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """
    Upload profile image
    """
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    current_user = db.get(User, user_id)
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    file_data = upload_file(image)
    # image_url = file_data.get('url')

    file_upload = FileUpload(
        file_name = file_data.get("filename"),
        file_type = file_data.get("file_type"),
        file_size = file_data.get("file_size"),
        formated_size = file_data.get("formated_size"),
        file_url = file_data.get("url"),
        record_type = "User",
        record_id = current_user.id,
        record_field = "image",
        owner_id = session_user.id
    )
    db.add(file_upload)
    
    # current_user.image = image_url
    current_user.updated_at = get_datetime()
    current_user.modifier_id = session_user.id
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    resp_data = {
        **current_user.model_dump(),
        "image": "" if not current_user.image else current_user.image.file_name,
        "department": current_user.department,
        "roles": current_user.roles,
        "created_by": current_user.created_by
    }
    return resp_data