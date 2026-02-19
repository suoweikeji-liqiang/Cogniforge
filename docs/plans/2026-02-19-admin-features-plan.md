# 管理员功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现完整的管理员功能，包括用户管理、LLM配置、邮件配置、找回密码，支持中英文双语

**Architecture:** 
- 后端：扩展 User 模型添加 role 字段，新增 EmailConfig/SystemSettings 模型，新增管理员 API
- 前端：新增 /admin 路由页面，集成 vue-i18n 实现国际化

**Tech Stack:** FastAPI, SQLAlchemy, Vue3, Pinia, vue-i18n, SMTP

---

## 阶段 1：后端 - 数据库和模型

### Task 1: 修改用户模型添加 role 字段

**Files:**
- Modify: `las_backend/app/models/entities/user.py:16`

**Step 1: 添加 role 字段**

```python
# 在 User 类中添加
role = Column(String(20), default="user")  # "admin" 或 "user"
```

**Step 2: 验证模型**

```bash
cd las_backend && python -c "from app.models.entities.user import User; print('User model OK')"
```
Expected: 输出 "User model OK"

---

### Task 2: 创建邮件配置模型

**Files:**
- Create: `las_backend/app/models/entities/email_config.py`

**Step 1: 创建模型文件**

```python
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
```

**Step 2: 验证模型**

```bash
cd las_backend && python -c "from app.models.entities.email_config import EmailConfig; print('EmailConfig model OK')"
```
Expected: 输出 "EmailConfig model OK"

---

### Task 3: 创建系统设置模型

**Files:**
- Create: `las_backend/app/models/entities/system_settings.py`

**Step 1: 创建模型文件**

```python
from sqlalchemy import Column, String, Integer, JSON, Text
from app.core.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON)
    description = Column(Text)
```

**Step 2: 验证模型**

```bash
cd las_backend && python -c "from app.models.entities.system_settings import SystemSettings; print('SystemSettings model OK')"
```
Expected: 输出 "SystemSettings model OK"

---

### Task 4: 注册新模型到数据库

**Files:**
- Modify: `las_backend/app/models/entities/__init__.py`

**Step 1: 添加导出**

```python
from app.models.entities.user import User, Problem, ModelCard, EvolutionLog, Conversation, PracticeTask, PracticeSubmission, Review
from app.models.entities.email_config import EmailConfig
from app.models.entities.system_settings import SystemSettings

__all__ = ["User", "Problem", "ModelCard", "EvolutionLog", "Conversation", "PracticeTask", "PracticeSubmission", "Review", "EmailConfig", "SystemSettings"]
```

**Step 2: 创建数据库表**

```bash
cd las_backend && python -c "
import asyncio
from app.core.database import engine, Base
from app.models.entities import *

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Database tables created')

asyncio.run(init_db())
"
```
Expected: 成功创建表，无错误

---

## 阶段 2：后端 - API 接口

### Task 5: 修改用户注册逻辑（第一个用户为管理员）

**Files:**
- Modify: `las_backend/app/api/routes/auth.py:49-75`

**Step 1: 修改 register 函数**

```python
from sqlalchemy import select, func

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # 检查是否已有用户
    result = await db.execute(select(func.count(User.id)))
    user_count = result.scalar()
    
    # 第一个用户设为管理员
    role = "admin" if user_count == 0 else "user"
    
    # 检查重复
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
        role=role,  # 添加 role
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    return db_user
```

**Step 2: 测试注册**

```bash
curl -X POST http://127.0.0.1:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","username":"admin","password":"admin123","full_name":"Admin User"}'
```
Expected: 返回用户信息，role 为 "admin"

---

### Task 6: 创建管理员路由 - 用户管理

**Files:**
- Create: `las_backend/app/api/routes/admin_users.py`

**Step 1: 创建管理员用户管理路由**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.entities.user import User
from app.schemas.user import UserResponse, UserUpdate, UserAdminUpdate
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/admin/users", tags=["Admin"])


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_data.email:
        user.email = user_data.email
    if user_data.username:
        user.username = user_data.username
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.role:
        user.role = user_data.role
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.password:
        user.hashed_password = get_password_hash(user_data.password)
    
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    return None
```

**Step 2: 添加 Schema**

修改 `las_backend/app/schemas/user.py`:

```python
class UserAdminUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)
```

---

### Task 7: 创建管理员路由 - LLM 配置

**Files:**
- Create: `las_backend/app/api/routes/admin_llm.py`

**Step 1: 创建 LLM 配置路由**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.entities.system_settings import SystemSettings
from app.models.entities.user import User
from app.api.routes.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/admin/llm-config", tags=["Admin"])


class LLMConfigSchema(BaseModel):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    default_provider: str = "openai"


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("")
async def get_llm_config(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "llm_config")
    )
    config = result.scalar_one_or_none()
    if config:
        return config.value
    return LLMConfigSchema().dict()


@router.put("")
async def update_llm_config(
    config: LLMConfigSchema,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "llm_config")
    )
    db_config = result.scalar_one_or_none()
    
    if db_config:
        db_config.value = config.dict()
    else:
        db_config = SystemSettings(
            key="llm_config",
            value=config.dict(),
            description="LLM provider configuration"
        )
        db.add(db_config)
    
    await db.commit()
    return {"status": "success", "config": config.dict()}
```

---

### Task 8: 创建管理员路由 - 邮件配置

**Files:**
- Create: `las_backend/app/api/routes/admin_email.py`

**Step 1: 创建邮件配置路由**

```python
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
        # 不返回密码
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
```

---

### Task 9: 创建统计信息 API

**Files:**
- Modify: `las_backend/app/api/routes/admin_users.py` (添加)

**Step 1: 添加统计接口**

```python
@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    from sqlalchemy import func
    from app.models.entities.user import Problem, ModelCard, Conversation
    
    # 统计用户数
    user_count = await db.execute(select(func.count(User.id)))
    users = user_count.scalar()
    
    # 统计问题数
    problem_count = await db.execute(select(func.count(Problem.id)))
    problems = problem_count.scalar()
    
    # 统计模型卡数
    model_count = await db.execute(select(func.count(ModelCard.id)))
    models = model_count.scalar()
    
    # 统计对话数
    conv_count = await db.execute(select(func.count(Conversation.id)))
    conversations = conv_count.scalar()
    
    return {
        "users": users,
        "problems": problems,
        "model_cards": models,
        "conversations": conversations,
    }
```

---

### Task 10: 创建找回密码 API

**Files:**
- Create: `las_backend/app/api/routes/password_reset.py`

**Step 1: 创建密码重置路由**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from uuid import uuid4
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

# 存储重置 token（生产环境应存数据库）
reset_tokens = {}


@router.post("/forgot-password")
async def forgot_password(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user:
        # 不暴露用户是否存在
        return {"message": "If email exists, reset link will be sent"}
    
    # 生成 token
    token = secrets.token_urlsafe(32)
    reset_tokens[token] = {
        "user_id": user.id,
        "expires": datetime.utcnow() + timedelta(hours=1)
    }
    
    # 获取邮件配置
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
    
    # 删除 token
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
```

**Step 2: 添加 Schema**

修改 `las_backend/app/schemas/user.py`:

```python
class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)
```

---

### Task 11: 注册管理员路由

**Files:**
- Modify: `las_backend/app/api/__init__.py`

**Step 1: 添加路由**

```python
from fastapi import APIRouter
from app.api.routes import auth, problems, model_cards, conversations, practice
from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.admin_llm import router as admin_llm_router
from app.api.routes.admin_email import router as admin_email_router
from app.api.routes.password_reset import router as password_reset_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(password_reset_router)
api_router.include_router(problems.router)
api_router.include_router(model_cards.router)
api_router.include_router(conversations.router)
api_router.include_router(practice.router)
api_router.include_router(practice.router_reviews)

# Admin routes
api_router.include_router(admin_users_router)
api_router.include_router(admin_llm_router)
api_router.include_router(admin_email_router)
```

---

## 阶段 3：前端 - 管理页面

### Task 12: 安装 vue-i18n

**Files:**
- Modify: `las_frontend/package.json`

**Step 1: 添加依赖**

```bash
cd las_frontend && npm install vue-i18n@9
```

---

### Task 13: 创建 i18n 配置

**Files:**
- Create: `las_frontend/src/locales/en.json`
- Create: `las_frontend/src/locales/zh.json`
- Create: `las_frontend/src/i18n/index.ts`

**Step 1: 创建英文语言文件**

```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "edit": "Edit",
    "add": "Add",
    "search": "Search",
    "loading": "Loading...",
    "success": "Success",
    "error": "Error",
    "confirm": "Confirm",
    "actions": "Actions"
  },
  "nav": {
    "dashboard": "Dashboard",
    "problems": "Problems",
    "modelCards": "Model Cards",
    "practice": "Practice",
    "reviews": "Reviews",
    "chat": "Chat",
    "admin": "Admin",
    "logout": "Logout",
    "login": "Login",
    "register": "Register"
  },
  "admin": {
    "title": "Admin Panel",
    "users": "User Management",
    "llmConfig": "LLM Configuration",
    "emailConfig": "Email Configuration",
    "stats": "Statistics",
    "statsUsers": "Total Users",
    "statsProblems": "Total Problems",
    "statsModels": "Total Model Cards",
    "statsConversations": "Total Conversations"
  },
  "users": {
    "email": "Email",
    "username": "Username",
    "fullName": "Full Name",
    "role": "Role",
    "admin": "Admin",
    "user": "User",
    "status": "Status",
    "active": "Active",
    "inactive": "Inactive",
    "createdAt": "Created At",
    "resetPassword": "Reset Password",
    "changeRole": "Change Role",
    "newPassword": "New Password",
    "confirmDelete": "Are you sure you want to delete this user?"
  },
  "llm": {
    "openaiKey": "OpenAI API Key",
    "openaiModel": "OpenAI Model",
    "anthropicKey": "Anthropic API Key",
    "anthropicModel": "Anthropic Model",
    "defaultProvider": "Default Provider",
    "saveSuccess": "LLM configuration saved"
  },
  "email": {
    "smtpHost": "SMTP Host",
    "smtpPort": "SMTP Port",
    "smtpUser": "SMTP User",
    "smtpPassword": "SMTP Password",
    "fromEmail": "From Email",
    "fromName": "From Name",
    "useTLS": "Use TLS",
    "testEmail": "Test Email",
    "testSuccess": "Test email sent successfully",
    "saveSuccess": "Email configuration saved"
  },
  "auth": {
    "forgotPassword": "Forgot Password?",
    "resetPassword": "Reset Password",
    "sendResetLink": "Send Reset Link",
    "passwordResetSuccess": "Password reset successful",
    "loginRequired": "Please login"
  }
}
```

**Step 2: 创建中文语言文件**

```json
{
  "common": {
    "save": "保存",
    "cancel": "取消",
    "delete": "删除",
    "edit": "编辑",
    "add": "添加",
    "search": "搜索",
    "loading": "加载中...",
    "success": "成功",
    "error": "错误",
    "confirm": "确认",
    "actions": "操作"
  },
  "nav": {
    "dashboard": "仪表盘",
    "problems": "问题",
    "modelCards": "模型卡",
    "practice": "练习",
    "reviews": "复习",
    "chat": "对话",
    "admin": "管理",
    "logout": "退出登录",
    "login": "登录",
    "register": "注册"
  },
  "admin": {
    "title": "管理面板",
    "users": "用户管理",
    "llmConfig": "LLM 配置",
    "emailConfig": "邮件配置",
    "stats": "统计",
    "statsUsers": "用户总数",
    "statsProblems": "问题总数",
    "statsModels": "模型卡总数",
    "statsConversations": "对话总数"
  },
  "users": {
    "email": "邮箱",
    "username": "用户名",
    "fullName": "姓名",
    "role": "角色",
    "admin": "管理员",
    "user": "普通用户",
    "status": "状态",
    "active": "激活",
    "inactive": "未激活",
    "createdAt": "创建时间",
    "resetPassword": "重置密码",
    "changeRole": "修改角色",
    "newPassword": "新密码",
    "confirmDelete": "确定要删除这个用户吗？"
  },
  "llm": {
    "openaiKey": "OpenAI API 密钥",
    "openaiModel": "OpenAI 模型",
    "anthropicKey": "Anthropic API 密钥",
    "anthropicModel": "Anthropic 模型",
    "defaultProvider": "默认供应商",
    "saveSuccess": "LLM 配置已保存"
  },
  "email": {
    "smtpHost": "SMTP 服务器",
    "smtpPort": "SMTP 端口",
    "smtpUser": "SMTP 用户名",
    "smtpPassword": "SMTP 密码",
    "fromEmail": "发送邮箱",
    "fromName": "发送名称",
    "useTLS": "使用 TLS",
    "testEmail": "测试邮件",
    "testSuccess": "测试邮件发送成功",
    "saveSuccess": "邮件配置已保存"
  },
  "auth": {
    "forgotPassword": "忘记密码？",
    "resetPassword": "重置密码",
    "sendResetLink": "发送重置链接",
    "passwordResetSuccess": "密码重置成功",
    "loginRequired": "请先登录"
  }
}
```

**Step 3: 创建 i18n 配置**

```typescript
import { createI18n } from 'vue-i18n'
import en from '../locales/en.json'
import zh from '../locales/zh.json'

const i18n = createI18n({
  legacy: false,
  locale: navigator.language.startsWith('zh') ? 'zh' : 'en',
  fallbackLocale: 'en',
  messages: {
    en,
    zh
  }
})

export default i18n
```

---

### Task 14: 更新 auth store 支持 role

**Files:**
- Modify: `las_frontend/src/stores/auth.ts`

**Step 1: 扩展 User 类型**

```typescript
interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  role: string  // 添加
  is_active: boolean  // 添加
}
```

---

### Task 15: 创建管理页面组件

**Files:**
- Create: `las_frontend/src/views/admin/AdminLayout.vue`
- Create: `las_frontend/src/views/admin/AdminDashboard.vue`
- Create: `las_frontend/src/views/admin/UserManagement.vue`
- Create: `las_frontend/src/views/admin/LLMConfig.vue`
- Create: `las_frontend/src/views/admin/EmailConfig.vue`

**Step 1: AdminLayout.vue**

```vue
<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <h2>{{ t('admin.title') }}</h2>
      <nav>
        <router-link to="/admin">{{ t('admin.stats') }}</router-link>
        <router-link to="/admin/users">{{ t('admin.users') }}</router-link>
        <router-link to="/admin/llm-config">{{ t('admin.llmConfig') }}</router-link>
        <router-link to="/admin/email-config">{{ t('admin.emailConfig') }}</router-link>
      </nav>
    </aside>
    <main class="admin-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<style scoped>
.admin-layout {
  display: flex;
  min-height: 100vh;
}
.admin-sidebar {
  width: 250px;
  background: #f5f5f5;
  padding: 20px;
}
.admin-sidebar a {
  display: block;
  padding: 10px;
  margin: 5px 0;
  color: #333;
  text-decoration: none;
}
.admin-sidebar a.router-link-active {
  background: #42b983;
  color: white;
  border-radius: 4px;
}
.admin-content {
  flex: 1;
  padding: 20px;
}
</style>
```

**Step 2: AdminDashboard.vue**

```vue
<template>
  <div class="admin-dashboard">
    <h1>{{ t('admin.stats') }}</h1>
    <div class="stats-grid">
      <div class="stat-card">
        <h3>{{ t('admin.statsUsers') }}</h3>
        <p class="stat-number">{{ stats.users }}</p>
      </div>
      <div class="stat-card">
        <h3>{{ t('admin.statsProblems') }}</h3>
        <p class="stat-number">{{ stats.problems }}</p>
      </div>
      <div class="stat-card">
        <h3>{{ t('admin.statsModels') }}</h3>
        <p class="stat-number">{{ stats.model_cards }}</p>
      </div>
      <div class="stat-card">
        <h3>{{ t('admin.statsConversations') }}</h3>
        <p class="stat-number">{{ stats.conversations }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const stats = ref({ users: 0, problems: 0, model_cards: 0, conversations: 0 })

onMounted(async () => {
  const response = await api.get('/admin/users/stats')
  stats.value = response.data
})
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 20px;
}
.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.stat-number {
  font-size: 32px;
  font-weight: bold;
  color: #42b983;
}
</style>
```

**Step 3: UserManagement.vue**

```vue
<template>
  <div class="user-management">
    <h1>{{ t('admin.users') }}</h1>
    <table class="users-table">
      <thead>
        <tr>
          <th>{{ t('users.username') }}</th>
          <th>{{ t('users.email') }}</th>
          <th>{{ t('users.role') }}</th>
          <th>{{ t('users.status') }}</th>
          <th>{{ t('users.createdAt') }}</th>
          <th>{{ t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.username }}</td>
          <td>{{ user.email }}</td>
          <td>
            <select v-model="user.role" @change="updateUser(user)">
              <option value="admin">{{ t('users.admin') }}</option>
              <option value="user">{{ t('users.user') }}</option>
            </select>
          </td>
          <td>{{ user.is_active ? t('users.active') : t('users.inactive') }}</td>
          <td>{{ new Date(user.created_at).toLocaleDateString() }}</td>
          <td>
            <button @click="showResetPassword(user)">{{ t('users.resetPassword') }}</button>
            <button @click="deleteUser(user)">{{ t('common.delete') }}</button>
          </td>
        </tr>
      </tbody>
    </table>
    
    <!-- Reset Password Modal -->
    <div v-if="showModal" class="modal">
      <div class="modal-content">
        <h3>{{ t('users.resetPassword') }}</h3>
        <input v-model="newPassword" type="password" :placeholder="t('users.newPassword')" />
        <button @click="resetPassword">{{ t('common.save') }}</button>
        <button @click="showModal = false">{{ t('common.cancel') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const users = ref([])
const showModal = ref(false)
const selectedUser = ref(null)
const newPassword = ref('')

const loadUsers = async () => {
  const response = await api.get('/admin/users')
  users.value = response.data
}

const updateUser = async (user) => {
  await api.put(`/admin/users/${user.id}`, {
    role: user.role,
    is_active: user.is_active
  })
}

const showResetPassword = (user) => {
  selectedUser.value = user
  showModal.value = true
}

const resetPassword = async () => {
  await api.put(`/admin/users/${selectedUser.value.id}`, {
    password: newPassword.value
  })
  showModal.value = false
  newPassword.value = ''
}

const deleteUser = async (user) => {
  if (confirm(t('users.confirmDelete'))) {
    await api.delete(`/admin/users/${user.id}`)
    loadUsers()
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.users-table {
  width: 100%;
  border-collapse: collapse;
}
.users-table th, .users-table td {
  padding: 10px;
  border: 1px solid #ddd;
  text-align: left;
}
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-content {
  background: white;
  padding: 20px;
  border-radius: 8px;
}
</style>
```

**Step 4: LLMConfig.vue**

```vue
<template>
  <div class="llm-config">
    <h1>{{ t('admin.llmConfig') }}</h1>
    <form @submit.prevent="saveConfig">
      <div class="form-group">
        <label>{{ t('llm.openaiKey') }}</label>
        <input v-model="config.openai_api_key" type="password" />
      </div>
      <div class="form-group">
        <label>{{ t('llm.openaiModel') }}</label>
        <input v-model="config.openai_model" type="text" />
      </div>
      <div class="form-group">
        <label>{{ t('llm.anthropicKey') }}</label>
        <input v-model="config.anthropic_api_key" type="password" />
      </div>
      <div class="form-group">
        <label>{{ t('llm.anthropicModel') }}</label>
        <input v-model="config.anthropic_model" type="text" />
      </div>
      <div class="form-group">
        <label>{{ t('llm.defaultProvider') }}</label>
        <select v-model="config.default_provider">
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
        </select>
      </div>
      <button type="submit">{{ t('common.save') }}</button>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const config = ref({
  openai_api_key: '',
  openai_model: 'gpt-4o-mini',
  anthropic_api_key: '',
  anthropic_model: 'claude-3-5-sonnet-20241022',
  default_provider: 'openai'
})

const loadConfig = async () => {
  try {
    const response = await api.get('/admin/llm-config')
    config.value = { ...config.value, ...response.data }
  } catch (e) {
    // 使用默认值
  }
}

const saveConfig = async () => {
  await api.put('/admin/llm-config', config.value)
  alert(t('llm.saveSuccess'))
}

onMounted(loadConfig)
</script>

<style scoped>
.form-group {
  margin-bottom: 15px;
}
.form-group label {
  display: block;
  margin-bottom: 5px;
}
.form-group input, .form-group select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}
</style>
```

**Step 5: EmailConfig.vue**

```vue
<template>
  <div class="email-config">
    <h1>{{ t('admin.emailConfig') }}</h1>
    <form @submit.prevent="saveConfig">
      <div class="form-group">
        <label>{{ t('email.smtpHost') }}</label>
        <input v-model="config.smtp_host" type="text" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.smtpPort') }}</label>
        <input v-model.number="config.smtp_port" type="number" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.smtpUser') }}</label>
        <input v-model="config.smtp_user" type="text" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.smtpPassword') }}</label>
        <input v-model="config.smtp_password" type="password" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.fromEmail') }}</label>
        <input v-model="config.from_email" type="email" required />
      </div>
      <div class="form-group">
        <label>{{ t('email.fromName') }}</label>
        <input v-model="config.from_name" type="text" />
      </div>
      <div class="form-group">
        <label>
          <input v-model="config.use_tls" type="checkbox" />
          {{ t('email.useTLS') }}
        </label>
      </div>
      <button type="submit">{{ t('common.save') }}</button>
      <button type="button" @click="testEmail">{{ t('email.testEmail') }}</button>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const config = ref({
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  from_email: '',
  from_name: 'Learning Assistant',
  use_tls: true
})

const loadConfig = async () => {
  try {
    const response = await api.get('/admin/email-config')
    config.value = { ...config.value, ...response.data }
  } catch (e) {
    // 使用默认值
  }
}

const saveConfig = async () => {
  await api.put('/admin/email-config', config.value)
  alert(t('email.saveSuccess'))
}

const testEmail = async () => {
  const email = prompt('Enter email to test:')
  if (email) {
    try {
      await api.post('/admin/email-config/test', { to_email: email })
      alert(t('email.testSuccess'))
    } catch (e) {
      alert(e.response?.data?.detail || 'Error')
    }
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.form-group {
  margin-bottom: 15px;
}
.form-group label {
  display: block;
  margin-bottom: 5px;
}
.form-group input[type="text"],
.form-group input[type="email"],
.form-group input[type="password"],
.form-group input[type="number"] {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}
</style>
```

---

### Task 16: 添加管理路由

**Files:**
- Modify: `las_frontend/src/router/index.ts`

**Step 1: 添加路由**

```typescript
{
  path: '/admin',
  component: () => import('@/views/admin/AdminLayout.vue'),
  meta: { requiresAuth: true, requiresAdmin: true },
  children: [
    {
      path: '',
      name: 'admin-dashboard',
      component: () => import('@/views/admin/AdminDashboard.vue'),
    },
    {
      path: 'users',
      name: 'admin-users',
      component: () => import('@/views/admin/UserManagement.vue'),
    },
    {
      path: 'llm-config',
      name: 'admin-llm',
      component: () => import('@/views/admin/LLMConfig.vue'),
    },
    {
      path: 'email-config',
      name: 'admin-email',
      component: () => import('@/views/admin/EmailConfig.vue'),
    },
  ],
},
```

---

### Task 17: 添加路由守卫

**Files:**
- Modify: `las_frontend/src/router/index.ts`

**Step 1: 更新路由守卫**

```typescript
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.meta.requiresAdmin && authStore.user?.role !== 'admin') {
    next('/dashboard')  // 非管理员不能访问管理页面
  } else if ((to.name === 'login' || to.name === 'register') && authStore.isAuthenticated) {
    next('/dashboard')
  } else {
    next()
  }
})
```

---

### Task 18: 创建找回密码页面

**Files:**
- Create: `las_frontend/src/views/ForgotPasswordView.vue`
- Create: `las_frontend/src/views/ResetPasswordView.vue`

**Step 1: ForgotPasswordView.vue**

```vue
<template>
  <div class="forgot-password">
    <h1>{{ t('auth.forgotPassword') }}</h1>
    <form @submit.prevent="sendResetLink">
      <input v-model="email" type="email" :placeholder="t('users.email')" required />
      <button type="submit">{{ t('auth.sendResetLink') }}</button>
    </form>
    <p>{{ message }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()
const email = ref('')
const message = ref('')

const sendResetLink = async () => {
  try {
    await api.post('/auth/forgot-password', { email: email.value })
    message.value = 'If email exists, reset link will be sent'
  } catch (e) {
    message.value = 'Error sending reset link'
  }
}
</script>
```

**Step 2: ResetPasswordView.vue**

```vue
<template>
  <div class="reset-password">
    <h1>{{ t('auth.resetPassword') }}</h1>
    <form @submit.prevent="resetPassword">
      <input v-model="password" type="password" :placeholder="t('users.newPassword')" required />
      <button type="submit">{{ t('common.save') }}</button>
    </form>
    <p>{{ message }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const password = ref('')
const message = ref('')

const resetPassword = async () => {
  try {
    await api.post('/auth/reset-password', {
      token: route.query.token,
      new_password: password.value
    })
    message.value = t('auth.passwordResetSuccess')
    setTimeout(() => router.push('/login'), 2000)
  } catch (e) {
    message.value = 'Error resetting password'
  }
}
</script>
```

**Step 3: 添加路由**

```typescript
{
  path: '/forgot-password',
  name: 'forgot-password',
  component: () => import('@/views/ForgotPasswordView.vue'),
},
{
  path: '/reset-password',
  name: 'reset-password',
  component: () => import('@/views/ResetPasswordView.vue'),
},
```

---

### Task 19: 更新登录页面添加忘记密码链接

**Files:**
- Modify: `las_frontend/src/views/LoginView.vue`

**Step 1: 添加链接**

```vue
<router-link to="/forgot-password">{{ t('auth.forgotPassword') }}</router-link>
```

---

## 验证清单

- [ ] 后端启动正常，API 可访问
- [ ] 第一个注册用户 role 为 admin
- [ ] /admin 路由仅管理员可访问
- [ ] 用户管理：增删改查正常
- [ ] LLM 配置保存和读取正常
- [ ] 邮件配置保存和测试发送正常
- [ ] 找回密码流程正常（需要配置邮件）
- [ ] 前端中英文切换正常
