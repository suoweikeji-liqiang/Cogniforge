# 认知对抗测试系统（Cognitive Adversarial Testing）

## What This Is

学习助手系统的认知对抗测试模块：学习者从模型卡发起测试，两个苏格拉底式AI导师（引导者 + 质疑者）通过实时流式对话帮助发现理解盲区，追踪理解度评分，生成可导出的认知诊断报告，并自动提升发现盲区的模型卡的间隔重复复习优先级。

**v1.0 已交付：** 完整的后端对话引擎（FastAPI + SSE）、Vue3前端（实时流式UI + 历史记录）、报告导出、SRS集成。

## Core Value

帮助学习者通过结构化的苏格拉底式对话，发现自己对概念的认知盲区和薄弱点——不是灌输知识，而是暴露理解的缺口。

## Requirements

### Validated

- ✓ 从模型卡发起认知对抗测试会话，概念自动预加载 (SESS-01) — v1.0
- ✓ SSE实时流式输出导师对话，逐token显示 (SESS-02) — v1.0
- ✓ 每轮对话基于完整历史上下文构建 (SESS-03) — v1.0
- ✓ 用户可随时停止测试，立即获得认知诊断摘要 (SESS-04) — v1.0
- ✓ 对话记录持久化，用户可查看历史会话列表 (SESS-05) — v1.0
- ✓ 学习助手导航栏新增"认知测试"入口 (SESS-06) — v1.0
- ✓ 引导者Agent通过正面提问引导深入理解 (AGNT-01) — v1.0
- ✓ 质疑者Agent温和指出矛盾和不完整之处 (AGNT-02) — v1.0
- ✓ 两个Agent严格遵守苏格拉底契约——绝不直接给出答案 (AGNT-03) — v1.0
- ✓ 轮次调度器决定每轮由哪个Agent发言 (AGNT-04) — v1.0
- ✓ Agent反馈解释为何回答不完整 (AGNT-05) — v1.0
- ✓ 每轮对话后基于LLM分析计算理解度评分（仅在报告中展示）(ANLS-01) — v1.0
- ✓ LLM从每轮对话中提取理解盲区 (ANLS-02) — v1.0
- ✓ 每轮保存认知演进快照 (ANLS-03) — v1.0
- ✓ 导出认知诊断报告（Markdown格式）(REPT-01) — v1.0
- ✓ 测试发现的盲区自动提升SRS复习优先级 (REPT-02) — v1.0
- ✓ 认知测试数据表合并到现有SQLAlchemy/SQLite (INFR-01) — v1.0
- ✓ AI调用复用现有agno + LLM service层 (INFR-02) — v1.0
- ✓ 后端新增sse-starlette依赖 (INFR-03) — v1.0

### Active

(No active requirements — ready for v1.1 planning)

### Out of Scope

- 直接给答案模式 — 违背苏格拉底核心契约
- 6Agent完整对抗 — 对学习者压力过大
- 游戏化（积分、徽章、排行榜）— 导致刷分而非真正思考
- 实时显示理解度分数 — 学习者会优化分数而非真正推理
- 语音输入/输出 — 高复杂度低优先级，v1文本优先
- 同伴对比/社交功能 — 隐私问题
- 独立入口（不关联模型卡）— 概念锚定需要
- Per-Agent独立AI模型配置 — 复用现有统一LLM配置

## Context

**v1.0 shipped:** 2026-03-01
**Tech stack:** Vue3 + Pinia + FastAPI + SQLAlchemy/SQLite + agno + sse-starlette
**LOC added:** ~7,500 across 50 files
**Reference:** `ref/prodmindweb/` (ProdMind 2.0 — adapted engine concept)

**Known tech debt:**
- Report builder `category == "gap"` filter never matches persisted blind spots — "Improvement Suggestions" section always empty. Blind spot categories are `factual_error | incomplete_reasoning | hidden_assumption | surface_understanding`, not `gap`. Fix: update frontend report builder or add category mapping in backend.
- `CogTestTurn.analysis_json` stored as raw Text string — not indexed, no schema validation at DB level.
- Dead code in `cog_test_engine.py` line ~315: `blind_spot_count = 0` computed then immediately overwritten.

## Constraints

- **Tech stack**: 前端必须用Vue3重写，后端必须用FastAPI
- **Database**: 必须合并到现有SQLAlchemy ORM + SQLite，不引入Supabase
- **AI layer**: 必须复用现有agno + LLM service层，不单独引入OpenAI SDK调用
- **UX**: 对抗强度必须温和（苏格拉底式），不能让学习者感到被攻击

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 概念适配而非原样移植 | ProdMind的产品决策场景与学习场景不匹配，但多Agent对抗引擎的核心机制对学习有价值 | ✓ 成功 — 引擎核心保留，场景完全重写 |
| 2导师苏格拉底模式替代6Agent对抗 | 6Agent同时开火对学习者压力过大，温和引导更适合学习场景 | ✓ 成功 — 引导者+质疑者张力自然 |
| 从模型卡触发而非独立入口 | 认知测试需要具体概念作为锚点，模型卡是最自然的触发点 | ✓ 成功 — 概念自动预加载 |
| 随时可停而非固定轮次/达标结束 | 学习者应掌握节奏控制权，停止时给出当前诊断即可 | ✓ 成功 — stop端点是SRS提升保证触发点 |
| SSE而非WebSocket | EventSource原生支持断线重连，服务端推送场景足够 | ✓ 成功 — 但JWT必须通过query param传递 |
| stop端点作为SRS提升保证触发点 | EventSourceResponse生命周期内post-stream DB访问不可靠 | ✓ 成功 — _stream_with_elevation补充stream路径 |
| `<analysis>`分隔符而非纯JSON模式 | 允许自然对话文本+结构化JSON在同一响应中 | ✓ 成功 — parse_agent_output永不抛出异常 |
| _run_agent_turn作为普通协程（非异步生成器）| Python异步生成器不能return值同时yield | ✓ 成功 — 返回(AgentOutput, events, failed)元组 |
| stream_session双独立db参数 | 防止auth依赖和引擎共享同一async session（跨async边界不安全）| ✓ 成功 |
| 理解度评分仅在报告中显示 | 实时显示会导致学习者优化分数而非真正推理 | ✓ 成功 |

---
*Last updated: 2026-03-01 after v1.0 milestone*
