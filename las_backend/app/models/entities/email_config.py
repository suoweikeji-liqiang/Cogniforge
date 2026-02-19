from sqlalchemy import Column, String, Integer, Boolean
from app.core.database import Base


class EmailConfig(Base):
    __tablename__ = "email_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    smtp_host = Column(String(200), nullable=False)
    smtp_port = Column(Integer, nullable=False)
    smtp_user = Column(String(200), nullable=False)
    smtp_password = Column(String(200), nullable=False)
    from_email = Column(String(200), nullable=False)
    from_name = Column(String(100))
    use_tls = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
