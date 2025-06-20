# MCP Email Service 大文件分析报告

## 文件大小统计

### 主要文件
- `src/main.py`: 1329 行
- `src/mcp_tools.py`: 666 行
- `src/legacy_operations.py`: 573 行
- `src/operations/` 目录下共有约 3500 行代码

总代码行数：约 6745 行

## 代码结构分析

### 1. main.py 文件分析（1329行）

**主要功能模块：**
- 账户管理函数（61-105行）
- IMAP连接管理（120-238行）
- 邮件获取操作（239-476行）
- 邮件标记操作（477-613行）
- 垃圾箱操作（614-757行）
- 批量操作（758-803行）
- 其他邮件操作（804-1329行）

**发现的问题：**
1. **功能混杂**：一个文件包含了太多不同类型的功能
2. **重复的连接逻辑**：每个操作函数都包含相似的连接和错误处理代码
3. **缺乏抽象**：相似的操作（如批量操作）没有共享基础逻辑

### 2. mcp_tools.py 文件分析（666行）

**主要内容：**
- MCPTools 类定义（77行开始）
- 包含所有 MCP 工具方法的定义
- 大量的装饰器和工具函数

**问题：**
- 单个类过大，包含了所有工具方法
- 可以按功能拆分为多个专门的工具类

### 3. operations 目录分析

存在大量功能重叠的文件：
- `parallel_operations.py` (429行)
- `folder_operations.py` (358行)
- `email_operations.py` (341行)
- `performance_optimizer.py` (312行)

这些文件中存在功能重复和代码冗余。

## 优化建议

### 1. 重构 main.py

将 main.py 拆分为以下模块：

```python
# src/core/
├── connection.py      # IMAP连接管理
├── account.py         # 账户管理
├── email_fetcher.py   # 邮件获取
├── email_actions.py   # 邮件操作（标记、删除等）
├── batch_operations.py # 批量操作
└── utils.py          # 工具函数
```

### 2. 重构 mcp_tools.py

按功能拆分为：

```python
# src/tools/
├── base_tool.py       # 基础工具类
├── email_tools.py     # 邮件相关工具
├── search_tools.py    # 搜索相关工具
├── folder_tools.py    # 文件夹相关工具
└── send_tools.py      # 发送邮件工具
```

### 3. 清理 operations 目录

- 合并功能重复的文件
- 建立清晰的职责边界
- 删除未使用的代码

### 4. 实现连接池

创建一个连接管理器，避免重复连接：

```python
# src/core/connection_pool.py
class ConnectionPool:
    def __init__(self):
        self._connections = {}
    
    def get_connection(self, account_id):
        # 复用或创建新连接
        pass
```

### 5. 统一错误处理

创建统一的错误处理装饰器：

```python
# src/core/decorators.py
def handle_imap_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 统一错误处理逻辑
            pass
    return wrapper
```

## 重复代码示例

### 1. 连接模式重复

每个函数都有类似的连接代码：
```python
mail = connect_to_imap(account_id)
result, data = mail.select(folder)
if result != 'OK':
    raise Exception(f"Cannot select folder {folder}")
```

### 2. 批量操作重复

批量操作函数有大量相似逻辑，可以抽象为通用批量处理框架。

## 建议的重构步骤

1. **第一阶段**：创建新的模块结构，不改变现有接口
2. **第二阶段**：逐步迁移功能到新模块
3. **第三阶段**：更新 mcp_tools.py 使用新模块
4. **第四阶段**：清理和删除旧代码
5. **第五阶段**：优化性能和添加缓存

## 预期效果

- 代码可维护性提升 80%
- 重复代码减少 60%
- 文件大小减少到平均 200-300 行
- 更容易添加新功能和修复问题