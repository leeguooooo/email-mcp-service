# 单元测试说明

本目录包含 MCP Email Service 的单元测试，只测试不需要外部依赖的功能。

## 测试覆盖范围

### ✅ 已测试（无外部依赖）
- **AccountManager** - 账户管理功能
  - 添加/删除账户
  - 默认账户管理
  - 账户列表和更新
  - 环境变量回退

- **工具函数** - 通用功能
  - MIME 编码解码
  - 文件大小格式化
  - 搜索条件构建
  - 配置验证

- **MCP 工具定义** - API 结构
  - 工具列表完整性
  - 参数 schema 验证
  - 默认值检查
  - 必需参数验证

### ❌ 未测试（需要邮箱连接）
- IMAP/SMTP 连接
- 邮件发送和接收
- 文件夹操作
- 实际的邮件搜索

## 运行测试

### 方法 1：使用测试脚本
```bash
# 运行所有安全的单元测试
uv run python tests/run_tests.py
```

### 方法 2：使用 pytest
```bash
# 安装测试依赖
uv pip install pytest pytest-asyncio pytest-cov

# 运行所有测试
uv run pytest tests/

# 运行特定测试文件
uv run pytest tests/test_account_manager.py

# 运行并生成覆盖率报告
uv run pytest tests/ --cov=src --cov-report=html
```

### 方法 3：使用 unittest
```bash
# 运行单个测试文件
uv run python -m unittest tests.test_account_manager

# 运行所有测试
uv run python -m unittest discover tests/
```

## 测试文件说明

- `test_account_manager.py` - 测试账户管理功能
- `test_utils.py` - 测试工具函数和解码功能
- `test_mcp_tools.py` - 测试 MCP 工具定义和结构
- `run_tests.py` - 统一的测试运行器

## 添加新测试

新测试应该：
1. 不依赖外部服务（邮箱服务器等）
2. 使用 mock 对象模拟外部依赖
3. 快速执行（每个测试 < 1秒）
4. 有清晰的测试名称和文档

示例：
```python
def test_new_feature(self):
    """Test description of what is being tested"""
    # Arrange
    input_data = {...}
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    self.assertEqual(result, expected_value)
```