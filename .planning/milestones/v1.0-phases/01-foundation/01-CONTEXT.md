# Phase 1: Foundation - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock infrastructure and design decisions: DB schema for cognitive testing tables, SSE dependency, LLM streaming extension, agent prompt design validated against Socratic contract. No UI, no API endpoints, no frontend work.

</domain>

<decisions>
## Implementation Decisions

### 导师人设与语气
- 引导者Agent: 温暖同伴风格，耐心鼓励，用"你觉得呢？""如果是这样的话…"引导思考
- 质疑者Agent: 随和但精准，先肯定再提问，"有意思，不过如果换个角度看…"
- 两者都用中文，口语化，不学术腔
- 绝不直接给答案，只通过提问引导（苏格拉底契约）

### Agent输出格式
- 面向用户的回复：自然对话文本（不是结构化markdown）
- 面向系统的分析：JSON结构化输出（盲区提取、评分），用户不可见
- 每次Agent调用产生两部分——对话文本 + 隐藏分析JSON
- 参考ProdMind的parsers.ts但改用JSON-mode而非正则提取（研究建议避免正则静默失败）

### 盲区分类体系
- factual_error: 事实错误（概念理解有误）
- incomplete_reasoning: 推理不完整（逻辑链断裂）
- hidden_assumption: 隐含假设（未经检验的前提）
- surface_understanding: 表面理解（能复述但不能应用）

### 理解度评分
- 粗粒度三档：low / medium / high
- 报告中展示为描述性文字而非百分比数字（避免学习者刷分心态）
- 评分仅在报告中展示，对话过程中不显示

### Claude's Discretion
- DB表的具体字段设计和索引策略
- LLM streaming的具体实现方式（AsyncOpenAI vs httpx streaming）
- Alembic迁移 vs auto-create的选择
- Agent system prompt的具体措辞（遵循上述人设约束即可）
- sse-starlette的具体集成方式

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LLMService` (las_backend/app/services/llm_service.py): 现有LLM调用层，支持openai/anthropic/ollama，需扩展streaming方法
- `Base` (las_backend/app/core/database.py): SQLAlchemy DeclarativeBase，新表继承此基类
- `User` model (las_backend/app/models/entities/user.py): 所有实体通过user_id关联，UUID string PK模式

### Established Patterns
- 所有model在entities/目录下，UUID string(36) PK，datetime默认值
- 关系通过relationship + back_populates定义
- LLMService是单例模式（模块级llm_service实例）
- 现有LLM调用是同步OpenAI client包在async函数里（需改为真正async streaming）

### Integration Points
- 新表需加到entities/目录并在__init__.py注册
- LLMService需新增stream_generate()方法
- ModelCard模型是认知测试的触发点（需关联）

</code_context>

<specifics>
## Specific Ideas

- 参考ProdMind的engine架构（scheduler, debate, roles, parsers, context-builder）但适配为Python/FastAPI
- Agent prompt设计是Phase 1最关键的交付物——研究指出prompt漂移（偷偷给答案）是最高风险
- 质疑者温度可以略高于引导者（参考ProdMind: devil's advocate用0.8，其他用0.4）

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-28*
