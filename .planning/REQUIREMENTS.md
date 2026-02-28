# Requirements: 认知对抗测试系统（Cognitive Adversarial Testing）

**Defined:** 2026-02-28
**Core Value:** 帮助学习者通过苏格拉底式对话发现认知盲区和薄弱点

## v1 Requirements

### Session（会话基础）

- [ ] **SESS-01**: 用户可从模型卡详情页发起认知对抗测试会话，概念内容自动预加载
- [ ] **SESS-02**: Agent回复通过SSE实时流式输出到前端，逐token显示
- [ ] **SESS-03**: 每轮对话基于完整历史上下文构建，Agent能引用前文内容
- [ ] **SESS-04**: 用户可随时停止测试，立即获得当前状态的认知诊断摘要
- [ ] **SESS-05**: 对话记录持久化到数据库，用户可查看历史会话列表
- [ ] **SESS-06**: 学习助手导航栏新增"认知测试"入口，可查看所有测试会话

### Agent（引擎）

- [ ] **AGNT-01**: 引导者Agent通过正面提问引导学习者深入理解概念
- [ ] **AGNT-02**: 质疑者Agent温和指出学习者回答中的矛盾和不完整之处
- [ ] **AGNT-03**: 两个Agent严格遵守苏格拉底契约——绝不直接给出答案，只通过提问引导思考
- [ ] **AGNT-04**: 轮次调度器决定每轮由哪个Agent发言，控制对话节奏和强度
- [ ] **AGNT-05**: Agent反馈解释为什么学习者的回答不完整，而非简单判定对错

### Analysis（认知分析）

- [ ] **ANLS-01**: 每轮对话后基于LLM分析计算理解度评分（仅在报告中展示，不实时显示）
- [ ] **ANLS-02**: LLM从每轮对话中提取理解盲区，分类为：缺口/已理解/不清楚
- [ ] **ANLS-03**: 每轮保存认知演进快照（状态树），记录理解度、盲区、薄弱点的变化

### Report（报告与集成）

- [ ] **REPT-01**: 用户可导出认知诊断报告（Markdown格式），包含概念、盲区、评分轨迹、建议
- [ ] **REPT-02**: 测试中发现的盲区自动提升对应模型卡在间隔重复系统中的复习优先级

### Infrastructure（基础设施）

- [ ] **INFR-01**: 认知测试相关数据表合并到现有SQLAlchemy/SQLite数据库
- [ ] **INFR-02**: AI调用复用现有agno + LLM service层，不引入新的AI SDK
- [ ] **INFR-03**: 后端新增sse-starlette依赖支持SSE事件流

## v2 Requirements

### Analysis

- **ANLS-04**: 跨轮矛盾检测——分析学习者在不同轮次中的自我矛盾，作为浅层理解的信号

### Mobile

- **MOBL-01**: 认知测试功能适配Android移动端（通过Capacitor）

### Persistence

- **PERS-01**: 盲区库跨会话持久化——同一概念多次测试的盲区累积追踪

## Out of Scope

| Feature | Reason |
|---------|--------|
| 直接给答案模式 | 违背苏格拉底核心契约，一旦给答案学习者会永远要求答案 |
| 6Agent完整对抗 | 对学习者压力过大，研究显示多Agent系统有从众失败风险 |
| 游戏化（积分、徽章、排行榜） | 导致学习者刷分而非真正思考 |
| 实时显示理解度分数 | 学习者会优化分数而非真正推理，分数只在报告中展示 |
| 语音输入/输出 | 高复杂度低优先级，v1文本优先 |
| 同伴对比/社交功能 | 隐私问题，与个人认知检测无关 |
| 独立入口（不关联模型卡） | 当前只从模型卡触发，保持概念锚定 |
| Per-Agent独立AI模型配置 | 复用现有统一LLM配置，降低复杂度 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SESS-01 | — | Pending |
| SESS-02 | — | Pending |
| SESS-03 | — | Pending |
| SESS-04 | — | Pending |
| SESS-05 | — | Pending |
| SESS-06 | — | Pending |
| AGNT-01 | — | Pending |
| AGNT-02 | — | Pending |
| AGNT-03 | — | Pending |
| AGNT-04 | — | Pending |
| AGNT-05 | — | Pending |
| ANLS-01 | — | Pending |
| ANLS-02 | — | Pending |
| ANLS-03 | — | Pending |
| REPT-01 | — | Pending |
| REPT-02 | — | Pending |
| INFR-01 | — | Pending |
| INFR-02 | — | Pending |
| INFR-03 | — | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 0
- Unmapped: 19 ⚠️

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 after initial definition*
