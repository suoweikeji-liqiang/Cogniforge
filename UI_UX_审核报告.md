# Cogniforge UI/UX 产品交互质量审核报告

## 1. 产品主线判断

**核心任务：** Cogniforge 是一个认知学习引擎，核心任务是帮助用户通过"问题工作区"进行深度学习，将理解转化为结构化的"模型卡片"，并通过间隔重复系统（SRS）巩固知识。

**用户主路径：**
1. 创建 Problem（学习问题）→ 进入 Problem Workspace（工作区）→ 通过对话/步骤学习
2. 从学习中提取 Concept → 转化为 Model Card（模型卡片）
3. 将 Model Card 加入 Review 队列 → 定期复习巩固

**当前主线清晰度：** ⚠️ **主线存在但被稀释**

导航显示 4 个平级入口（Dashboard、Problems、Model Cards、Reviews），但它们之间的**流程关系不明确**。用户看到的是"四个功能模块"，而不是"一条学习主线的不同阶段"。

**总体评价：** 系统功能完整，但**缺少单一主任务的推进感**。页面在展示系统能力，但没有清晰引导用户"当前应该做什么、下一步去哪里"。

---

## 2. 关键问题列表

### [P0] Dashboard 缺少明确的主操作入口

**位置：** `DashboardView.vue` 整体布局

**现象：**
- Dashboard 展示了 6 个区域：Hero + Focus Card + 3 个 Metrics + 2 个面板（Recent Problems、Review Queue）+ Model Cards 面板 + 4 个 Quick Actions
- 信息密度高，但**没有一个明确的"当前最重要动作"**
- Focus Card 虽然存在，但被淹没在众多信息中
- Quick Actions 区域有 4 个平级按钮，用户不知道先点哪个

**为什么是问题：**
这是典型的"功能堆砌"而非"任务推进"。用户进入 Dashboard 后会感到迷失：
- "我应该先看哪里？"
- "我现在应该做什么？"
- "这些数字和列表是让我了解状态，还是让我采取行动？"

**建议修改：**
1. **重构 Dashboard 为任务驱动型首页：**
   - 将 Focus Card 放大并置顶，作为**唯一主操作**
   - 将 Metrics 和面板降级为"上下文信息"，缩小视觉权重
   - 移除 Quick Actions 区域（这些操作应该在主流程中自然出现，而不是作为"快捷方式"堆在首页）

2. **建议结构：**
   ```
   [大号 Focus Card - 当前最重要的任务]
   ↓
   [进度概览 - 3 个 Metrics，小尺寸]
   ↓
   [最近活动 - 合并 Recent Problems + Review Queue，单列显示]
   ```

**是否涉及结构性重构：** 是

---

### [P0] Problem Workspace 职责混乱，一个页面承担多阶段任务

**位置：** `ProblemDetailView.vue` (76KB 超大文件)

**现象：**
- 页面同时包含：
  - Workspace Overview（概览）
  - Learning Path（学习路径）
  - Conversation（对话）
  - Derived Concepts（概念提取）
  - Concept Candidates（候选概念）
  - Associated Concepts（关联概念）
  - Learning Events（学习事件）
- 所有内容在同一个页面中，通过折叠/展开控制
- 用户需要在"学习模式"和"管理模式"之间切换，但界面没有明确区分

**为什么是问题：**
这是**工程视角过强，用户视角过弱**的典型案例：
- 开发者把所有相关数据都放在一个"详情页"，但用户的心智模型是：
  - "我现在在学习" vs "我在整理学到的东西" vs "我在查看历史记录"
- 页面缺少**阶段感**，用户不知道"当前处于学习流程的哪个阶段"

**建议修改：**
1. **将 Problem Workspace 拆分为三个明确的阶段视图：**
   - **Learning Mode（学习模式）：** 只显示 Learning Path + Conversation，聚焦当前学习任务
   - **Concept Extraction（概念提取）：** 学习完成后进入，专注于提取和确认概念
   - **Workspace Archive（工作区归档）：** 查看历史对话、学习事件、关联概念

2. **用明确的阶段切换按钮或进度条引导用户：**
   ```
   [学习中] → [提取概念] → [归档查看]
   ```

3. **每个阶段只显示当前需要的信息，隐藏其他内容**

**是否涉及结构性重构：** 是

---

### [P1] 导航结构扁平化，缺少层级关系

**位置：** `App.vue` 导航栏 + `router/index.ts`

**现象：**
- 主导航显示 4 个平级入口：Dashboard、Problems、Model Cards、Reviews
- 路由中还有 10+ 个其他页面（Chat、SRS Review、Knowledge Graph、Challenges、Resources、Notes、Cog Test 等）
- 这些页面没有出现在主导航中，用户不知道它们的存在和入口

**为什么是问题：**
- **主导航没有反映真实的用户流程**：Problems → Model Cards → Reviews 是顺序关系，但导航呈现为并列关系
- **隐藏页面缺少入口**：Chat、Knowledge Graph、Challenges 等功能存在但用户找不到
- **心智模型不统一**：用户不知道"这个系统到底有多少功能？它们之间是什么关系？"

**建议修改：**
1. **重构导航为任务流程导向：**
   ```
   [工作台 Dashboard]
   [学习 Problems] → 点击后进入 Problem Workspace
   [模型库 Model Cards] → 从 Problems 中提取的概念
   [复习 Reviews] → 巩固 Model Cards
   ```

2. **将隐藏功能整合到主流程中：**
   - Chat → 合并到 Problem Workspace 的对话功能
   - Knowledge Graph → 作为 Model Cards 的可视化视图
   - Challenges、Resources、Notes → 如果不是核心功能，考虑移除或降级为"工具"区域

3. **如果功能确实很多，考虑二级导航：**
   ```
   主导航：[工作台] [学习] [复习]
   学习子导航：[问题工作区] [模型库] [知识图谱]
   ```

**是否涉及结构性重构：** 是

---

### [P1] Chat 页面存在但被标记为"Legacy"，用户困惑

**位置：** `ChatView.vue`

**现象：**
- Chat 页面顶部有一个醒目的 "Legacy Banner"，提示用户这是旧功能
- Banner 建议用户去 Problems 页面，但没有解释为什么
- Chat 功能本身仍然可用，但用户不知道应该用还是不应该用

**为什么是问题：**
- **产品方向不明确**：如果 Chat 是旧功能，为什么还保留？如果要废弃，为什么不直接移除？
- **用户体验割裂**：用户可能从某个地方进入 Chat，看到 Banner 后感到困惑："我是不是走错地方了？"
- **功能重复**：Chat 和 Problem Workspace 的对话功能重复，增加维护成本和用户困惑

**建议修改：**
1. **明确产品决策：**
   - 如果 Chat 功能已被 Problem Workspace 替代 → **直接移除 Chat 页面**，将所有对话功能统一到 Problem Workspace
   - 如果 Chat 有独特价值（如自由对话、不绑定 Problem）→ **重新定位 Chat 的用途**，给它一个明确的使用场景

2. **如果保留 Chat：**
   - 移除 "Legacy" 标签，重新命名为"自由对话"或"探索对话"
   - 在导航中给它一个明确的位置
   - 解释它与 Problem Workspace 的区别

**是否涉及结构性重构：** 是（如果移除）

---

### [P1] Model Cards 页面信息过载，卡片承载过多状态

**位置：** `ModelCardsView.vue`

**现象：**
- 每个 Model Card 显示：
  - Title + Lifecycle Stage Badge
  - User Notes / Draft Summary
  - Card Stats (version, examples, counter examples)
  - Evolution State Strip (state pill + summary)
  - Recall Strip (recall pill + copy)
  - Recall Next Action
  - Reinforcement Info
  - 4 个操作按钮（View、Add to Review、Counter Examples、Suggest Transfer）
- 单个卡片信息密度极高，用户需要解析大量状态信息

**为什么是问题：**
- **认知负担过重**：用户看到一个卡片需要理解 5+ 种状态（lifecycle、evolution、recall、reinforcement 等）
- **主次不分**：所有信息平铺展示，用户不知道哪些是重要的、哪些是次要的
- **操作按钮过多**：4 个按钮并列，用户不知道先点哪个

**建议修改：**
1. **简化卡片显示，只保留核心信息：**
   ```
   [Title + Lifecycle Badge]
   [User Notes - 一行摘要]
   [主要状态 - 只显示最重要的一个状态]
   [主操作按钮 - 只显示当前最需要的操作]
   ```

2. **将详细信息移到卡片详情页：**
   - Evolution State、Recall Strip、Reinforcement Info 等技术细节应该在点击卡片后的详情页中显示
   - 列表页只显示"用户需要知道的最少信息"

3. **操作按钮优先级：**
   - 如果卡片是 Draft → 主按钮是"Activate"
   - 如果卡片未加入复习 → 主按钮是"Add to Review"
   - 如果卡片需要复习 → 主按钮是"Start Review"
   - 其他操作（Counter Examples、Suggest Transfer）移到详情页或下拉菜单

**是否涉及结构性重构：** 否（但需要大幅简化）

---

### [P1] Reviews 页面混合了三种不同的"Review"概念

**位置：** `ReviewsView.vue`

**现象：**
- 页面包含三个区域：
  1. **Review Queue（SRS 复习队列）：** 需要复习的 Model Cards
  2. **Model Cards Lifecycle（模型卡片生命周期）：** 所有 Model Cards 的状态
  3. **Review Archive（复习归档）：** 用户创建的 Daily/Weekly/Monthly Review

- 这三个区域的"Review"含义完全不同：
  - Review Queue = SRS 间隔重复复习
  - Model Cards Lifecycle = 查看卡片状态
  - Review Archive = 学习总结/反思

**为什么是问题：**
- **概念混淆**：用户看到"Reviews"页面，不知道这是"复习卡片"还是"查看总结"
- **页面职责不清**：一个页面承担了"任务执行"（SRS 复习）、"状态查看"（Model Cards）、"内容管理"（Review Archive）三种职责
- **用户流程断裂**：用户想"开始复习"，但页面上有三个区域，不知道从哪里开始

**建议修改：**
1. **拆分为两个独立页面：**
   - **SRS Review（间隔复习）：** 专注于 SRS 复习任务，包含 Review Queue + 开始复习的主操作
   - **Learning Journal（学习日志）：** 专注于学习总结和反思，包含 Daily/Weekly/Monthly Review Archive

2. **移除 Model Cards Lifecycle 区域：**
   - 这个区域实际上是 Model Cards 页面的重复
   - 如果用户想查看 Model Cards 状态，应该去 Model Cards 页面
   - 如果需要快速访问，可以在 Dashboard 显示"需要关注的卡片"

3. **重命名导航：**
   - 将"Reviews"改为"复习"或"SRS Review"，明确这是间隔重复复习功能

**是否涉及结构性重构：** 是

---

### [P2] Problems 列表页缺少"继续学习"的明确入口

**位置：** `ProblemsView.vue`

**现象：**
- Problems 列表显示所有问题，每个卡片显示 Title、Description、Status、Learning Mode、Concepts
- 卡片底部有"Open Workspace →"文案，但不够突出
- 用户看到的是"问题列表"，而不是"我的学习任务列表"

**为什么是问题：**
- **缺少任务感**：列表页像"档案库"，而不是"待办任务"
- **状态不够明确**：Status 显示"new"、"in-progress"、"completed"，但用户不知道"in-progress 的问题我学到哪一步了？"
- **主操作不突出**："Open Workspace"只是一个小文案，不像主操作按钮

**建议修改：**
1. **将 Problems 列表改为"学习任务列表"：**
   - 对于 in-progress 的问题，显示"继续学习"按钮 + 进度信息（如"Step 3/5"）
   - 对于 new 的问题，显示"开始学习"按钮
   - 对于 completed 的问题，降低视觉权重或移到"已完成"标签页

2. **增加进度可视化：**
   - 在卡片上显示进度条或步骤数
   - 让用户一眼看到"我还有多少任务要做"

3. **优化排序：**
   - 默认排序应该是"最近活动"，把 in-progress 的问题排在最前面
   - 让用户优先看到"当前应该继续的任务"

**是否涉及结构性重构：** 否

---

### [P2] 缺少全局的"当前任务"指示器

**位置：** 全局导航 `App.vue`

**现象：**
- 导航栏只显示页面链接，没有显示"当前正在进行的任务"
- 用户在不同页面之间跳转时，容易忘记"我刚才在做什么"

**为什么是问题：**
- **上下文丢失**：用户从 Problem Workspace 跳到 Model Cards，再回到 Dashboard，不记得"我刚才在学习哪个问题"
- **缺少连续性**：系统没有帮助用户维持"当前任务"的心智模型

**建议修改：**
1. **在导航栏增加"当前任务"指示器：**
   ```
   [Logo] [导航链接...] [当前任务: Problem Title] [用户信息]
   ```

2. **或者在页面顶部增加面包屑导航：**
   ```
   Dashboard > Problems > "控制理论基础" > Learning Path
   ```

3. **提供"返回当前任务"的快捷方式：**
   - 在 Dashboard 的 Focus Card 中始终显示"继续上次的学习"

**是否涉及结构性重构：** 否

---

### [P2] 空状态处理不足，缺少引导

**位置：** 多个页面的空状态

**现象：**
- Problems 页面空状态：只显示"No problems yet. Create your first problem to start learning."
- Model Cards 页面空状态：只显示"No model cards yet. Create your first card."
- Reviews 页面空状态：只显示"No due reviews."

**为什么是问题：**
- **缺少引导**：新用户看到空状态，不知道"为什么要创建 Problem？创建后会发生什么？"
- **缺少动机**：文案只是陈述事实，没有激发用户行动的欲望

**建议修改：**
1. **优化空状态文案和设计：**
   ```
   Problems 空状态：
   "开始你的第一个学习任务
   通过创建 Problem，你可以：
   - 与 AI 对话深入理解概念
   - 自动提取关键知识点
   - 构建你的认知模型库
   [创建第一个 Problem]"
   ```

2. **提供示例或模板：**
   - "不知道从哪里开始？试试这些示例：控制理论、机器学习基础、系统设计..."

3. **显示引导流程：**
   - 用图示或步骤说明"Problem → Learning → Model Card → Review"的完整流程

**是否涉及结构性重构：** 否

---

## 3. 全局结构建议

### 导航重构

**当前问题：** 导航是功能模块的罗列，不是用户任务流程的体现

**建议调整：**
```
主导航：
[工作台] - Dashboard，显示当前任务和进度
[学习] - Problems 列表 + Problem Workspace
[模型库] - Model Cards 列表 + 详情
[复习] - SRS Review 队列 + 复习界面

移除或整合：
- Chat → 合并到 Problem Workspace
- Knowledge Graph → 作为 Model Cards 的可视化视图
- Challenges、Resources、Notes → 评估是否为核心功能，考虑移除
- Cog Test → 如果不是核心功能，移到设置或工具区域
```

### 页面职责重新定义

**Dashboard（工作台）：**
- **职责：** 显示当前最重要的任务 + 进度概览
- **核心元素：** 大号 Focus Card（唯一主操作）+ 简化的进度指标 + 最近活动
- **移除：** Quick Actions 区域（功能重复）

**Problems（学习）：**
- **职责：** 学习任务管理 + 学习执行
- **拆分为两个视图：**
  1. Problems List（任务列表）：显示所有学习任务，突出"继续学习"操作
  2. Problem Workspace（学习工作区）：拆分为"学习模式"、"概念提取"、"归档查看"三个阶段

**Model Cards（模型库）：**
- **职责：** 认知模型管理
- **简化列表页：** 只显示核心信息，详细状态移到详情页
- **整合 Knowledge Graph：** 作为可视化视图选项

**Reviews（复习）：**
- **职责：** SRS 间隔重复复习
- **移除：** Model Cards Lifecycle 区域（重复）
- **拆分：** Review Archive 移到独立的"学习日志"页面

### 是否需要引入更明确的步骤流或任务流

**是的，强烈建议引入任务流：**

1. **新用户引导流程：**
   ```
   欢迎 → 创建第一个 Problem → 开始学习 → 提取第一个 Concept → 创建第一个 Model Card → 加入复习队列 → 完成第一次复习
   ```

2. **日常使用流程：**
   ```
   Dashboard Focus Card → 继续学习 / 开始复习 / 查看模型库
   ```

3. **学习流程阶段化：**
   ```
   Problem Workspace:
   [阶段 1: 学习] → [阶段 2: 提取概念] → [阶段 3: 归档]
   每个阶段只显示当前需要的内容
   ```

---

## 4. 优先级最高的前 5 个修改动作

### 1. 重构 Dashboard 为任务驱动型首页
- **文件：** `las_frontend/src/views/DashboardView.vue`
- **动作：** 放大 Focus Card，移除 Quick Actions，简化信息展示
- **预期效果：** 用户进入首页立即知道"当前应该做什么"

### 2. 拆分 Problem Workspace 为三个阶段视图
- **文件：** `las_frontend/src/views/ProblemDetailView.vue`
- **动作：** 将学习、概念提取、归档拆分为独立视图，用阶段切换按钮连接
- **预期效果：** 用户在学习时不被其他信息干扰，清楚知道当前处于哪个阶段

### 3. 简化 Model Cards 列表页信息密度
- **文件：** `las_frontend/src/views/ModelCardsView.vue`
- **动作：** 只保留 Title、主要状态、主操作按钮，其他信息移到详情页
- **预期效果：** 用户快速扫描卡片列表，不被过多状态信息淹没

### 4. 拆分 Reviews 页面为"SRS 复习"和"学习日志"
- **文件：** `las_frontend/src/views/ReviewsView.vue` + 新建 `LearningJournalView.vue`
- **动作：** 将 SRS Review 和 Review Archive 分离，明确各自职责
- **预期效果：** 用户清楚"复习"和"总结"是两个不同的功能

### 5. 移除或整合 Chat 页面
- **文件：** `las_frontend/src/views/ChatView.vue` + `las_frontend/src/router/index.ts`
- **动作：** 如果功能已被 Problem Workspace 替代，直接移除；否则重新定位用途
- **预期效果：** 消除用户困惑，统一对话功能入口

---

## 总结

Cogniforge 的核心问题不是功能缺失，而是**功能过多但主线不清**。系统像一个"功能齐全的工具箱"，但用户需要的是"一条清晰的学习路径"。

**核心改进方向：**
1. **从功能展示转向任务推进**：每个页面都应该回答"用户当前应该做什么"
2. **从信息堆砌转向内容聚焦**：每个页面只显示当前阶段最需要的信息
3. **从模块并列转向流程串联**：让用户感受到"Problem → Model Card → Review"的自然流动

通过这些改进，Cogniforge 可以从"一个功能丰富但复杂的系统"变成"一个引导用户深度学习的认知工具"。

---

**审核日期：** 2026-03-11
**审核范围：** Cogniforge 前端代码（Vue 3 + TypeScript）
**审核重点：** 产品交互质量、用户流程清晰度、任务导向设计
