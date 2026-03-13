# Cogniforge 主线四页线框说明

更新时间：2026-03-12

用途：
- 把主线 IA 方案进一步落成页面级线框说明
- 为 `Dashboard / Problems / ProblemDetail / Reviews` 提供统一的页面骨架
- 作为下一步设计稿或前端重构的直接参考

这份文档不提供视觉风格，只定义：
- 页面块
- 主次关系
- 首屏信息顺序
- 页面间跳转
- 不该出现的内容

相关上位文档：
- [Cogniforge 产品定位与学习使用流程参考](/Users/asteroida/work/Cogniforge/docs/plans/2026-03-12-cogniforge-product-positioning-and-learning-flow-zh.md)
- [ProblemDetail 高层 UI 重构方向](/Users/asteroida/work/Cogniforge/docs/plans/2026-03-12-problemdetail-high-level-ui-redesign-zh.md)
- [ProblemDetail 主学习工作区重构原则](/Users/asteroida/work/Cogniforge/docs/plans/2026-03-12-problemdetail-rebuild-principles-zh.md)
- [主线信息架构重组方案](/Users/asteroida/work/Cogniforge/docs/plans/2026-03-12-mainline-ia-restructure-zh.md)

---

## 1. 总体原则

四个主页面必须合起来表达一条完整主线：

```text
Continue -> Problems -> ProblemDetail -> Reviews -> 回到 ProblemDetail
```

### 1.1 四页各自只回答一个问题

- `Dashboard / Continue`
  - 我现在最该继续什么？
- `Problems`
  - 我要学哪个问题？
- `ProblemDetail`
  - 我现在如何完成这一轮学习？
- `Reviews`
  - 我现在先复习什么？如果脆弱，怎么回去强化？

### 1.2 四页不应该互相争夺职责

错误示例：
- `Dashboard` 变成半个工作区
- `Problems` 变成轻量学习页
- `ProblemDetail` 变成治理后台
- `Reviews` 变成归档中心

### 1.3 每一页都必须有明确首屏主动作

不能让用户进入页面后先看摘要卡，再猜下一步。

---

## 2. Dashboard / Continue 线框

### 2.1 页面目标

用户进入后，3 秒内点下一个动作。

### 2.2 页面结构

```text
┌──────────────────────────────────────────────┐
│ Header: Continue Learning                    │
│ Subtitle: resume the most important task     │
├──────────────────────────────────────────────┤
│ Focus Card                                   │
│ - 现在最优先动作                             │
│ - CTA: Continue Problem / Start Review       │
├──────────────────────────────────────────────┤
│ Metrics Row                                  │
│ - Active Problems                            │
│ - Due Reviews                                │
│ - Model Cards                                │
├──────────────────────────────────────────────┤
│ Recent Problems                              │
├──────────────────────────────────────────────┤
│ Due Review Preview                           │
└──────────────────────────────────────────────┘
```

### 2.3 首屏顺序

1. 页面标题
2. Focus Card
3. Metrics Row
4. Recent Problems 或 Due Review Preview

### 2.4 Focus Card 规则

#### 有 due review
- CTA 直接去 `SRS Review` 或 `Reviews`

#### 无 due review，但有活跃问题
- CTA 直接去最近活跃的 `ProblemDetail`

#### 没有问题
- CTA 去 `Problems`

### 2.5 不该出现的内容

- 大量 quick actions
- 知识资产治理动作
- 复盘归档入口
- 导出入口
- 解释型说明文字过长

### 2.6 页面跳转

- Focus Card -> `ProblemDetail` 或 `Reviews`
- Recent Problems -> `ProblemDetail`
- Due Review Preview -> `Reviews` / `SRS Review`
- Secondary link -> `Problems`

---

## 3. Problems 线框

### 3.1 页面目标

用户快速完成两种任务之一：

1. 打开一个已有问题继续学习
2. 新建一个问题并选起始协议

### 3.2 页面结构

```text
┌──────────────────────────────────────────────┐
│ Header: Problems                             │
│ CTA: New Problem                             │
├──────────────────────────────────────────────┤
│ Search / Filters / Sort                      │
├──────────────────────────────────────────────┤
│ Problem List                                 │
│ - title                                      │
│ - one-line description                       │
│ - status / mode / concepts                   │
│ - CTA: Open Workspace                        │
└──────────────────────────────────────────────┘
```

### 3.3 新建问题流程

#### Step 1: Create Problem
- title
- short description
- optional concept seeds

#### Step 2: Choose Start Protocol
- `Start with Socratic`
- `Start with Exploration`

#### Step 3: Enter ProblemDetail

### 3.4 协议选择的页面行为

不要求一定是独立页面。
可以是：
- modal
- drawer
- full-screen interstitial

但必须满足：
- 明确是一个完整步骤
- 两种协议都显式落库
- 用户进入工作区前已经知道自己将以哪种方式开始

### 3.5 Problem Card 应该有的内容

保留：
- 标题
- 一行描述
- 状态
- 当前协议或最近协议
- 概念数量或更新时间

不要加入：
- 太多操作按钮
- 路径治理
- 学习结果摘要
- 复习状态明细

### 3.6 不该出现的内容

- 大量模式切换动作
- 模型卡提升动作
- 概念治理入口
- 复习执行入口

### 3.7 页面跳转

- Card -> `ProblemDetail`
- Create -> `Start Protocol` -> `ProblemDetail`

---

## 4. ProblemDetail 线框

### 4.1 页面目标

用户围绕一个问题，完成“当前这一轮学习”。

### 4.2 页面结构

```text
┌──────────────────────────────────────────────┐
│ Learning Header                              │
│ - Problem                                    │
│ - Path                                       │
│ - Step                                       │
│ - Mode                                       │
├──────────────────────────────────────────────┤
│ Current Learning Contract                    │
│ - 当前任务                                   │
│ - 为什么现在做这个                           │
│ - 本轮完成标准                               │
├──────────────────────────────────────────────┤
│ Primary Turn Area                            │
│ - Socratic question / Exploration input      │
│ - answer / ask form                          │
│ - submit                                     │
├──────────────────────────────────────────────┤
│ Turn Result Area                             │
│ - 是否推进                                   │
│ - 为什么                                     │
│ - 缺口 / 误区                                │
│ - 推荐下一步                                 │
├──────────────────────────────────────────────┤
│ Post-turn Decision Area                      │
│ - Derived Concepts summary                   │
│ - Derived Paths summary                      │
│ - Promote / Schedule actions                 │
├──────────────────────────────────────────────┤
│ Secondary Areas                              │
│ - History                                    │
│ - Notes                                      │
│ - Resources                                  │
│ - Export                                     │
└──────────────────────────────────────────────┘
```

### 4.3 首屏顺序

首屏必须尽可能只覆盖：

1. Learning Header
2. Current Learning Contract
3. Primary Turn Area

如果空间允许，才让：

4. Turn Result Area 上半部分

### 4.4 Learning Header 内容

只保留：
- Problem title
- current path
- current step
- current mode
- compact progress

不放：
- 导出
- 打开复习中心
- 打开知识卡
- Notes / Resources

### 4.5 Current Learning Contract 内容

这是整个页面的关键区块。

必须明确写出：
- 当前任务是什么
- 当前在补哪个点
- 当前回合怎么才算过线

#### Socratic 示例
- 当前目标：说明 precision/recall 的阈值权衡
- 通过标准：能给出一个具体场景解释阈值变化

#### Exploration 示例
- 当前目标：理解 boosting 的基本机制
- 推荐提问：为什么 boosting 不是简单投票

### 4.6 Primary Turn Area

#### Socratic
- 当前问题
- question kind
- 回答框
- 一个主提交按钮
- 可选轻提示

#### Exploration
- 用户提问框
- answer style 或 answer type 轻选择
- 一个主提交按钮

不应出现：
- 大段历史
- 概念治理按钮
- 路径治理按钮

### 4.7 Turn Result Area

这是最容易被做错的部分。

#### 默认行为
用户提交后自动出现，不需要再点“处理本轮产物”。

#### 首要内容

##### Socratic
- 是否推进
- 为什么推进或不推进
- 缺口 / 误区
- 下一步推荐

##### Exploration
- 本轮解释的核心点
- 这轮发现了什么值得继续问
- 是否建议开新路径

#### 不该被放在结果区首位的内容
- merge
- rollback
- schedule review
- open model card

这些属于下一阶段动作。

### 4.8 Post-turn Decision Area

这是“本轮产物处理区”，必须与 Turn Result Area 分开。

#### Concepts
- 本轮发现了几个概念
- 哪个最值得保留
- 接受 / 稍后处理 / 忽略

#### Paths
- 建议你先补哪个、比较哪个、深挖哪个
- 意图词动作：
  - 先补这个
  - 单独深入
  - 稍后再看
  - 现在忽略

不要在首屏暴露实现词：
- insert_before_current_main
- bookmark_for_later

### 4.9 Secondary Areas

这些全部降级：
- 历史
- Notes
- Resources
- Export
- Open Review Hub
- Open Model Cards

推荐放法：
- details / accordion
- more menu
- bottom utility area

### 4.10 分支与前置的页面表达

当用户离开主线时，页面必须显式显示：

```text
You are temporarily on:
Prerequisite Path / Comparison Path / Branch Deep Dive

Reason:
为什么离开主线

Return condition:
什么时候回主线
```

不能只是改一个 badge。

### 4.11 Reinforcement 的位置

reinforcement 不是首屏主动作，但也不能藏到找不到。

正确做法：
- 当存在 reinforcement target 时，放在 `Learning Contract` 下方或 `Turn Result Area` 上方
- 作为一个清晰的“先做这个”的 contextual strip

而不是一个展开很多卡片的独立控制区。

---

## 5. Reviews 线框

### 5.1 页面目标

用户进入后，立即知道先复习哪个，并能在需要时回到工作区强化。

### 5.2 页面结构

```text
┌──────────────────────────────────────────────┐
│ Header: Reviews                              │
│ Subtitle: focus on recall and reinforcement  │
├──────────────────────────────────────────────┤
│ Focus Card                                   │
│ - 现在最优先复习任务                         │
│ - CTA: Start Review / Return to Workspace    │
├──────────────────────────────────────────────┤
│ Due Review Queue                             │
│ - title                                      │
│ - due time                                   │
│ - reason / origin                            │
│ - CTA: Start SRS / Open Workspace            │
├──────────────────────────────────────────────┤
│ Fragile Knowledge / Needs Reinforcement      │
│ - current state                              │
│ - suggested action                           │
│ - CTA: Return to Workspace                   │
└──────────────────────────────────────────────┘
```

### 5.3 页面首屏

只需要回答：

1. 现在先复习哪个
2. 哪些知识已经脆弱
3. 如何回去强化

### 5.4 允许保留但必须降级的内容

- archive
- generated review reports
- new review generator

建议：
- 单独二级页面
- 或折叠到底部
- 或从 admin / reports 进入

### 5.5 不该再放在首屏的内容

- 长篇 review archive
- 复杂 report creation 表单
- 多种 review type 创建器

### 5.6 页面跳转

- Due item -> `SRS Review`
- Fragile item -> `ProblemDetail`
- Model card item -> `Model Card Detail`

但主 CTA 仍应围绕：
- `Start Review`
- `Return to Workspace`

---

## 6. 四页之间的跳转规则

### 6.1 Dashboard

只能把用户送到：
- `ProblemDetail`
- `Reviews`
- `Problems`

### 6.2 Problems

只能把用户送到：
- `ProblemDetail`

创建后允许经过一次：
- `Start Protocol`

### 6.3 ProblemDetail

主跳转只能有两种：
- 继续当前问题内部路径
- 去 `Reviews`

次级跳转：
- `Model Cards`

工具跳转不应首屏暴露。

### 6.4 Reviews

主跳转只能有两种：
- `SRS Review`
- `ProblemDetail`

这页不应再把用户带去太多平行 surface。

---

## 7. 页面之间的状态传递

### 7.1 Problems -> ProblemDetail

必须带：
- problem id
- chosen learning mode

### 7.2 ProblemDetail -> Reviews

可以带：
- current model card context
- scheduled concept context

但不要破坏 Reviews 的单一职责。

### 7.3 Reviews -> ProblemDetail

必须带：
- reinforcement target
- recommended action
- source turn context

不能只把用户丢回一个空的工作区。

---

## 8. 不该继续坚持的现状

以下现状不应成为后续设计约束：

- `ProblemDetail` 必须长期两栏
- `Turn result` 必须在右侧
- `概念治理` 必须和当前回合动作同层
- `Export / Review Hub / Model Cards` 必须留在主工作区顶部
- `Model Cards` 必须长期和 Problems / Reviews 同等一级
- `Chat / Practice / Notes / Resources / Challenges` 仍然是产品核心表面

---

## 9. 实施建议顺序

### 阶段 1：先重建四页骨架

不要先写组件，先定：
- 页面块
- 信息层级
- 跳转关系

### 阶段 2：先做 ProblemDetail 和 Reviews

因为这两个页面最直接影响学习是否顺畅。

### 阶段 3：再收口 Problems 与 Dashboard

它们更像分发问题，而不是核心学习执行问题。

### 阶段 4：最后处理 Model Cards 和 secondary surfaces

---

## 10. 一句话结论

这四个页面不应该再被理解成“功能入口集合”，而应该被重建为一条清晰主线：

> Continue 帮用户找下一步，Problems 帮用户选问题，ProblemDetail 让用户完成当前学习回合，Reviews 让用户完成复习并回流强化。

