# Learning Loop Hardening Plan (2026-03-05)

> Archived on 2026-03-11.
> Superseded by `/Users/asteroida/work/Cogniforge/docs/plans/2026-03-10-focused-milestone-and-hardening-plan.md`.
> Preserved as historical planning context, not as the active execution plan.

## 1. 背景与目标

### 1.1 背景问题
当前学习链路存在以下高风险点：
1. 学习推进缺少可证明掌握度闭环（依赖 correctness 文本语义）。
2. 自动推进依赖关键词规则，鲁棒性不足。
3. 新概念自动回写无置信度与人工确认，噪声不可控。
4. 知识图谱主要由统计接口拼装，缺独立概念/关系实体治理。
5. `/problems/{id}/ask` 与概念沉淀、路径更新链路断裂。
6. 一次作答涉及多次 LLM 调用，缺预算守卫与策略化降级。
7. 关键流程缺针对性自动化回归用例。

### 1.2 目标
1. 建立“可解释、可追踪、可回滚”的学习推进闭环。
2. 将关键流程从文本脆弱规则升级为结构化判定。
3. 将概念体系从“展示层”升级为“可治理知识层”。
4. 控制成本与延迟，保障在异常场景下稳定退化。

### 1.3 非目标（本轮不做）
1. 不重做前端视觉交互，仅做必要 API/字段适配。
2. 不引入复杂编排框架（如全量状态机重构）。

## 2. 关键成功指标（验收口径）
1. 自动推进误判率（误推进+误卡住）较基线下降 >= 40%。
2. 每次 `/responses` 链路 P95 延迟下降 >= 25%，超时错误率 < 1%。
3. 概念噪声率（后续被回滚/驳回占比）下降 >= 50%。
4. `/ask` 触发的有效概念沉淀覆盖率 >= 60%。
5. 新增关键回归用例覆盖：自动推进、概念回写、`/ask` 融合、降级分支。

## 3. 分阶段实施

### P0（3-5天）：可观测性 + 成本守卫 + 降级策略
目标：先控风险，避免链路雪崩。

交付：
1. 为 `/responses`、`/ask` 增加链路观测字段：`trace_id`、`llm_calls`、`llm_latency_ms`、`fallback_reason`。
2. 增加请求级预算守卫：
   - `PROBLEM_MAX_LLM_CALLS_PER_REQUEST`
   - `PROBLEM_RESPONSE_TIMEOUT_SECONDS`
3. 增加降级序列：
   - 结构化反馈失败 -> 使用最小结构 fallback。
   - 概念抽取失败 -> 仅保留 step_concept，不扩写。
   - 超预算 -> 跳过“低优先级”调用（如概念扩展）。
4. 将关键指标落表，便于统计回归。

### P1（1-2周）：掌握度闭环 + 自动推进 V2
目标：从关键词判定迁移到量表判定。

交付：
1. 反馈结构扩展：
   - `mastery_score: int (0-100)`
   - `dimension_scores: {accuracy, completeness, transfer, rigor}`
   - `confidence: float (0-1)`
   - `pass_stage: bool`
   - `decision_reason: str`
2. 重写 `_should_auto_advance`：
   - 以阈值策略替代关键词包含。
   - 支持连续达标（例如连续 2 次达标才推进）。
3. 加入 feature flag：
   - `PROBLEM_AUTO_ADVANCE_V2_ENABLED`
   - 支持快速回退旧逻辑。

### P2（1-2周）：概念治理（候选、确认、归一、回滚）
目标：降低自动写回噪声，构建可治理概念流。

交付：
1. 新概念先入候选池：`pending -> accepted/rejected`。
2. 引入概念置信度与来源：
   - `source`: response / ask / manual
   - `confidence`
3. 同义词归一：`canonical_concept + aliases`。
4. 回滚机制：对“accepted”概念保留审计记录与回滚操作。

### P3（1周）：`/ask` 融合沉淀链路
目标：消除提问链路断层。

交付：
1. `/ask` 产出的回答进入同一概念候选管道。
2. 根据问答质量信号更新“阶段进展建议”，但默认不直接推进步数。
3. 新增“问答沉淀”事件记录，统一进入统计口径。

### P4（1-2周）：知识图谱实体化
目标：将图谱从临时拼装转为可治理实体层。

交付：
1. 新增实体：`concepts`、`concept_aliases`、`concept_relations`、`concept_evidences`。
2. 统计图谱接口从读 JSON 拼装转为读实体关系。
3. 关系支持来源追踪与版本字段，支持后续长期分析。

### P5（1周并持续）：测试与发布保护
目标：建立高风险流程回归保护。

交付：
1. 新增后端自动化回归：
   - 自动推进边界（达标/未达标/连续达标）
   - 概念候选确认与回滚
   - `/ask` 沉淀联通
   - 超时/超预算降级路径
2. 为 LLM 输出增加结构契约测试（JSON shape + 必填字段）。

## 4. 数据模型与迁移草案

### 4.1 新增表（建议）
1. `problem_mastery_events`
   - `id, problem_id, step_index, mastery_score, confidence, pass_stage, decision_reason, created_at`
2. `concepts`
   - `id, canonical_name, language, status, created_at, updated_at`
3. `concept_aliases`
   - `id, concept_id, alias, normalized_alias, created_at`
4. `concept_relations`
   - `id, source_concept_id, target_concept_id, relation_type, weight, version, created_at`
5. `concept_evidences`
   - `id, concept_id, source_type, source_id, snippet, confidence, created_at`
6. `problem_concept_candidates`
   - `id, problem_id, concept_text, normalized_text, source, confidence, status, reviewer_id, reviewed_at, created_at`
7. `learning_events`
   - `id, user_id, problem_id, event_type, trace_id, payload_json, created_at`

### 4.2 兼容策略
1. 旧字段 `problem.associated_concepts` 暂保留，作为过渡读模型。
2. 新旧双写一段时间，待前端和统计完成切换后再裁剪旧路径。

## 5. 配置与开关
1. `PROBLEM_AUTO_ADVANCE_V2_ENABLED=false`（默认关闭，灰度开启）
2. `PROBLEM_MAX_LLM_CALLS_PER_REQUEST=3`
3. `PROBLEM_RESPONSE_TIMEOUT_SECONDS=20`
4. `PROBLEM_CONCEPT_AUTO_ACCEPT_CONFIDENCE=0.85`
5. `PROBLEM_CONCEPT_MAX_CANDIDATES_PER_TURN=5`

## 6. 风险与回滚
1. 风险：量表提示词不稳定导致误判。
   - 处理：V1/V2 双轨 + feature flag 一键回退。
2. 风险：概念候选堆积影响体验。
   - 处理：自动阈值接收 + 每日批处理清理低置信候选。
3. 风险：实体化迁移影响图谱查询性能。
   - 处理：索引 + 分页 + 统计缓存。

## 7. 里程碑
1. M1（P0完成）：可观测和守卫上线，错误可定位。
2. M2（P1完成）：自动推进 V2 灰度，误判显著下降。
3. M3（P2+P3完成）：概念治理与 `/ask` 融合闭环。
4. M4（P4+P5完成）：图谱实体化与回归体系稳定。
