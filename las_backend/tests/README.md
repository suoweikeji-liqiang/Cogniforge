# 测试说明

## 测试分类

### 1. 单元测试（快速，无需外部依赖）
- `test_data_integrity.py` - 数据完整性
- `test_services_unit.py` - 服务层逻辑
- `test_edge_cases.py` - 边界条件

### 2. 集成测试（使用 mock LLM）
- `test_api_smoke.py` - API 冒烟测试
- `test_problem_learning_flow.py` - 学习流程
- `test_api_contract.py` - API 契约
- `test_missing_apis.py` - 缺失的 API 端点

### 3. 安全和弹性测试
- `test_security_threats.py` - 安全威胁
- `test_chaos_resilience.py` - 混沌弹性

### 4. 真实 LLM 集成测试（需要 API key）
- `test_llm_integration.py` - 真实 LLM 调用

## 运行测试

### 快速测试（不需要 API key）
```bash
cd las_backend
pytest -v
```

### 包含真实 LLM 测试
```bash
# 1. 创建 test.env 文件
cp test.env.example test.env

# 2. 编辑 test.env，填入通义 API key
# QWEN_API_KEY=sk-your-key-here

# 3. 运行所有测试
pytest -v

# 4. 只运行真实 LLM 测试
pytest -v -m "not skipif" test_llm_integration.py
```

### 运行特定测试
```bash
# 只运行服务层测试
pytest tests/test_services_unit.py -v

# 只运行安全测试
pytest tests/test_security_threats.py -v

# 跳过慢速测试
pytest -v -m "not slow"
```

## 测试覆盖率

```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html
```
