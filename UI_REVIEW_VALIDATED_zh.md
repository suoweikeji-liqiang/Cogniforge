# Cogniforge UI 审查结论校正版

## 范围

本文用于校验并整合以下两份报告的结论：

- `UI_INTERACTION_AUDIT.md`
- `UI_UX_审核报告.md`

校验基线：

- `las_frontend/src` 下的当前前端实现
- `las_frontend/tests` 下已有的 Playwright 用例
- `AGENTS.md` 中的产品约束与工作原则

审查日期：2026-03-11

---

## 总体判断

这两份报告在方向上有参考价值，但不能直接作为最终结论使用。

- 约 70% 的战略判断是成立的
- 约 30% 的表述存在夸大、失真，或与当前实现不一致

更准确的结论不是“当前产品没有学习主线”，而是：

> 主学习闭环已经存在，并且部分关键流程已有测试保护；当前问题在于，UI 在这条主线上同时暴露了过多并行信息和次级决策。

这个区分非常重要。如果把问题误判成“没有主路径”，很容易推动一次过度的页面或路由重写，反而破坏当前已经存在的学习模式结构。

---

## 两份报告判断正确的部分

### 1. Dashboard 的焦点被稀释了

这一点成立。

当前 `DashboardView.vue` 同时给用户展示了：

- 一个 Focus Card
- 三个指标卡
- 最近问题
- 复习队列
- 最近模型卡
- 四个快速操作

这些区域里有多处在表达相近的“下一步”，导致首页虽然存在主推荐动作，但它并没有获得足够明确的视觉和任务优先级。

核对依据：

- `las_frontend/src/views/DashboardView.vue`

### 2. ProblemDetail 的确是主工作区，但信息密度过高

这一点成立，而且是核心问题。

`ProblemDetailView.vue` 目前已经承担了学习闭环中的中心职责，包含：

- 学习模式状态
- 学习路径导航
- 当前步骤与进度
- 当前回合交互
- 回合结果
- 衍生概念
- 衍生路径
- 笔记与资源
- 复习回流与强化上下文

这里的问题不是“产品结构缺失”，而是“产品结构一次性暴露得太多”。

核对依据：

- `las_frontend/src/views/ProblemDetailView.vue`

### 3. Reviews 页面混合了多个不同概念

这一点成立。

当前 `ReviewsView.vue` 同时混合了：

- SRS 复习队列和启动入口
- 模型卡生命周期状态
- 手动创建的 Review Archive

这些内容相关，但并不属于同一类用户任务。页面现在更像“复习生命周期总览”，而不是一个单一任务界面。

核对依据：

- `las_frontend/src/views/ReviewsView.vue`

### 4. Model Cards 列表页信息密度过高

这一点成立。

当前 `ModelCardsView.vue` 的单张卡片可能同时展示：

- 生命周期阶段
- 版本与统计信息
- 演化状态
- 记忆状态
- 推荐动作
- 强化状态
- 最多四个操作按钮

这些信息本身并非无意义，但在列表页同时平铺，会显著提高扫描成本。

核对依据：

- `las_frontend/src/views/ModelCardsView.vue`

### 5. 次级页面仍然会带来产品定位上的模糊

这一点成立。

- `ChatView.vue` 已被明确标注为 legacy
- `PracticeView.vue` 和 `SRSReviewView.vue` 已被明确标注为 secondary surface

这说明代码层面已经知道哪些是主线、哪些是次级面，但这些页面依然存在，仍然会要求用户自己理解其定位。

核对依据：

- `las_frontend/src/views/ChatView.vue`
- `las_frontend/src/views/PracticeView.vue`
- `las_frontend/src/views/SRSReviewView.vue`

---

## 两份报告不准确或夸大的部分

### 1. “产品没有主路径”

这个结论被夸大了。

当前主路径在代码和测试里都已经可见：

- Problems 是主工作区入口
- ProblemDetail 承担核心学习闭环
- 衍生概念可以转成 model card
- model card 可以进入 SRS review
- 脆弱记忆状态会把用户引回 workspace 做 reinforcement

这些流程不是设想，而是已经被 Playwright 用例覆盖。

核对依据：

- `las_frontend/tests/problem-detail-workflow.spec.ts`
- `las_frontend/tests/app-shell-nav.spec.ts`

### 2. “学习模式切换只是改文案”

这个结论不成立。

当前实现中，`socratic` 和 `exploration` 是两套明确区分的交互协议：

- 不同的交互界面
- 不同的提交流程
- 不同的流式处理逻辑
- Socratic 显式带有 `question_kind`
- Exploration 显式带有 `answer_type`
- 两者有不同的回合结果与后续动作

这和 `AGENTS.md` 对学习模式的要求是一致的。

核对依据：

- `las_frontend/src/views/problem-detail/learningActions.ts`
- `las_frontend/src/components/problem-workspace/ProblemTurnOutcomePanel.vue`

### 3. “用户在导航中直接面对 14+ 个顶级页面”

这作为 UI 结论并不准确。

虽然路由文件里确实存在较多页面，但当前认证后的主导航只暴露了四个一级入口：

- Dashboard
- Problems
- Model Cards
- Reviews

因此，信息架构层面“路由很多”是事实，但“用户首页直接面对 14 个平级入口”并不是事实。

核对依据：

- `las_frontend/src/router/index.ts`
- `las_frontend/src/App.vue`

### 4. “复习完成后只显示下次复习时间”

这个结论不成立。

当前 `SRSReviewView.vue` 已经展示了：

- 上一次复习结果
- recall state
- recommended action
- 需要强化时的 reinforcement 状态
- 回到 workspace 或 model card 的链接

更准确的批评不是“没有反馈”，而是“反馈分散在 Reviews、SRS、Model Card 和 Workspace Reinforcement 几个面之间”。

核对依据：

- `las_frontend/src/views/SRSReviewView.vue`

### 5. 大规模重写路由和信息架构应该作为第一步

这和当前仓库约束并不匹配。

按照 `AGENTS.md`：

- ProblemDetail 应继续作为主学习工作区
- 学习模式必须保持显式建模
- 修改应尽量增量且收敛

因此，像 `/workspace`、`/library` 这类整体命名重组和大规模 IA 重写，可以作为远期方向讨论，但不应该作为当前仓库的第一优先级动作。

---

## 修正后的产品诊断

当前 UI 对学习系统的表达，其实比两份报告所描述的更完整：

- 双学习模式是显式的
- 衍生概念是结构化产物
- 衍生路径候选是可执行的
- branch 和 return flow 已存在
- reinforcement 可以把用户带回 workspace

真正的问题在于：

1. 系统一次暴露了太多状态
2. 主操作与辅助上下文的层级仍然不够强
3. 次级页面仍会削弱用户对主线的信心
4. Reviews 相关概念被语义混放
5. 列表页过早暴露了过多运营细节

所以这更像是“渐进披露不足”和“流程表达不够清晰”的问题，而不是“产品没有学习架构”的问题。

---

## 建议的优先级

### P0：在不改变产品模型的前提下，先把现有主线讲清楚

建议优先做：

- 围绕一个主动作简化 Dashboard
- 减少首页上的重复导航入口
- 让 Reviews 更明确地承担一个主要任务

不建议第一步就做：

- 全量路由重命名
- 顶层信息架构大改
- 把核心学习流程从 ProblemDetail 拆散到多个页面

### P1：在同一个工作区内降低 ProblemDetail 的认知负担

建议方向：

- 保留 ProblemDetail 作为主工作区
- 在页面内部加强“分阶段显示”
- 保持学习交互处于主位置
- 对概念管理、路径管理等信息做折叠、延后或上下文触发

这比把核心学习工作拆到多个独立页面，更符合当前仓库的产品约束。

### P1：拆分 review 的语义，而不一定拆分 review 的入口

更合理的方向是：

- 在概念上把 SRS 执行和手动 review archive 区分开
- 保留从“当前到期复习”直接进入 SRS 的能力
- 避免为了开始复习而强迫用户多跳一层页面

### P1：简化 model card 列表卡片

列表页优先强调：

- 概念标题
- 一个主要状态
- 一个主要动作

详细的演化信息和强化分析可以保留在详情页中。

### P2：增强连续性和迷路恢复能力

例如：

- 更强的“继续当前任务”提示
- 更好的空状态引导
- 更清楚地解释为什么 concept 会变成 model card
- 更清楚地解释为什么 fragile review 会把用户带回 workspace

---

## 可执行结论

如果要把这两份报告用于规划，它们应被视为“原始输入”，而不是“已确认结论”。

当前最可靠的合并结论是：

1. 保留现有学习闭环架构
2. 围绕这条闭环简化 UI 表达
3. 降低 Reviews 页面中的语义混杂
4. 降低 Dashboard 与 Model Cards 的信息密度
5. 继续把 ProblemDetail 作为主工作区，并在其中加强分阶段披露

这比基于“产品没有可用主线”去做一次大范围重写，更安全，也更符合当前仓库约束。
