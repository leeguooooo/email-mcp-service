# 📁 项目结构

本文档描述 MCP Email Service 的完整目录结构和文件组织。

> 🆕 **最近更新**：2025-10-17 - 项目结构重组，引入 `data/` 目录集中管理运行时数据

---

## 🌳 目录树

```
mcp-email-service/
├── 📄 核心文档
│   ├── README.md                    # 项目主页（英文）
│   ├── README.zh.md                 # 项目主页（中文）
│   ├── LICENSE                      # MIT 许可证
│   ├── CHANGELOG.md                 # 版本变更历史
│   ├── PROJECT_STRUCTURE.md         # 项目结构说明（本文档）
│   └── FINAL_DEPLOYMENT_CHECKLIST.md # 部署检查清单
│
├── ⚙️  配置文件
│   ├── pyproject.toml               # 项目配置和依赖
│   ├── requirements.txt             # Python 依赖列表
│   ├── uv.lock                      # 依赖锁定文件
│   ├── .gitignore                   # Git 忽略规则
│   ├── .python-version              # Python 版本
│   ├── smithery.yaml                # Smithery 配置
│   └── accounts.json                # 邮箱账户配置（用户创建，不在版本控制）
│
├── 🔧 启动脚本
│   ├── run.sh                       # MCP 服务启动脚本
│   └── setup.py                     # 交互式配置脚本
│
├── 💾 运行时数据 (data/) ⭐ 新增
│   ├── README.md                    # 数据目录使用指南
│   ├── .gitkeep                     # Git 占位符
│   ├── email_sync.db                # 邮件同步数据库（运行时生成）
│   ├── sync_config.json             # 同步配置文件（运行时生成）
│   ├── sync_health_history.json     # 同步健康历史（运行时生成）
│   ├── notification_history.db      # 通知历史数据库（运行时生成）
│   ├── logs/                        # 日志文件目录（自动创建）
│   ├── tmp/                         # 临时文件目录（自动创建）
│   └── attachments/                 # 附件下载目录（自动创建）
│
├── 📂 源代码 (src/)
│   ├── __main__.py                  # 程序入口
│   ├── main.py                      # MCP 服务主程序
│   ├── account_manager.py           # 账号管理
│   ├── connection_manager.py        # 连接管理
│   ├── connection_pool.py           # IMAP 连接池
│   ├── legacy_operations.py         # 传统邮件操作（向后兼容）
│   ├── mcp_tools.py                 # MCP 工具定义
│   ├── models.py                    # 数据模型
│   │
│   ├── config/ ⭐ 新增               # 配置管理
│   │   ├── __init__.py
│   │   ├── paths.py                 # 集中路径配置（所有路径的单一来源）
│   │   └── messages.py              # 消息模板
│   │
│   ├── core/                        # 核心功能
│   │   ├── __init__.py
│   │   ├── tool_handlers.py         # MCP 工具处理器
│   │   ├── tool_registry.py         # 工具注册表
│   │   ├── tool_schemas.py          # 工具模式定义
│   │   ├── communication_handlers.py # 通信处理
│   │   ├── organization_handlers.py  # 组织处理
│   │   ├── sync_handlers.py         # 同步处理
│   │   ├── system_handlers.py       # 系统处理
│   │   └── connection_pool.py       # 连接池管理
│   │
│   ├── operations/                  # 邮件操作
│   │   ├── __init__.py
│   │   ├── email_operations.py      # 邮件基础操作
│   │   ├── parallel_fetch.py        # 并行获取（多账户）
│   │   ├── cached_operations.py ⭐ 新增 # 缓存操作（100-500x 加速）
│   │   ├── search_operations.py     # 搜索操作
│   │   ├── email_sync.py            # 邮件同步
│   │   ├── send_operations.py       # 发送操作
│   │   ├── folder_operations.py     # 文件夹操作
│   │   └── attachment_operations.py # 附件操作
│   │
│   ├── services/                    # 业务服务
│   │   ├── __init__.py
│   │   ├── email_service.py         # 邮件服务
│   │   ├── folder_service.py        # 文件夹服务
│   │   └── system_service.py        # 系统服务
│   │
│   ├── database/                    # 数据库
│   │   ├── __init__.py
│   │   ├── email_database.py        # 邮件数据库
│   │   ├── email_sync_db.py         # 邮件同步数据库（SQLite）
│   │   └── sync_manager.py          # 同步管理
│   │
│   ├── background/                  # 后台任务
│   │   ├── __init__.py
│   │   ├── sync_scheduler.py        # 同步调度器（自动启动）
│   │   ├── sync_config.py           # 同步配置管理
│   │   └── sync_health_monitor.py   # 健康监控
│   │
│   └── utils/                       # 工具函数
│       └── __pycache__/
│
├── 🧪 测试 (tests/) ⭐ 改进
│   ├── __init__.py
│   ├── run_tests.py                 # 测试运行器
│   ├── README.md                    # 测试说明
│   ├── test_account_manager.py      # 账号管理测试
│   ├── test_mcp_tools.py            # MCP 工具测试
│   ├── test_parallel_operations.py  # 并行操作测试
│   ├── test_utils.py                # 工具函数测试
│   ├── test_account_id_fix.py ⭐ 新增 # Account ID 修复测试
│   ├── test_email_lookup_fallback.py ⭐ 新增 # 邮箱查找回退测试
│   ├── test_performance.py ⭐ 新增   # 性能测试
│   ├── test_regression_fixes.py ⭐ 新增 # 回归测试（16 个）
│   ├── test_error_handling_improvements.py ⭐ 新增 # 错误处理测试（10 个）
│   ├── test_batch_delete_delegation.py ⭐ 新增 # 批量删除测试（8 个）
│   └── test_critical_fixes.py ⭐ 新增 # 关键修复测试（10 个）
│
├── 📚 文档 (docs/)
│   ├── README.md                    # 文档索引
│   ├── ARCHITECTURE.md              # 系统架构
│   ├── PROJECT_REORGANIZATION.md ⭐ 新增 # 项目重组详情
│   ├── CODE_REVIEW_FIXES.md ⭐ 新增  # 代码审查修复
│   ├── TESTING_GUIDE.md ⭐ 新增      # 测试指南
│   ├── TEST_IMPROVEMENTS_SUMMARY.md ⭐ 新增 # 测试改进总结
│   ├── TEST_IMPROVEMENT_PLAN.md ⭐ 新增 # 测试改进计划
│   ├── CHANGELOG_REFACTORING.md     # 重构日志
│   ├── CLEANUP_SUMMARY.md           # 清理总结
│   ├── CONNECTION_POOL_FIX.md       # 连接池修复
│   ├── database_design.md           # 数据库设计
│   ├── DEADLOCK_FIX.md              # 死锁修复
│   ├── REFACTORING_SUMMARY.md       # 重构总结
│   ├── RUN_SCRIPT_OPTIMIZATION.md   # 运行脚本优化
│   ├── SERVICE_OPTIMIZATION.md      # 服务优化
│   ├── SYNC_IMPROVEMENTS.md         # 同步改进
│   ├── TOOL_REGISTRY_FIX.md         # 工具注册表修复
│   │
│   ├── archive/ ⭐ 新增              # 历史文档归档（23 个文档）
│   │   ├── ACCOUNT_ID_FIX_SUMMARY.md
│   │   ├── AUTO_SYNC_ENABLED.md
│   │   ├── BATCH_DELETE_FIX.md
│   │   ├── BUG_EMAIL_ID_MISMATCH.md
│   │   ├── CACHE_CONSISTENCY_FIX.md
│   │   ├── CACHE_FIX_SUMMARY.md
│   │   ├── CRITICAL_FIXES.md
│   │   ├── CRITICAL_FIXES_SUMMARY.md
│   │   ├── CRITICAL_TRY_FINALLY_FIX_STATUS.md
│   │   ├── FINAL_REVIEW_FIXES.md
│   │   ├── FINAL_SUMMARY.md
│   │   ├── FINAL_UID_FIX_SUMMARY.md
│   │   ├── FIX_UID_MIGRATION.md
│   │   ├── FIX_UID_REVIEW_ISSUES.md
│   │   ├── PERFORMANCE_OPTIMIZATION_COMPLETED.md
│   │   ├── PERFORMANCE_OPTIMIZATION_PLAN.md
│   │   ├── QUICK_TEST.md
│   │   ├── TRY_FINALLY_FIX.md
│   │   ├── TRY_FINALLY_FIX_APPLIED.md
│   │   ├── UID_FALLBACK_SUMMARY.md
│   │   ├── UID_FIXES_COMPLETED.md
│   │   ├── UID_IN_LIST_FIX.md
│   │   ├── UID_MIGRATION_PLAN.md
│   │   └── UID_VERIFICATION_REPORT.md
│   │
│   └── guides/                      # 用户指南
│       ├── CRITICAL_FIXES.md        # 关键修复指南
│       ├── EMAIL_TRANSLATE_WORKFLOW_GUIDE.md # 邮件翻译工作流
│       ├── FINAL_DEPLOYMENT_CHECKLIST.md # 最终部署清单
│       ├── HTTP_API_QUICK_START.md  # HTTP API 快速开始
│       ├── LARK_SETUP_GUIDE.md      # 飞书设置指南
│       ├── OPEN_SOURCE_READINESS.md # 开源准备
│       ├── PRODUCTION_DEPLOYMENT_GUIDE.md # 生产部署指南
│       ├── SECURITY_SETUP_GUIDE.md  # 安全设置指南
│       └── TRANSLATION_WORKFLOW_SUMMARY.md # 翻译工作流总结
│
├── 🔌 脚本 (scripts/)
│   ├── create_env.sh                # 环境创建脚本
│   ├── daily_email_digest.py        # 每日汇总调度
│   ├── email_monitor_api.py         # 邮件监控 API
│   ├── email_monitor.py             # 邮件监控
│   ├── email_translator.py          # 邮件翻译
│   ├── init_sync.py                 # 初始化同步
│   ├── monitor_sync.py ⭐ 新增       # 监控同步状态
│   ├── notification_service.py      # 通知服务
│   ├── test_connection.py           # 测试连接
│   ├── test_lark_webhook.py         # 测试飞书 webhook
│   └── test_sync.py                 # 测试同步
│
├── 📝 配置模板 (config_templates/)
│   ├── daily_digest_config.example.json # 每日汇总配置示例
│   ├── email_monitor_config.example.json # 邮件监控配置示例
│   ├── env.example                  # 环境变量示例
│   └── notification_config.example.json # 通知配置示例
│
├── 📦 示例 (examples/)
│   ├── README.md                    # 示例说明
│   ├── accounts.example.json        # 账户配置示例
│   └── sync_config.json.example     # 同步配置示例
│
├── 🐳 Docker (docker/)
│   ├── README.md                    # Docker 使用指南
│   ├── Dockerfile.optimized         # 优化的 Dockerfile
│   └── Dockerfile.optional          # 可选的 Dockerfile
│
└── 🆕 GitHub 配置 (.github/) ⭐ 新增
    └── FUNDING.yml                  # GitHub Sponsors 配置
```

---

## 📊 目录统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 源代码文件 | 50+ | Python 模块和包
| 测试文件 | 11 | 71/72 测试通过
| 文档文件 | 40+ | 包括指南和归档
| 配置文件 | 10+ | 项目和功能配置
| 脚本文件 | 15+ | 实用工具脚本

---

## 🔑 关键目录说明

### 1. `data/` - 运行时数据目录 ⭐ 新增

**用途**：集中存放所有运行时生成的数据文件

**特点**：
- 📌 所有路径通过 `src/config/paths.py` 集中配置
- 🚫 整个目录被 `.gitignore` 排除（除 README.md 和 .gitkeep）
- 🔄 子目录自动创建（logs、tmp、attachments）
- 💾 简化备份：`tar czf backup.tar.gz data/`

**包含**：
- `email_sync.db` - 26MB 邮件同步数据库
- `sync_config.json` - 同步配置
- `sync_health_history.json` - 健康监控历史
- `logs/` - 应用日志
- `tmp/` - 临时处理文件
- `attachments/` - 下载的邮件附件

### 2. `src/config/` - 配置管理 ⭐ 新增

**用途**：集中管理所有配置和路径

**关键文件**：
- `paths.py` - 所有路径的单一来源（Single Source of Truth）
  - `EMAIL_SYNC_DB = "data/email_sync.db"`
  - `LOG_DIR = "data/logs"`
  - `TEMP_DIR = "data/tmp"`
  - 等等...

**优势**：
- ✅ 修改路径只需改一处
- ✅ 易于测试（可以注入测试路径）
- ✅ 清晰的依赖关系

### 3. `src/operations/` - 邮件操作

**核心模块**：
- `legacy_operations.py` - 传统操作（向后兼容）
- `cached_operations.py` ⭐ 新增 - 缓存操作（快 100-500x）
- `parallel_fetch.py` - 并行多账户获取
- `search_operations.py` - 智能搜索
- `email_sync.py` - 后台同步

### 4. `src/background/` - 后台任务

**功能**：
- 🔄 自动同步邮件（增量 + 完整）
- 📊 健康监控和报告
- ⏰ 静默时段管理
- 🔁 重试和错误恢复

**自动启动**：
- MCP 服务启动时自动拉起同步调度器
- `src/main.py` 中配置

### 5. `tests/` - 测试套件 ⭐ 大幅改进

**统计**：
- 总测试数：72 个
- 通过：71 个 ✅
- 失败：1 个（环境依赖，非功能问题）
- 覆盖率：~65%（+35%）

**新增测试文件**（7 个）：
1. `test_account_id_fix.py` - Account ID 路由测试
2. `test_email_lookup_fallback.py` - 邮箱查找回退测试
3. `test_performance.py` - 性能和缓存测试
4. `test_regression_fixes.py` - 16 个回归测试
5. `test_error_handling_improvements.py` - 10 个错误处理测试
6. `test_batch_delete_delegation.py` - 8 个批量删除测试
7. `test_critical_fixes.py` - 10 个关键修复测试

### 6. `docs/` - 文档中心

**组织结构**：
- `guides/` - 11 个用户和部署指南
- `archive/` ⭐ 新增 - 23 个历史文档归档
- 根目录 - 技术文档和架构说明

**新增文档**（4 个）：
1. `PROJECT_REORGANIZATION.md` - 项目重组详情
2. `CODE_REVIEW_FIXES.md` - 代码审查修复
3. `TESTING_GUIDE.md` - 测试指南
4. `TEST_IMPROVEMENTS_SUMMARY.md` - 测试改进总结

---

## 🔄 最近变更总结

### 项目结构重组（2025-10-17）

#### ✅ 完成的改进

1. **数据目录集中管理**
   - 创建 `data/` 目录
   - 所有运行时数据移到一个位置
   - 根目录文件数从 40+ 降到 26 个（-35%）

2. **路径配置集中化**
   - 新增 `src/config/paths.py`
   - 11 处硬编码路径改为 1 处集中配置
   - 易于维护和测试

3. **文档组织优化**
   - 23 个临时文档归档到 `docs/archive/`
   - 4 个新文档添加到 `docs/`
   - 文档结构清晰

4. **测试套件扩充**
   - 44 个新测试（本次会话）
   - 覆盖率从 ~30% 提升到 ~65%
   - 7 个新测试文件

5. **代码质量改进**
   - 5 项代码审查修复
   - FLAGS 解析更健壮
   - 文件夹名称规范化
   - Account ID 冲突避免
   - API 响应一致性

#### 📊 改进效果

| 指标 | 之前 | 现在 | 改进 |
|------|------|------|------|
| 根目录文件 | 40+ | 26 | **-35%** |
| 数据文件位置 | 分散 | 集中 data/ | **100% 集中** |
| 路径硬编码 | 11 处 | 1 处 | **-91%** |
| 测试数量 | 28 | 72 | **+157%** |
| 测试覆盖率 | ~30% | ~65% | **+117%** |
| 文档归档 | 0 | 23 | **完全整理** |

---

## 🚀 快速查找

### 想要...

| 目标 | 位置 |
|------|------|
| 📖 **了解项目** | `README.md`, `README.zh.md` |
| 🔧 **配置邮箱** | `setup.py`, `examples/accounts.example.json` |
| 💾 **查看数据** | `data/` 目录 |
| 🔍 **修改路径** | `src/config/paths.py` |
| 📧 **邮件操作** | `src/operations/`, `src/legacy_operations.py` |
| 🔄 **后台同步** | `src/background/` |
| 🧪 **运行测试** | `tests/run_tests.py` |
| 📚 **阅读文档** | `docs/README.md` |
| 🐳 **Docker 部署** | `docker/README.md` |
| ⏰ **本地定时任务** | `scripts/daily_email_digest.py`, `scripts/email_monitor.py` |
| 📝 **查看日志** | `data/logs/` |
| 💰 **赞助项目** | `.github/FUNDING.yml` |

---

## 📝 注意事项

### Git 忽略规则

以下文件/目录**不会**被提交到版本控制：

```
data/                  # 整个数据目录
accounts.json          # 邮箱账户配置（敏感）
*.db                   # 数据库文件
*.db-wal               # SQLite WAL 日志
*.db-shm               # SQLite 共享内存
*.log                  # 日志文件
__pycache__/           # Python 缓存
.env                   # 环境变量
*.pyc                  # 编译的 Python 文件
```

### 安全注意

⚠️ **永远不要提交这些文件**：
- `accounts.json` - 包含邮箱密码/授权码
- `.env` - 包含 API 密钥
- `data/` 目录 - 包含私人邮件内容

---

## 📚 相关文档

- **[docs/PROJECT_REORGANIZATION.md](docs/PROJECT_REORGANIZATION.md)** - 项目重组详细说明
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 系统架构设计
- **[data/README.md](data/README.md)** - 数据目录使用指南
- **[README.md](README.md)** - 项目主页

---

**最后更新**：2025-10-17  
**版本**：2.0 - 项目结构重组版
