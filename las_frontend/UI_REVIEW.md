# UI 审核报告

## 一、i18n 翻译键错误使用（严重）

多处使用了错误的翻译键，导致界面文案与实际功能不符。

### 1. ReviewsView.vue — 大量翻译键复用 `reviews.title`

- 第6行：创建按钮文案用了 `t('reviews.title')`（显示"复习"），应该是"新建复习"
- 第18行：insights 标签用了 `t('reviews.title')`
- 第19行：next_steps 标签也用了 `t('reviews.title')`
- 第31行：弹窗标题用了 `t('reviews.title')`
- 第34行：review_type 的 label 用了 `t('reviews.title')`
- 第50行：insights textarea 的 label 用了 `t('reviews.title')`
- 第54行：next_steps textarea 的 label 用了 `t('reviews.title')`

弹窗里至少有4个字段的标签都显示为"复习"，用户完全无法区分各字段的含义。

### 2. ModelCardsView.vue — "迁移"按钮文案错误

- 第29行：`suggestMigration` 按钮使用了 `t('chat.newConversation')`（显示"新建对话"），应该是"迁移建议"
- 第41行：迁移结果标题也用了 `t('chat.newConversation')`

### 3. ChatView.vue — 第二个 checkbox 文案错误

- 第44行：`suggestMigration` 选项使用了 `t('chat.newConversation')`（显示"新建对话"），应该是"迁移建议"

### 4. i18n 缺失键

`reviews` 模块缺少：
- `reviews.newReview`（新建复习）
- `reviews.reviewType`（复习类型）
- `reviews.summary`（摘要）
- `reviews.insights`（洞察）
- `reviews.nextSteps`（下一步）

`modelCards` / `chat` 模块缺少：
- `modelCards.suggestMigration`（迁移建议）

---

## 二、样式一致性问题

### 1. ForgotPasswordView.vue 和 ResetPasswordView.vue 风格脱节

这两个页面的样式与其他页面完全不同：
- 使用硬编码颜色 `#ddd`（浅灰边框）和 `#42b983`（绿色按钮），在深色主题下非常突兀
- input 的 `border: 1px solid #ddd` 在深色背景上会显示为亮白色边框
- 按钮颜色 `#42b983` 与全局主色 `#4ade80` 不一致
- 没有使用全局 CSS 变量（`--bg-card`, `--border`, `--primary` 等）
- 没有使用 `.auth-container` / `.auth-card` 的卡片布局，与 Login/Register 页面视觉差异大
- 没有使用 `.btn` / `.btn-primary` 全局按钮类

### 2. 缺少 `lang="ts"`

`ForgotPasswordView.vue` 和 `ResetPasswordView.vue` 的 `<script setup>` 没有 `lang="ts"`，与项目其他文件不一致。

---

## 三、交互与操作问题

### 1. viewCard() 函数是空实现 — ModelCardsView.vue:143

```js
const viewCard = (card: any) => {
  console.log('View card:', card.id)
}
```

用户点击"查看"按钮后什么都不会发生，只在控制台打印日志。

### 2. 使用 alert() / confirm() / prompt() 原生弹窗

多处使用了浏览器原生弹窗，体验粗糙且与深色主题不搭：
- `LLMConfig.vue:280,298,300,304` — `alert()` 用于错误和成功提示
- `LLMConfig.vue:285` — `confirm()` 用于删除确认
- `UserManagement.vue:83` — `confirm()` 用于删除确认
- `EmailConfig.vue:68,72,76,78` — `alert()` 和 `prompt()` 用于测试邮件

建议统一使用自定义 Modal 或 Toast 组件。

### 3. 错误处理不一致

- 部分页面有错误提示（LoginView 显示 error 文案），部分只有 `console.error`
- `UserManagement.vue` 的 `loadUsers()`、`updateUser()`、`resetPassword()` 完全没有 try/catch，API 失败会导致未处理的 Promise rejection
- `EmailConfig.vue:67` 的 `saveConfig()` 也没有 try/catch

### 4. 聊天页面错误消息未国际化 — ChatView.vue:164

```js
content: 'Sorry, I encountered an error. Please try again.'
```

硬编码英文，切换到中文界面后仍显示英文。

### 5. ForgotPasswordView.vue 和 ResetPasswordView.vue 同理

```js
message.value = 'If email exists, reset link will be sent'
message.value = 'Error resetting password'
```

硬编码英文提示，未使用 i18n。

---

## 四、响应式与布局问题

### 1. 导航栏无移动端适配 — App.vue

`.nav-links` 使用 `display: flex` + `gap: 1.5rem`，在窄屏上链接会挤在一起或溢出，没有汉堡菜单或折叠逻辑。

### 2. 聊天页面固定侧边栏宽度 — ChatView.vue:188

```css
grid-template-columns: 250px 1fr;
```

在移动端 250px 的侧边栏会占据大部分屏幕，没有响应式断点处理。

### 3. LLM 配置页面同理 — LLMConfig.vue:386

```css
grid-template-columns: 320px 1fr;
```

### 4. Admin 侧边栏固定 250px — AdminLayout.vue:29

同样没有移动端适配。

### 5. 语言切换按钮 position: fixed — App.vue:48

固定在右上角，可能与导航栏内容重叠（尤其是 admin 链接 + logout 按钮区域）。

---

## 五、可访问性（Accessibility）问题

### 1. 表单 input 缺少关联 label

- `ForgotPasswordView.vue` 和 `ResetPasswordView.vue` 的 input 只有 placeholder，没有 `<label>` 或 `aria-label`
- `UserManagement.vue:38` 的密码重置 input 同理

### 2. 按钮缺少 type 属性

- `UserManagement.vue:28-29` 的操作按钮没有 `type="button"`，在 form 内可能触发意外提交

### 3. Modal 缺少键盘支持

所有 Modal（Problems、ModelCards、Practice、Reviews）：
- 没有 ESC 键关闭支持
- 没有 focus trap（焦点可以 Tab 到遮罩层后面的元素）
- 没有 `role="dialog"` 和 `aria-modal="true"`

### 4. 颜色对比度

`--text-muted: #a0a0a0` 在 `--bg-card: #1a1a2e` 上对比度约 5.5:1，小字体场景下可能不满足 AAA 标准。

---

## 六、其他问题

### 1. LLM 配置页面明文显示 API Key — LLMConfig.vue:66

```html
<span class="value">{{ selectedProvider.api_key || '-' }}</span>
```

API Key 直接以明文展示在详情面板中，存在安全隐患。应该遮蔽显示（如 `sk-****xxxx`）。

### 2. LLMConfig.vue 重复定义全局样式类

第673-713行重新定义了 `.btn`、`.btn-primary`、`.btn-secondary` 等类，与 `main.css` 中的全局定义重复。虽然 scoped 不会冲突，但增加了维护成本。

### 3. PracticeView.vue:24 截断逻辑粗糙

```html
<h4>{{ sub.solution.substring(0, 100) }}...</h4>
```

无论内容长短都会追加 `...`，短内容也会显示省略号。且如果 `sub.solution` 为 null/undefined 会报错。

### 4. AdminLayout.vue 侧边栏 router-link-active 匹配问题

`/admin` 路由会匹配所有 `/admin/*` 子路由的 `router-link-active`，导致"统计"链接在所有管理子页面都高亮。应使用 `router-link-exact-active` 或给链接加 `exact` 属性。

---

## 总结

| 类别 | 严重程度 | 数量 |
|------|---------|------|
| i18n 翻译键错误/缺失 | 高 | 7+ 处 |
| 样式不一致（忘记密码/重置密码页面） | 中 | 2 个页面 |
| 功能空实现（viewCard） | 中 | 1 处 |
| 原生弹窗替代自定义组件 | 中 | 6+ 处 |
| 错误处理缺失/不一致 | 中 | 4+ 处 |
| 响应式缺失 | 中 | 4 处 |
| 可访问性问题 | 低-中 | 多处 |
| API Key 明文显示 | 高 | 1 处 |

最需要优先修复的是 i18n 翻译键错误（直接影响用户理解界面）和 ForgotPassword/ResetPassword 的样式脱节（视觉上明显不协调）。
