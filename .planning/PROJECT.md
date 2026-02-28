# 认知对抗测试系统（Cognitive Adversarial Testing）

## What This Is

将 ProdMind 的多Agent对抗辩论引擎概念适配到学习场景，为学习助手新增"认知对抗测试"模块。学习者从模型卡发起测试，两个苏格拉底式AI导师（引导者 + 质疑者）通过对话帮助发现理解盲区，追踪理解度评分，生成认知诊断报告。

## Core Value

帮助学习者通过结构化的苏格拉底式对话，发现自己对概念的认知盲区和薄弱点——不是灌输知识，而是暴露理解的缺口。

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] 从模型卡发起认知对抗测试会话
- [ ] 两个AI导师角色：引导者（正面引导理解）+ 质疑者（温和指出矛盾）
- [ ] SSE实时流式输出导师对话
- [ ] 轮次调度器（决定每轮哪个导师发言）
- [ ] 理解盲区库（从对话中提取学习者的认知缺口）
- [ ] 认知薄弱点追踪（类似ProdMind风险库）
- [ ] 理解度评分（类似ProdMind置信度指数）
- [ ] 认知演进快照（每轮保存状态树快照）
- [ ] 随时可停 + 当前状态诊断
- [ ] 认知诊断报告导出（Markdown格式）
- [ ] 学习助手导航栏新增"认知测试"入口
- [ ] 数据合并到现有SQLAlchemy/SQLite数据库

### Out of Scope

- 原样移植ProdMind的产品决策场景 — 与学习场景不匹配
- 6个Agent完整对抗模式 — 对学习者压力过大，采用2导师温和模式
- 独立入口（不关联模型卡）— 当前只从模型卡触发
- Per-Agent独立AI模型配置 — 复用现有统一LLM配置
- Android移动端适配 — 未确认，暂不纳入v1
- Supabase数据库 — 合并到现有SQLite/SQLAlchemy

## Context

- 参考实现：`ref/prodmindweb/`（ProdMind 2.0 Web，Next.js + React + Supabase）
- 现有学习助手技术栈：Vue3 + FastAPI + SQLAlchemy + agno LLM层
- ProdMind核心引擎文件：`src/lib/engine/`（scheduler, debate, roles, parsers, context-builder, export）
- 学习助手已有矛盾日志（Contradiction Log）概念，认知对抗测试是其自然升级
- 学习助手已有模型卡、间隔重复、认知挑战等功能，认知测试与这些形成互补

## Constraints

- **Tech stack**: 前端必须用Vue3重写（不能用React），后端必须用FastAPI（不能用Next.js API Routes）
- **Database**: 必须合并到现有SQLAlchemy ORM + SQLite，不引入Supabase
- **AI layer**: 必须复用现有agno + LLM service层，不单独引入OpenAI SDK调用
- **UX**: 对抗强度必须温和（苏格拉底式），不能让学习者感到被攻击

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 概念适配而非原样移植 | ProdMind的产品决策场景与学习场景不匹配，但多Agent对抗引擎的核心机制对学习有价值 | — Pending |
| 2导师苏格拉底模式替代6Agent对抗 | 6Agent同时开火对学习者压力过大，温和引导更适合学习场景 | — Pending |
| 引导者 + 质疑者角色分工 | 一个从正面引导理解，一个温和指出矛盾，形成建设性张力 | — Pending |
| 从模型卡触发而非独立入口 | 认知测试需要具体概念作为锚点，模型卡是最自然的触发点 | — Pending |
| 随时可停而非固定轮次/达标结束 | 学习者应掌握节奏控制权，停止时给出当前诊断即可 | — Pending |

---
*Last updated: 2026-02-28 after initialization*
