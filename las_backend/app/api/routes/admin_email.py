from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.database import get_db
from app.models.entities.email_config import EmailConfig
from app.models.entities.user import User
from app.api.routes.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/admin/email-config", tags=["Admin"])


class EmailConfigSchema(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    from_name: str = "Learning Assistant"
    use_tls: bool = True
    is_active: bool = True


class TestEmailSchema(BaseModel):
    to_email: str


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("")
async def get_email_config(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(select(EmailConfig).limit(1))
    config = result.scalar_one_or_none()
    if config:
        return {
            "smtp_host": config.smtp_host,
            "smtp_port": config.smtp_port,
            "smtp_user": config.smtp_user,
            "from_email": config.from_email,
            "from_name": config.from_name,
            "use_tls": config.use_tls,
            "is_active": config.is_active,
        }
    return None


@router.put("")
async def update_email_config(
    config: EmailConfigSchema,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(select(EmailConfig).limit(1))
    db_config = result.scalar_one_or_none()
    
    if db_config:
        db_config.smtp_host = config.smtp_host
        db_config.smtp_port = config.smtp_port
        db_config.smtp_user = config.smtp_user
        db_config.smtp_password = config.smtp_password
        db_config.from_email = config.from_email
        db_config.from_name = config.from_name
        db_config.use_tls = config.use_tls
        db_config.is_active = config.is_active
    else:
        db_config = EmailConfig(**config.dict())
        db.add(db_config)
    
    await db.commit()
    return {"status": "success"}


@router.post("/test")
async def test_email(
    data: TestEmailSchema,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(select(EmailConfig).limit(1))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=400, detail="Email config not set")
    
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{config.from_name} <{config.from_email}>"
        msg["To"] = data.to_email
        msg["Subject"] = "Test Email"
        msg.attach(MIMEText("This is a test email from Learning Assistant System.", "plain"))
        
        server = smtplib.SMTP(config.smtp_host, config.smtp_port)
        if config.use_tls:
            server.starttls()
        server.login(config.smtp_user, config.smtp_password)
        server.sendmail(config.from_email, data.to_email, msg.as_string())
        server.quit()
        
        return {"status": "success", "message": "Test email sent"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send email: {str(e)}")
