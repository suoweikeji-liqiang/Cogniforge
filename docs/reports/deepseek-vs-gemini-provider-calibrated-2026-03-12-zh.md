# DeepSeek V3.2 vs Gemini 3.1 Flash Lite 对照评估（校准后）

- 日期：2026-03-12
- 目标：校准此前对 `DeepSeek V3.2` 的速度判断，确认在不经过 OpenRouter provider 动态路由的条件下，`dashscope/deepseek-v3.2` 与 `google/gemini-3.1-flash-lite-preview` 哪个更适合作为 Cogniforge 的主力模型。
- 裁判模型：`gpt-5.4`
- 候选模型：
  - `dashscope/deepseek-v3.2`
  - `openrouter/google/gemini-3.1-flash-lite-preview`

## 测试方法

- DeepSeek 走阿里云 DashScope 官方 OpenAI 兼容接口，不经过 OpenRouter。
- Gemini 走 OpenRouter。
- 每个模型执行 5 轮。
- 场景覆盖：
  - Exploration Answer EN / ZH
  - Concept Extraction EN / ZH
  - Learning Path EN
  - Socratic Question EN / ZH
  - Structured Feedback EN / ZH
- 汇总权重沿用现有基准脚本：
  - Exploration：45%
  - Socratic（提问 + 反馈）：45%
  - Learning Path：10%

## 核心结果

| 模型 | 加权质量 | Exploration p50 | Socratic p50 | Path p50 | Native Schema Success | Fallback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `dashscope/deepseek-v3.2` | 93.83 | 10.383s | 15.638s | 29.597s | 96.0% | 4.0% |
| `openrouter/google/gemini-3.1-flash-lite-preview` | 93.17 | 4.919s | 6.886s | 3.604s | 100.0% | 0.0% |

## 详细解读

### 1. 之前对 DeepSeek 的速度判断，确实需要修正

此前 OpenRouter 下的 `deepseek/deepseek-v3.2` 明显更慢。直连 DashScope 后，DeepSeek 的延迟改善明显：

- Exploration p50：`14.040s -> 10.383s`
- Socratic p50：`21.447s -> 15.638s`

这说明此前的 OpenRouter provider routing 确实放大了 DeepSeek 的速度劣势。

### 2. 但修正后，DeepSeek 仍然不是快模型

即使按 DashScope 直连口径，DeepSeek 仍显著慢于 Gemini：

- Exploration：`10.383s vs 4.919s`
- Socratic：`15.638s vs 6.886s`
- Learning Path：`29.597s vs 3.604s`

尤其 `Learning Path` 是 Cogniforge 的核心结构化能力之一，这里 DeepSeek 的延迟和长尾都偏重。

### 3. DeepSeek 的质量略高，但差距不大

加权质量上，DeepSeek 略高：

- DeepSeek：`93.83`
- Gemini：`93.17`

差值只有 `0.66`。这说明：

- DeepSeek 的内容质量确实不差，甚至略优
- 但还没有高到足以抵消 2 到 8 倍的延迟劣势

### 4. Gemini 的结构化稳定性更好

- Gemini：`100%` native schema success，`0%` fallback
- DeepSeek：`96%` native schema success，`4%` fallback

Cogniforge 不是纯聊天应用，而是强结构化学习产品。这里 Gemini 更稳。

## 价格对比

### 官方单价

- `google/gemini-3.1-flash-lite-preview`（OpenRouter 当前公开价格）
  - 输入：`$0.25 / 1M tokens`
  - 输出：`$1.50 / 1M tokens`
- `dashscope/deepseek-v3.2`（阿里云百炼当前公开价格）
  - 输入：`2 元 / 1M tokens`
  - 输出：`3 元 / 1M tokens`

按 2026-03-12 查询到的汇率近似换算，`1 USD ≈ 6.87725 CNY`：

- `dashscope/deepseek-v3.2` 输入约为：`$0.29 / 1M`
- `dashscope/deepseek-v3.2` 输出约为：`$0.44 / 1M`

### 按本轮基准的加权成本估算

- `openrouter/google/gemini-3.1-flash-lite-preview`
  - 估算加权单轮成本：`$0.0004482`
- `dashscope/deepseek-v3.2`
  - 估算加权单轮成本：`¥0.0014313`
  - 约合：`$0.0002081`

按这组样本，DeepSeek 的单轮推理成本大约是 Gemini 的 `46%`，也就是便宜约 `54%`。

## 最终结论

### 是否需要修正我之前对 DeepSeek 的评价

需要。

更准确的结论应该是：

- 之前基于 OpenRouter 的 DeepSeek 速度判断偏悲观
- `dashscope/deepseek-v3.2` 已经是一个认真的候选，不该再被归类成“明显不适合主路径”
- 但如果你仍然坚持“质量 + 速度”为第一优先级，Gemini 依然更适合默认主力

### 当前推荐

1. 默认主力：`google/gemini-3.1-flash-lite-preview`
   - 原因：速度明显更好，结构化输出更稳，适合主学习工作区这种高交互场景
2. 质量/成本导向备选：`dashscope/deepseek-v3.2`
   - 原因：质量略优，输出成本更低，但交互延迟明显更高

### 什么时候应该选 DeepSeek

适合：

- 你更看重答案质量边际提升
- 你对 `Learning Path` 的等待时间更能容忍
- 你希望把长期推理成本压下来

不适合：

- 你要把主工作区默认响应时间压到 5 到 7 秒级别
- 你非常在意结构化场景的稳定低延迟

## 原始结果

- Gemini 原始结果：`/Users/asteroida/work/Cogniforge/output/provider-calibration/20260312T070456Z/results.json`
- Gemini 机器报告：`/Users/asteroida/work/Cogniforge/docs/reports/provider-calibration-20260312T070456Z.md`
- DeepSeek 原始结果：`/Users/asteroida/work/Cogniforge/output/provider-calibration/20260312T065119Z/results.json`
- DeepSeek 机器报告：`/Users/asteroida/work/Cogniforge/docs/reports/provider-calibration-20260312T065119Z.md`
