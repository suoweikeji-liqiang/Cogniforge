from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import timedelta
from datetime import datetime

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.core.config import get_settings
from app.models.entities.user import User
from app.schemas.user import UserCreate, UserResponse, Token, UserUpdate, RefreshTokenRequest, LogoutRequest
from app.schemas.problem import ProblemResponse, ProblemCreate, ProblemUpdate
from app.models.entities.user import Problem

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# In-memory token blacklist for logout
_token_blacklist: set = set()
_login_attempts: dict[str, list[datetime]] = {}
_login_blocks: dict[str, datetime] = {}


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None or token in _token_blacklist:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user


def _login_rate_limit_enabled() -> bool:
    return (
        settings.LOGIN_RATE_LIMIT_ATTEMPTS > 0
        and settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS > 0
        and settings.LOGIN_RATE_LIMIT_BLOCK_SECONDS > 0
    )


def _login_limit_keys(username: str, request: Request) -> list[str]:
    client_ip = request.client.host if request.client else "unknown"
    normalized_username = (username or "").strip().lower()
    return [
        f"ip:{client_ip}",
        f"user:{normalized_username}",
        f"ip-user:{client_ip}:{normalized_username}",
    ]


def _prune_login_attempts(now: datetime, key: str) -> list[datetime]:
    window_start = now - timedelta(seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    attempts = [
        ts for ts in _login_attempts.get(key, [])
        if ts >= window_start
    ]
    if attempts:
        _login_attempts[key] = attempts
    else:
        _login_attempts.pop(key, None)
    if _login_blocks.get(key) and _login_blocks[key] <= now:
        _login_blocks.pop(key, None)
    return attempts


def _ensure_login_allowed(username: str, request: Request) -> None:
    if not _login_rate_limit_enabled():
        return

    now = datetime.utcnow()
    for key in _login_limit_keys(username, request):
        blocked_until = _login_blocks.get(key)
        if blocked_until and blocked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later.",
            )

        attempts = _prune_login_attempts(now, key)
        if len(attempts) >= settings.LOGIN_RATE_LIMIT_ATTEMPTS:
            _login_blocks[key] = now + timedelta(seconds=settings.LOGIN_RATE_LIMIT_BLOCK_SECONDS)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later.",
            )


def _register_failed_login(username: str, request: Request) -> None:
    if not _login_rate_limit_enabled():
        return

    now = datetime.utcnow()
    for key in _login_limit_keys(username, request):
        attempts = _prune_login_attempts(now, key)
        attempts.append(now)
        _login_attempts[key] = attempts


def _clear_login_attempts(username: str, request: Request) -> None:
    for key in _login_limit_keys(username, request):
        _login_attempts.pop(key, None)
        _login_blocks.pop(key, None)


def _issue_auth_tokens(user_id: str) -> dict:
    access_token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        data={"sub": user_id},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if this is the first user (admin)
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()
    role = "admin" if user_count == 0 else "user"
    
    # Check for duplicate
    result = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=role,
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    _ensure_login_allowed(form_data.username, request)

    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        _register_failed_login(form_data.username, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    _clear_login_attempts(form_data.username, request)
    
    return _issue_auth_tokens(str(user.id))


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if user_data.email and user_data.email != current_user.email:
        existing = await db.execute(
            select(User).where(User.email == user_data.email, User.id != current_user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = user_data.email

    if user_data.username and user_data.username != current_user.username:
        existing = await db.execute(
            select(User).where(User.username == user_data.username, User.id != current_user.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already in use")
        current_user.username = user_data.username

    if user_data.full_name:
        current_user.full_name = user_data.full_name
    if user_data.password:
        current_user.hashed_password = get_password_hash(user_data.password)

    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    refresh_token_value = payload.refresh_token
    if refresh_token_value in _token_blacklist:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    token_payload = decode_refresh_token(refresh_token_value)
    if token_payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = token_payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    _token_blacklist.add(refresh_token_value)
    return _issue_auth_tokens(str(user.id))


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
):
    if payload.access_token:
        _token_blacklist.add(payload.access_token)
    if payload.refresh_token:
        _token_blacklist.add(payload.refresh_token)
    return {"message": "Logged out successfully"}
