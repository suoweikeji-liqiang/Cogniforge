from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.entities.user import User
from app.models.entities.email_config import EmailConfig
from app.schemas.user import PasswordResetRequest, PasswordReset
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

router = APIRouter(prefix="/auth", tags=["Auth"])

reset_tokens = {}


@router.post("/forgot-password")
async def forgot_password(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user:
        return {"message": "If email exists, reset link will be sent"}
    
    token = secrets.token_urlsafe(32)
    reset_tokens[token] = {
        "user_id": user.id,
        "expires": datetime.utcnow() + timedelta(hours=1)
    }
    
    config_result = await db.execute(select(EmailConfig).limit(1))
    config = config_result.scalar_one_or_none()
    
    if config:
        try:
            reset_link = f"http://localhost:5175/reset-password?token={token}"
            
            msg = MIMEMultipart()
            msg["From"] = f"{config.from_name} <{config.from_email}>"
            msg["To"] = user.email
            msg["Subject"] = "Password Reset Request"
            msg.attach(MIMEText(
                f"Click the following link to reset your password:\n\n{reset_link}\n\n"
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
            print(f"Failed to send email: {e}")
    
    return {"message": "If email exists, reset link will be sent"}


@router.post("/reset-password")
async def reset_password(
    data: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    token_data = reset_tokens.get(data.token)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )
    
    if datetime.utcnow() > token_data["expires"]:
        del reset_tokens[data.token]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token expired"
        )
    
    result = await db.execute(select(User).where(User.id == token_data["user_id"]))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hashed_password = get_password_hash(data.new_password)
    await db.commit()
    
    del reset_tokens[data.token]
    
    return {"message": "Password reset successful"}


@router.get("/verify-reset-token")
async def verify_token(token: str):
    token_data = reset_tokens.get(token)
    
    if not token_data:
        raise HTTPException(status_code=400, detail="Invalid token")
    
    if datetime.utcnow() > token_data["expires"]:
        del reset_tokens[token]
        raise HTTPException(status_code=400, detail="Token expired")
    
    return {"valid": True}
