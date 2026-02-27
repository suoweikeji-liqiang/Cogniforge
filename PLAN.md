# Cogniforge 功能增强开发计划

## 阶段一：P0 核心功能（本次实现）

### 1.1 认知演化时间线
- **后端**: 完善 `EvolutionLog` 持久化，新增演化对比 API
- **前端**: Model Card 详情页增加演化时间线组件
- **文件变更**:
  - `las_backend/app/api/routes/model_cards.py` - 新增演化日志 API
  - `las_backend/app/services/model_os_service.py` - 完善 log_evolution
  - `las_backend/app/models/schemas/model_card.py` - 演化日志 schema
  - `las_frontend/src/views/ModelCardDetailView.vue` - 新建详情页
  - `las_frontend/src/router/index.ts` - 新增路由

### 1.2 间隔重复系统（SRS）
- **后端**: 新增 ReviewSchedule 模型，基于 SM-2 算法的复习调度
- **前端**: Dashboard 显示待复习卡片，复习交互界面
- **文件变更**:
  - `las_backend/app/models/entities/user.py` - 新增 ReviewSchedule 模型
  - `las_backend/app/models/schemas/model_card.py` - 复习调度 schema
  - `las_backend/app/api/routes/reviews.py` - 新建间隔复习 API
  - `las_backend/app/services/srs_service.py` - SM-2 算法服务
  - `las_frontend/src/views/SRSReviewView.vue` - 复习界面
  - `las_frontend/src/views/DashboardView.vue` - 增加待复习提醒

### 1.3 学习数据仪表盘增强
- **后端**: 新增统计 API（热力图数据、认知覆盖度）
- **前端**: Dashboard 重构，增加图表组件
- **文件变更**:
  - `las_backend/app/api/routes/statistics.py` - 新建统计 API
  - `las_frontend/src/views/DashboardView.vue` - 增强仪表盘

## 阶段二：P1 重要功能

### 2.1 知识图谱可视化
### 2.2 多模态输入（PDF 解析）
### 2.3 主动式认知挑战

## 阶段三：P2 增值功能

### 3.1 结构化导出（Markdown/Anki）
### 3.2 学习目标与里程碑
### 3.3 个性化学习风格适配

## 阶段四：P3 社交功能

### 4.1 Model Card 分享
### 4.2 学习小组
