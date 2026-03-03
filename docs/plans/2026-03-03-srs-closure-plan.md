# Cogniforge SRS 补齐方案

日期: 2026-03-03
关联文档:

- `/Users/asteroida/work/Cogniforge/docs/srs-gap-analysis-2026-03-03.md`
- `/Users/asteroida/work/Cogniforge/SRS.md`

## 目标

把当前仓库从“可演示 MVP”推进到“可按 SRS 主线验收”的版本，同时控制返工成本，不重写整个系统。

## 总体策略

1. 先补主流程闭环，再补架构深度。
2. 先补“用户能直接感知”的能力，再补“系统内部质量”。
3. 对已存在的扩展功能不大改，只做必要整合。
4. 对 SRS 中成本最高的架构项采取分阶段落地，不一次性推翻现有代码。

## 阶段规划

### 阶段 1: 主流程闭环

目标: 让问题学习、Model Card、Practice、Review、SRS 形成完整学习闭环。

#### 1.1 问题学习流程补齐

- 在问题详情页加入“推进到下一步/标记当前步骤完成”交互。
- 调用现有 `/problems/{id}/learning-path` 更新接口。
- 后端在完成最后一步时自动将问题状态推进到 `completed`。
- 增加获取问题回答历史的接口，避免页面刷新后历史丢失。

#### 1.2 Review 复盘模块补齐

- 增加“自动生成复盘”接口:
  - 输入周期类型 `daily/weekly/monthly`
  - 聚合 Problems、Practice、Challenges、EvolutionLog、SRS 数据
  - 生成 `summary / insights / next_steps / misconceptions`
- 前端 Review 页面支持:
  - 自动生成
  - 编辑后保存
  - 查看历史复盘
- 新增 Markdown 导出接口，满足“可下载报告/学习日志”。

#### 1.3 SRS 闭环补齐

- 在 Model Card 列表和详情页增加“加入复习计划”按钮。
- 前端调用 `/srs/schedule/{card_id}`。
- SRS 复习页增加答案内容:
  - 展示 `user_notes`
  - 展示 examples
  - 展示 counter examples
- Dashboard 增加“最近加入复习的卡片”和排程状态。

#### 1.4 Practice 与迁移闭环

- 在创建 PracticeTask 时支持从 Model Card 自动生成任务。
- 在任务详情或提交反馈中加入“迁移提示”区块。
- 将 PracticeSubmission 与对应 Model Card 的演化日志关联。

### 阶段 2: Model OS 深化

目标: 让演化、迁移、反馈更像 SRS 描述的 Model OS，而不是零散功能。

#### 2.1 版本管理补齐

- 新增 Model Card 版本快照策略:
  - 每次重要更新时写入快照
  - 建立 `parent_id` 或独立版本表
- 新增版本历史列表接口。
- 新增版本差异摘要:
  - 调用 `generate_evolution_summary()`
  - 在详情页展示“这次更新有什么变化”

#### 2.2 结构化反馈补齐

- 把 `generate_feedback()` 输出改成结构化 JSON:
  - correctness
  - misconceptions
  - suggestions
  - next_question
- 前端在问题回答、练习反馈、挑战反馈中统一渲染。

#### 2.3 迁移闭环补齐

- 迁移建议不再只保存 `target_domain`。
- 增加迁移尝试记录:
  - applied_context
  - adaptation_notes
  - outcome
- 前端提供“记录一次迁移尝试”的表单。

### 阶段 3: 检索与知识库能力

目标: 逐步向 SRS 的 PostgreSQL + pgvector + RAG 靠拢。

#### 3.1 数据层迁移

- 将默认数据库切换到 PostgreSQL。
- 保留 SQLite 仅作为开发回退模式。
- 新增 Alembic 迁移，覆盖全部核心表。

#### 3.2 向量与搜索

- 为 Model Card、Problem、Resource 建立 embedding 生成流程。
- 引入 pgvector。
- 新增搜索接口:
  - 关键词搜索
  - 相似卡片搜索
  - 相似问题搜索

#### 3.3 轻量 RAG

- 对话时从用户相关 Model Card、Review、Problem 中召回上下文。
- 用检索结果替代当前纯文本消息拼接。
- 增加召回日志，便于调试。

### 阶段 4: 安全、质量与验收

目标: 让系统具备可持续迭代和可验收属性。

#### 4.1 安全补齐

- 去掉默认 `SECRET_KEY`。
- 前端接入 refresh token 或最少接入后端 refresh 流程。
- 登出调用后端 `/auth/logout`。
- API Key/SMTP 密钥不在前端明文展示。
- 登录增加基本频率限制。

#### 4.2 测试补齐

- 增加后端 API 集成测试:
  - auth
  - problems
  - model-cards
  - reviews
  - srs
- 增加前端关键页面 smoke tests。
- 增加一份 SRS 验收测试脚本。

#### 4.3 性能与可观测性

- 为主要 LLM 路径记录耗时。
- 对学习路径、反馈、迁移、总结生成设置超时和失败降级。
- 增加后台统计“近 7 天失败请求”和“平均响应时间”。

## 实施优先级

### P0

- 问题学习路径推进闭环
- 问题回答历史读取
- Review 自动生成与导出
- SRS 加入排程入口
- Model Card 详情补充排程状态

### P1

- 结构化反馈
- 版本历史与演化摘要
- Practice 自动生成任务
- 迁移尝试记录

### P2

- PostgreSQL 迁移
- pgvector
- 轻量 RAG
- 搜索能力

### P3

- 安全基线
- 测试体系
- 性能观测

## 建议交付节奏

### Sprint 1

- 问题流程闭环
- Review 自动生成
- SRS 接入入口

### Sprint 2

- 结构化反馈
- 版本历史
- 迁移闭环

### Sprint 3

- PostgreSQL/pgvector
- 搜索
- 轻量 RAG

### Sprint 4

- 安全加固
- 自动化测试
- 验收与文档收尾

## 具体改造清单

### 后端

- `app/api/routes/problems.py`
- `app/api/routes/model_cards.py`
- `app/api/routes/practice.py`
- 新增 `app/api/routes/reports.py`
- `app/api/routes/srs.py`
- `app/services/model_os_service.py`
- 新增 `app/services/review_service.py`
- `app/services/llm_service.py`
- `app/models/entities/user.py`
- 新增 Alembic 迁移

### 前端

- `src/views/ProblemDetailView.vue`
- `src/views/ModelCardsView.vue`
- `src/views/ModelCardDetailView.vue`
- `src/views/ReviewsView.vue`
- `src/views/SRSReviewView.vue`
- `src/views/PracticeView.vue`
- `src/views/DashboardView.vue`
- `src/api/index.ts`
- `src/stores/auth.ts`

## 风险与取舍

### 高风险

- PostgreSQL/pgvector 迁移会触及部署和本地开发方式。
- RAG 会改变聊天与反馈路径，需要单独回归测试。

### 中风险

- Review 自动生成涉及多源聚合，输出结构需要稳定。
- 版本管理如果直接改现有表，容易引入迁移复杂度。

### 低风险

- 学习路径推进
- SRS 前端入口
- 导出 Markdown 报告

## 推荐的推进顺序

先做以下 5 项，不要并行开太多战线:

1. 问题详情页学习路径推进闭环
2. 问题回答历史接口与前端展示修正
3. Review 自动生成接口与页面改造
4. Model Card 加入 SRS 计划入口
5. SRS 复习页补充卡片内容

这 5 项完成后，项目会从“有很多模块”变成“真正有一条完整学习主线”。
