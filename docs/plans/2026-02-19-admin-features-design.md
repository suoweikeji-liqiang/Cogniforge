# 管理员功能设计文档

> **For Claude:** 实现前请先阅读此设计文档，确保理解所有需求和架构。

**目标：** 为学习助手系统添加管理员功能，支持用户管理、LLM配置管理、邮件配置管理、找回密码功能，并实现中英文双语支持。

**架构：**
- 管理员角色：第一个注册用户自动设为管理员，后续用户为普通用户
- 权限控制：管理员可访问 /admin 路由，普通用户无法访问
- 找回密码：支持邮件重置和管理员重置两种方式
- 国际化：Vue i18n 支持中英文切换

**技术栈：**
- 后端：FastAPI + SQLAlchemy + SMTP (邮件)
- 前端：Vue3 + Pinia + vue-i18n

---

## 1. 数据库模型

### 1.1 用户表变更
```python
# users 表新增字段
role: str = "user"  # "admin" 或 "user"
```

### 1.2 邮件配置表
```python
class EmailConfig(Base):
    __tablename__ = "email_config"
    
    id: int = Column(Integer, primary_key=True)
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str  # 应加密存储
    from_email: str
    from_name: str
    use_tls: bool = True
    is_active: bool = True
```

### 1.3 系统设置表
```python
class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id: int = Column(Integer, primary_key=True)
    key: str = Column(unique=True)
    value: JSON
    description: str
```

---

## 2. 后端 API 设计

### 2.1 管理员用户管理
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/admin/users | 获取用户列表 |
| GET | /api/admin/users/{id} | 获取单个用户 |
| PUT | /api/admin/users/{id} | 更新用户信息 |
| DELETE | /api/admin/users/{id} | 删除用户 |
| POST | /api/admin/users/{id}/reset-password | 管理员重置密码 |

### 2.2 LLM 配置管理
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/admin/llm-config | 获取 LLM 配置 |
| PUT | /api/admin/llm-config | 更新 LLM 配置 |

### 2.3 邮件配置管理
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/admin/email-config | 获取邮件配置 |
| PUT | /api/admin/email-config | 更新邮件配置 |
| POST | /api/admin/email-config/test | 测试邮件发送 |

### 2.4 统计信息
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/admin/stats | 获取系统统计 |

### 2.5 找回密码
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/auth/forgot-password | 请求密码重置 |
| POST | /api/auth/reset-password | 重置密码 |
| GET | /api/auth/verify-reset-token | 验证 token 有效性 |

---

## 3. 前端设计

### 3.1 路由
```
/admin                  - 管理后台首页（仪表盘）
/admin/users           - 用户管理
/admin/llm-config      - LLM 配置
/admin/email-config    - 邮件配置
```

### 3.2 权限控制
- 路由守卫：检查用户 role 为 "admin"
- API 拦截：后端返回 403 时跳转

### 3.3 国际化
- 语言文件：locales/en.json, locales/zh.json
- 切换组件：顶部导航栏语言切换
- 默认语言：跟随浏览器设置

---

## 4. 找回密码流程

### 4.1 邮件重置流程
1. 用户在登录页点击"忘记密码"
2. 输入注册邮箱
3. 后端验证邮箱存在，生成 token（有效期 1 小时）
4. 发送邮件到用户邮箱（包含重置链接）
5. 用户点击链接，跳转到重置密码页
6. 输入新密码，验证 token，更新密码

### 4.2 管理员重置流程
1. 管理员进入用户管理页面
2. 点击用户操作"重置密码"
3. 输入新密码
4. 后端更新密码（不验证旧密码）

---

## 5. 第一个管理员设置

- 数据库初始化时无用户，第一个注册用户自动设为 admin
- 后续注册用户默认 role 为 user
- 管理员可在用户管理页面修改用户角色
