# PostgreSQL + pgvector 迁移方案

日期: 2026-03-03
适用仓库: `/Users/asteroida/work/Cogniforge`

## 当前现状

截至 2026-03-03，仓库数据库相关状态如下：

- 配置层默认宣称使用 PostgreSQL:
  - `/Users/asteroida/work/Cogniforge/las_backend/app/core/config.py`
- 实际运行层仍然强制使用 SQLite 文件:
  - `/Users/asteroida/work/Cogniforge/las_backend/app/core/database.py`
- Docker Compose 仅启动前后端，没有 PostgreSQL 服务:
  - `/Users/asteroida/work/Cogniforge/docker-compose.yml`
- 后端依赖已包含 `asyncpg` 和 `psycopg2-binary`，说明迁移成本可控:
  - `/Users/asteroida/work/Cogniforge/las_backend/requirements.txt`
- Alembic 已存在，但当前元数据来源仍跟随现有数据库层。

这意味着项目“名义上支持 PostgreSQL”，但实际上还没有真正接入。

## 迁移目标

1. 默认运行数据库从 SQLite 切换到 PostgreSQL。
2. 启用 `pgvector` 扩展，为后续相似检索和轻量 RAG 做准备。
3. 保留本地快速开发能力:
   - 允许通过环境变量继续用 SQLite
   - 但生产和默认 Docker 环境统一走 PostgreSQL
4. 不一次性重写业务代码，先打通数据库层和迁移链路。

## 迁移原则

1. 先兼容双栈，再切默认值。
2. 先落数据库基础设施，再做 embedding 与检索接口。
3. Alembic 作为唯一 schema 变更来源，避免 `create_all` 成为长期主路径。
4. 向量能力先落字段与扩展，再接入生成逻辑。

## 实施步骤

### 阶段 A: 基础设施切换

#### A1. 统一数据库配置入口

目标:

- `app/core/database.py` 不再自行拼 SQLite URL。
- 统一读取 `Settings.DATABASE_URL`。
- 仅在显式传入 `DATABASE_FILE` 或 `DATABASE_URL` 为 SQLite 时才使用 SQLite。

改造点:

- `/Users/asteroida/work/Cogniforge/las_backend/app/core/config.py`
- `/Users/asteroida/work/Cogniforge/las_backend/app/core/database.py`

结果:

- 本地与容器环境都能通过 `.env` 或环境变量切换数据库。

#### A2. Docker Compose 增加 PostgreSQL

新增服务:

- `postgres`
- 镜像建议: `pgvector/pgvector:pg16`

建议参数:

- 数据库名: `las_db`
- 用户: `postgres`
- 密码: `postgres`
- 持久化 volume
- 健康检查

同时修改:

- backend 依赖 postgres 健康状态
- backend 环境变量注入 `DATABASE_URL`

#### A3. 移除运行期长期依赖 `create_all`

当前:

- `app/main.py` 在启动时运行 `Base.metadata.create_all`

目标:

- 开发早期可保留开关
- 默认使用 Alembic migration

建议:

- 增加 `AUTO_CREATE_TABLES=false` 配置
- 默认关闭
- Alembic 成为正式 schema 初始化方式

### 阶段 B: Alembic 与 schema 校准

#### B1. 校准 Alembic URL 来源

当前 Alembic 依赖 `alembic.ini` 的 URL。

目标:

- `alembic/env.py` 从应用配置读取 `DATABASE_URL`
- 保证 Alembic 与运行时数据库一致

#### B2. 生成基线迁移

需要确认:

- 现有 SQLite 数据是否需要保留迁移
- 若无需保留，可直接生成 PostgreSQL 基线
- 若需保留，则要增加 SQLite -> PostgreSQL 数据导入脚本

建议做法:

1. 先生成 PostgreSQL 基线 migration
2. 在测试库上跑全量建表
3. 再决定是否写一次性数据迁移脚本

### 阶段 C: pgvector 接入

#### C1. 安装并启用扩展

在 Alembic migration 中增加:

- `CREATE EXTENSION IF NOT EXISTS vector`

#### C2. 为核心对象增加向量字段

建议优先对象:

1. `model_cards`
2. `problems`
3. `resource_links`

说明:

- 当前 `ModelCard.embedding` 是 JSON 字段，不适合正式向量检索
- 应改为 `Vector(n)` 或与 pgvector 兼容的列类型

建议维度:

- 如果使用 OpenAI `text-embedding-3-small`: 1536
- 如果后续希望模型可切换，可先封装常量，不硬编码到业务代码里

#### C3. 向量生成流程

第一阶段只做同步生成，后续再异步化。

触发时机:

- 创建 Model Card
- 更新 Model Card
- 创建 Problem
- 添加 Resource 解读后

### 阶段 D: 搜索与召回

#### D1. Model Card 相似搜索

新增接口:

- `/model-cards/search?q=...`
- `/model-cards/{id}/similar`

#### D2. Problem 与 Resource 召回

新增接口:

- `/problems/search`
- `/resources/search`

#### D3. 聊天与反馈接入轻量 RAG

先做最小闭环:

- 对话提问时，召回最相关的 3-5 张模型卡
- 将召回结果作为上下文片段注入
- 保留原有消息上下文拼接，避免直接替换失败

### 阶段 E: 数据迁移

如果需要保留 SQLite 历史数据，建议单独做一次性脚本:

- 导出 SQLite 数据
- 映射主键与时间字段
- 导入 PostgreSQL
- 重建 review schedules / evolution logs 的关联完整性

建议脚本位置:

- `/Users/asteroida/work/Cogniforge/las_backend/scripts/migrate_sqlite_to_postgres.py`

## 建议执行顺序

### Sprint P1

1. 统一 `DATABASE_URL`
2. Docker Compose 增加 PostgreSQL
3. Alembic 跟随应用配置

### Sprint P2

1. PostgreSQL 基线 migration
2. 停止默认 `create_all`
3. 在容器环境跑通后端启动

### Sprint P3

1. pgvector extension
2. embedding 列重构
3. Model Card embedding 写入

### Sprint P4

1. 相似搜索接口
2. 轻量 RAG 接入聊天/反馈
3. 性能与召回质量验证

## 风险点

### 风险 1: 现有 JSON embedding 字段与 pgvector 冲突

解决:

- 不原地复用 JSON 字段
- 先新增正式向量列，再逐步弃用旧字段

### 风险 2: `create_all` 与 Alembic 混用造成 schema 漂移

解决:

- 明确关闭默认 `create_all`
- 所有 schema 变更都走 Alembic

### 风险 3: SQLite 与 PostgreSQL 行为差异

典型点:

- JSON 查询行为
- 模糊匹配
- 默认值/时间戳
- UUID 存储策略

解决:

- 在 PostgreSQL 上补一组 API 集成测试

### 风险 4: pgvector 上线后写入成本增加

解决:

- 初期允许 embedding 失败不阻塞主写流程
- 通过后台补算或重试任务修复

## 建议的首批代码改动

第一批不要直接碰 RAG，只做以下 5 项：

1. `database.py` 改为读取 `Settings.DATABASE_URL`
2. `docker-compose.yml` 增加 `postgres` 服务
3. `alembic/env.py` 跟随应用配置
4. `main.py` 增加 `AUTO_CREATE_TABLES` 开关
5. 新增 PostgreSQL 启动说明到 README

完成这 5 项后，项目数据库层才算真正具备切换条件。

## 验收标准

迁移准备完成的标准:

1. 本地 `docker compose up` 能拉起 PostgreSQL
2. 后端使用 PostgreSQL 启动成功
3. Alembic 可在 PostgreSQL 上执行迁移
4. 核心 API 冒烟通过
5. 后续 pgvector 改造不再需要重做数据库入口层
