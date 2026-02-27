import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.entities.user import User, PasswordResetToken
from app.models.entities.email_config import EmailConfig
from app.schemas.user import PasswordResetRequest, PasswordReset
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/forgot-password")
async def forgot_password(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    settings = get_settings()
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        return {"message": "If email exists, reset link will be sent"}

    token = secrets.token_urlsafe(32)
    db_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add(db_token)
    await db.commit()

    config_result = await db.execute(select(EmailConfig).limit(1))
    config = config_result.scalar_one_or_none()

    if not config:
        logger.warning("No email config found, cannot send reset email")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured"
        )

    try:
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        msg = MIMEMultipart()
        msg["From"] = f"{config.from_name} <{config.from_email}>"
        msg["To"] = user.email
        msg["Subject"] = "Password Reset Request"
        msg.attach(MIMEText(
            f"Click the following link to reset your password:\n\n"
            f"{reset_link}\n\n"
            f"This link will expire in 1 hour.",
            "plain"
        ))

        server = smtplib.SMTP(config.smtp_host, config.smtp_port)
        if config.use_tls:
            server.starttls()
        server.login(config.smtp_user, config.smtp_password)
        server.sendmail(config.from_email, user.email, msg.as_string())
        server.quit()
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send reset email, please try again later"
        )

    return {"message": "If email exists, reset link will be sent"}


@router.post("/reset-password")
async def reset_password(
    data: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == data.token,
            PasswordResetToken.used == False
        )
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )

    if datetime.utcnow() > token_record.expires_at:
        token_record.used = True
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token expired"
        )

    user_result = await db.execute(
        select(User).where(User.id == token_record.user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = get_password_hash(data.new_password)
    token_record.used = True
    await db.commit()

    return {"message": "Password reset successful"}


@router.get("/verify-reset-token")
async def verify_token(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False
        )
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        raise HTTPException(status_code=400, detail="Invalid token")

    if datetime.utcnow() > token_record.expires_at:
        token_record.used = True
        await db.commit()
        raise HTTPException(status_code=400, detail="Token expired")

    return {"valid": True}
