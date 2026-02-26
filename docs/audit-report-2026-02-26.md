# Cogniforge 学习助手系统 — 功能审核报告

**审核日期**: 2026-02-26
**审核范围**: 功能完整性 & 业务流程
**代码分支**: cv/0c8b33061e35-

---

## 一、总体评估

系统整体架构清晰，前后端分离，核心功能模块基本齐全。但存在若干功能缺失、流程断裂和数据一致性问题，需要关注。

---

## 二、功能模块审核

### 2.1 认证模块

| 项目 | 状态 | 说明 |
|------|------|------|
| 用户注册 | ✅ 正常 | 首个用户自动成为 admin |
| 用户登录 | ✅ 正常 | OAuth2 + JWT |
| 获取当前用户 | ✅ 正常 | |
| 更新用户信息 | ⚠️ 缺陷 | 更新 email/username 时未检查唯一性冲突，可能导致数据库约束报错而非友好提示 |
| 密码重置 | ⚠️ 缺陷 | 见 2.2 |
| Token 刷新 | ❌ 缺失 | 无 refresh token 机制，token 过期后用户必须重新登录，无法静默续期 |
| 登出 | ❌ 缺失 | 后端无登出接口，token 无法主动失效（无黑名单机制） |

---

### 2.2 密码重置流程

**严重问题**：

1. **内存存储 token**（`password_reset.py:18`）
   ```python
   reset_tokens = {}  # 进程内存字典
   ```
   - 服务重启后所有待重置 token 全部丢失
   - 多进程/多实例部署时 token 无法共享
   - 应改为数据库或 Redis 存储

2. **重置链接硬编码 localhost**（`password_reset.py:43`）
   ```python
   reset_link = f"http://localhost:5175/reset-password?token={token}"
   ```
   - 生产环境邮件中的链接无法使用
   - 前端端口也与 vite 默认端口 5173 不一致（写的是 5175）

3. **邮件发送失败静默处理**（`password_reset.py:61-62`）
   ```python
   except Exception as e:
       print(f"Failed to send email: {e}")
   ```
   - 邮件发送失败时用户收到成功响应，但实际未收到邮件，无法感知

---

### 2.3 问题（Problem）模块

| 项目 | 状态 | 说明 |
|------|------|------|
| 创建问题 | ✅ 正常 | 自动生成学习路径 |
| 列表/详情/更新/删除 | ✅ 正常 | |
| 提交回答 | ✅ 正常 | 自动生成 AI 反馈 |
| 获取学习路径 | ⚠️ 缺陷 | 见下 |
| 更新学习路径进度 | ❌ 缺失 | `LearningPath.current_step` 字段存在但无 API 可更新，用户无法推进学习步骤 |
| 问题状态流转 | ⚠️ 不完整 | status 字段可手动更新，但无自动状态流转逻辑（如完成所有步骤后自动标记为 done） |

**学习路径权限漏洞**（`problems.py:187-203`）：
```python
# 只按 problem_id 查询，未验证该 problem 是否属于当前用户
result = await db.execute(
    select(LearningPath).where(LearningPath.problem_id == problem_id)
)
```
任意已登录用户只要知道 `problem_id` 即可获取他人的学习路径。

---

### 2.4 模型卡（Model Card）模块

| 项目 | 状态 | 说明 |
|------|------|------|
| 创建/列表/详情/更新/删除 | ✅ 正常 | |
| 生成反例 | ✅ 正常 | |
| 跨域迁移建议 | ✅ 正常 | |
| 演化日志记录 | ❌ 缺失 | `EvolutionLog` 模型已定义，`model_os_service.log_evolution()` 方法存在但仅返回字典，从未实际写入数据库。模型卡版本变更时无演化记录 |
| 版本历史查看 | ❌ 缺失 | `parent_id` 字段存在但无相关 API，无法查看历史版本 |
| embedding 字段 | ❌ 未使用 | `ModelCard.embedding` 字段存在但从未被填充或使用 |

---

### 2.5 对话（Chat）模块

| 项目 | 状态 | 说明 |
|------|------|------|
| 创建/列表/详情/删除对话 | ✅ 正常 | |
| 发送消息 | ✅ 正常 | |
| 生成反例 | ✅ 正常 | |
| 跨域迁移 | ✅ 正常 | |
| 对话标题更新 | ❌ 缺失 | 无 PUT `/conversations/{id}` 接口，`ConversationUpdate` schema 已定义但未使用 |
| 消息持久化双轨问题 | ⚠️ 设计缺陷 | 消息同时存储在 `Conversation.messages`（JSON 列）和 `ConversationMessage` 表中，但实际只写入 JSON 列，`ConversationMessage` 表永远为空，造成数据冗余和混乱 |

---

### 2.6 练习（Practice）模块

| 项目 | 状态 | 说明 |
|------|------|------|
| 创建/列表练习任务 | ⚠️ 缺陷 | 见下 |
| 提交练习 | ✅ 正常 | 自动生成 AI 反馈 |
| 列表提交记录 | ✅ 正常 | |
| 获取单个提交 | ❌ 缺失 | 无 GET `/practice/submissions/{id}` 接口 |
| 删除练习任务 | ❌ 缺失 | 无删除接口 |

**权限漏洞**（`practice.py:48-58`）：
```python
# 列出所有练习任务，未过滤用户
result = await db.execute(
    select(PracticeTask).order_by(PracticeTask.created_at.desc())
)
```
所有用户可以看到系统中所有人创建的练习任务。`PracticeTask` 模型也没有 `user_id` 字段，无法区分归属。

---

### 2.7 回顾（Review）模块

| 项目 | 状态 | 说明 |
|------|------|------|
| 创建/列表/详情 | ✅ 正常 | |
| 更新回顾 | ❌ 缺失 | 无 PUT 接口 |
| 删除回顾 | ❌ 缺失 | 无 DELETE 接口 |
| AI 辅助生成回顾内容 | ❌ 缺失 | Review 内容完全由用户手动填写，未集成 LLM 生成摘要或建议 |

---

### 2.8 管理面板

| 项目 | 状态 | 说明 |
|------|------|------|
| 用户列表/详情/更新/删除 | ✅ 正常 | |
| 系统统计 | ✅ 正常 | |
| LLM 提供商 CRUD | ✅ 正常 | |
| LLM 模型 CRUD | ✅ 正常 | |
| 测试 LLM 连接 | ✅ 正常 | |
| 邮件配置 CRUD | ✅ 正常 | |
| 测试邮件发送 | ✅ 正常 | |
| 管理员删除自身 | ⚠️ 缺陷 | 无保护机制，管理员可以删除自己，导致系统无管理员 |
| `require_admin` 重复定义 | ⚠️ 代码问题 | `admin_users.py`、`admin_llm.py`、`admin_email.py` 各自独立定义了相同的 `require_admin` 函数，应提取为公共依赖 |

---

### 2.9 LLM 服务

| 项目 | 状态 | 说明 |
|------|------|------|
| OpenAI 调用 | ✅ 正常 | |
| Anthropic 调用 | ✅ 正常 | |
| Ollama 调用 | ✅ 正常 | |
| 无提供商时的降级 | ⚠️ 缺陷 | 返回错误字符串而非抛出异常，调用方无法区分正常响应和错误 |
| 使用数据库配置的模型 | ⚠️ 未完全实现 | `_get_default_model()` 方法存在但 `generate()` 中未调用，始终使用硬编码的默认模型名（如 `gpt-4o-mini`），忽略了管理员在数据库中配置的模型 |

---

## 三、前端流程审核

### 3.1 路由守卫

- ✅ 认证守卫正常（未登录跳转 `/login`）
- ✅ 管理员守卫正常（非 admin 跳转 `/dashboard`）
- ⚠️ 已登录用户访问 `/forgot-password` 和 `/reset-password` 无重定向保护

### 3.2 Dashboard

- ⚠️ 统计数据通过三个独立 API 请求获取（problems/model-cards/conversations），但 `practice` 统计始终为 0，因为没有对应的 API 调用

### 3.3 国际化

- ✅ 中英文切换正常
- 翻译文件完整性需进一步核查（未在本次审核范围内）

---

## 四、问题汇总

### 严重问题（影响核心功能）

| # | 位置 | 问题 |
|---|------|------|
| S1 | `password_reset.py:18` | 重置 token 存内存，重启丢失，多实例不可用 |
| S2 | `password_reset.py:43` | 重置链接硬编码 `localhost:5175`，生产不可用 |
| S3 | `problems.py:187` | 学习路径接口未验证用户归属，存在越权访问 |
| S4 | `practice.py:48` | 练习任务列表未过滤用户，所有人数据全部暴露 |
| S5 | `llm_service.py:48-52` | 忽略数据库中配置的模型，始终使用硬编码默认值 |

### 功能缺失（影响完整体验）

| # | 位置 | 缺失功能 |
|---|------|---------|
| F1 | `problems.py` | 无更新学习路径进度的 API |
| F2 | `model_cards.py` | 演化日志从未写入数据库 |
| F3 | `conversations.py` | 无更新对话标题的 API |
| F4 | `practice.py` | 无获取单个提交、删除任务的 API |
| F5 | `practice.py` | `PracticeTask` 缺少 `user_id`，无法区分归属 |
| F6 | `auth.py` | 无 token 刷新机制 |
| F7 | `auth.py` | 无登出/token 失效机制 |
| F8 | `admin_users.py` | 管理员可删除自身，无保护 |
| F9 | `DashboardView.vue` | practice 统计数据始终为 0 |

### 设计缺陷（影响可维护性）

| # | 位置 | 问题 |
|---|------|------|
| D1 | `user.py` + `conversations.py` | 消息双轨存储，`ConversationMessage` 表永远为空 |
| D2 | `admin_*.py` | `require_admin` 三处重复定义 |
| D3 | `auth.py:126-133` | 更新用户信息未检查 email/username 唯一性 |
| D4 | `model_os_service.py:167` | `log_evolution()` 仅返回字典，未持久化 |
| D5 | `user.py:84` | `ModelCard.embedding` 字段从未使用 |

---

## 五、优先修复建议

1. **S3/S4**（越权访问）— 最高优先级，安全问题
2. **S1/S2**（密码重置）— 高优先级，核心流程不可用
3. **S5**（LLM 模型配置未生效）— 高优先级，管理员配置形同虚设
4. **F1**（学习路径进度）— 中优先级，核心学习流程断裂
5. **F2**（演化日志）— 中优先级，Model OS 核心特性缺失
6. **D1**（消息双轨）— 中优先级，数据一致性隐患
