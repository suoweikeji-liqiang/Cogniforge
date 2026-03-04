from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.entities.user import LoginThrottle, Problem, RevokedToken, User
from app.schemas.problem import ProblemCreate, ProblemResponse, ProblemUpdate
from app.schemas.user import (
    LogoutRequest,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserResponse,
    UserUpdate,
)

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def _is_token_revoked(db: AsyncSession, token: Optional[str]) -> bool:
    if not token:
        return False
    result = await db.execute(
        select(RevokedToken.id).where(RevokedToken.token == token)
    )
    return result.scalar_one_or_none() is not None


def _extract_token_expiry(payload: Optional[dict]) -> Optional[datetime]:
    if not payload:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return None
    return datetime.utcfromtimestamp(exp)


async def _revoke_token(
    db: AsyncSession,
    token: Optional[str],
    token_type: str,
    payload: Optional[dict] = None,
) -> None:
    if not token or await _is_token_revoked(db, token):
        return

    db.add(
        RevokedToken(
            token=token,
            token_type=token_type,
            expires_at=_extract_token_expiry(payload),
        )
    )


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
    if payload is None or await _is_token_revoked(db, token):
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


def _extract_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _login_limit_keys(username: str, request: Request) -> list[str]:
    client_ip = _extract_client_ip(request)
    normalized_username = (username or "").strip().lower()
    return [
        f"ip:{client_ip}",
        f"user:{normalized_username}",
        f"ip-user:{client_ip}:{normalized_username}",
    ]


async def _get_login_throttle(db: AsyncSession, key: str) -> Optional[LoginThrottle]:
    result = await db.execute(
        select(LoginThrottle).where(LoginThrottle.scope_key == key)
    )
    return result.scalar_one_or_none()


async def _ensure_login_allowed(username: str, request: Request, db: AsyncSession) -> None:
    if not _login_rate_limit_enabled():
        return

    now = datetime.utcnow()
    for key in _login_limit_keys(username, request):
        throttle = await _get_login_throttle(db, key)
        if throttle and throttle.blocked_until and throttle.blocked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please try again later.",
            )


async def _register_failed_login(username: str, request: Request, db: AsyncSession) -> None:
    if not _login_rate_limit_enabled():
        return

    now = datetime.utcnow()
    client_ip = _extract_client_ip(request)
    window_start = now - timedelta(seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    normalized_username = (username or "").strip().lower() or None

    for key in _login_limit_keys(username, request):
        throttle = await _get_login_throttle(db, key)
        if throttle is None:
            throttle = LoginThrottle(
                scope_key=key,
                username=normalized_username,
                client_ip=client_ip,
                failed_count=0,
                window_started_at=now,
            )
            db.add(throttle)

        if throttle.window_started_at < window_start:
            throttle.failed_count = 0
            throttle.window_started_at = now
            throttle.blocked_until = None

        throttle.username = normalized_username
        throttle.client_ip = client_ip
        throttle.failed_count += 1

        if throttle.failed_count >= settings.LOGIN_RATE_LIMIT_ATTEMPTS:
            throttle.blocked_until = now + timedelta(
                seconds=settings.LOGIN_RATE_LIMIT_BLOCK_SECONDS
            )


async def _clear_login_attempts(username: str, request: Request, db: AsyncSession) -> None:
    await db.execute(
        delete(LoginThrottle).where(
            LoginThrottle.scope_key.in_(_login_limit_keys(username, request))
        )
    )


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
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()
    role = "admin" if user_count == 0 else "user"

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
    await _ensure_login_allowed(form_data.username, request, db)

    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        await _register_failed_login(form_data.username, request, db)
        await db.commit()
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

    await _clear_login_attempts(form_data.username, request, db)
    await db.commit()

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
    if await _is_token_revoked(db, refresh_token_value):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    token_payload = decode_refresh_token(refresh_token_value)
    if token_payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = token_payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    await _revoke_token(db, refresh_token_value, "refresh", token_payload)
    await db.commit()
    return _issue_auth_tokens(str(user.id))


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    if payload.access_token:
        await _revoke_token(
            db,
            payload.access_token,
            "access",
            decode_access_token(payload.access_token),
        )
    if payload.refresh_token:
        await _revoke_token(
            db,
            payload.refresh_token,
            "refresh",
            decode_refresh_token(payload.refresh_token),
        )
    await db.commit()
    return {"message": "Logged out successfully"}


@router.get("/problems", response_model=list[ProblemResponse])
async def get_user_problems(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem).where(Problem.user_id == current_user.id)
    )
    return list(result.scalars().all())


@router.post("/problems", response_model=ProblemResponse)
async def create_user_problem(
    problem_data: ProblemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    problem = Problem(
        user_id=current_user.id,
        title=problem_data.title,
        description=problem_data.description,
        associated_concepts=problem_data.associated_concepts,
    )
    db.add(problem)
    await db.commit()
    await db.refresh(problem)
    return problem


@router.put("/problems/{problem_id}", response_model=ProblemResponse)
async def update_user_problem(
    problem_id: str,
    problem_data: ProblemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Problem).where(
            Problem.id == problem_id,
            Problem.user_id == current_user.id,
        )
    )
    problem = result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    if problem_data.title is not None:
        problem.title = problem_data.title
    if problem_data.description is not None:
        problem.description = problem_data.description
    if problem_data.associated_concepts is not None:
        problem.associated_concepts = problem_data.associated_concepts
    if problem_data.status is not None:
        problem.status = problem_data.status

    await db.commit()
    await db.refresh(problem)
    return problem
