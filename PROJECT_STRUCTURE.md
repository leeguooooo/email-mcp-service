# 📁 项目结构

本文档描述 MCP Email Service 的完整目录结构和文件组织。

---

## 🌳 目录树

```
mcp-email-service/
├── 📄 核心文档
│   ├── README.md                    # 项目主页（英文）
│   ├── README.zh.md                 # 项目主页（中文）
│   ├── LICENSE                      # MIT 许可证
│   ├── CHANGELOG.md                 # 版本变更历史
│   └── CLAUDE.md                    # AI 助手使用指南
│
├── ⚙️  配置文件
│   ├── pyproject.toml               # 项目配置和依赖
│   ├── requirements.txt             # Python 依赖列表
│   ├── uv.lock                      # 依赖锁定文件
│   ├── .gitignore                   # Git 忽略规则
│   └── .python-version              # Python 版本
│
├── 🔧 启动脚本
│   ├── run.sh                       # MCP 服务启动脚本
│   └── setup.py                     # 交互式配置脚本
│
├── 📂 源代码 (src/)
│   ├── __main__.py                  # 程序入口
│   ├── main.py                      # MCP 服务主程序
│   ├── account_manager.py           # 账号管理
│   ├── connection_manager.py        # 连接管理
│   ├── models.py                    # 数据模型
│   ├── core/                        # 核心功能
│   │   ├── tool_handlers.py         # MCP 工具处理器
│   │   ├── tool_registry.py         # 工具注册表
│   │   └── tool_schemas.py          # 工具模式定义
│   ├── operations/                  # 邮件操作
│   │   ├── email_operations.py      # 邮件基础操作
│   │   ├── parallel_operations.py   # 并行操作
│   │   └── ...                      # 其他操作模块
│   ├── services/                    # 业务服务
│   │   ├── email_service.py         # 邮件服务
│   │   ├── folder_service.py        # 文件夹服务
│   │   └── system_service.py        # 系统服务
│   ├── database/                    # 数据库
│   │   ├── email_database.py        # 邮件数据库
│   │   └── sync_manager.py          # 同步管理
│   ├── background/                  # 后台任务
│   │   ├── sync_scheduler.py        # 同步调度器
│   │   └── sync_health_monitor.py   # 健康监控
│   └── config/                      # 配置
│       └── messages.py              # 消息模板
│
├── 📜 脚本 (scripts/)
│   ├── email_monitor_api.py         # 🌟 FastAPI 服务
│   ├── email_translator.py          # 🌟 邮件翻译模块
│   ├── call_email_tool.py           # MCP 工具调用
│   ├── deploy_http_workflow.py      # n8n 工作流部署
│   ├── setup_n8n_workflow.py        # n8n 配置脚本
│   ├── create_env.sh                # 环境变量生成
│   ├── test_connection.py           # 连接测试
│   ├── test_sync.py                 # 同步测试
│   └── init_sync.py                 # 同步初始化
│
├── 🧪 测试 (tests/)
│   ├── test_mcp_tools.py            # MCP 工具测试
│   ├── test_account_manager.py      # 账号管理测试
│   ├── test_parallel_operations.py  # 并行操作测试
│   └── run_tests.py                 # 测试运行器
│
├── 📚 文档 (docs/)
│   ├── README.md                    # 📍 文档导航（入口）
│   ├── guides/                      # 用户指南
│   │   ├── EMAIL_TRANSLATE_WORKFLOW_GUIDE.md  # 🌟 翻译工作流
│   │   ├── HTTP_API_QUICK_START.md           # HTTP API 快速上手
│   │   ├── SECURITY_SETUP_GUIDE.md           # 安全配置
│   │   ├── FINAL_DEPLOYMENT_CHECKLIST.md     # 部署清单
│   │   ├── PRODUCTION_DEPLOYMENT_GUIDE.md    # 生产部署
│   │   ├── N8N_EMAIL_MONITORING_GUIDE.md     # n8n 监控
│   │   ├── LARK_SETUP_GUIDE.md               # 飞书配置
│   │   ├── N8N_API_SETUP_GUIDE.md            # n8n API
│   │   ├── TRANSLATION_WORKFLOW_SUMMARY.md   # 实现总结
│   │   ├── CRITICAL_FIXES.md                 # Bug 修复
│   │   └── OPEN_SOURCE_READINESS.md          # 开源清单
│   ├── archive/                     # 历史文档归档
│   │   └── ...                      # 过时文档
│   ├── ARCHITECTURE.md              # 系统架构
│   ├── database_design.md           # 数据库设计
│   ├── CONNECTION_POOL_FIX.md       # 连接池修复
│   ├── SERVICE_OPTIMIZATION.md      # 服务优化
│   └── CLEANUP_SUMMARY.md           # 清理记录
│
├── 🔧 n8n 工作流 (n8n/)
│   ├── README.md                    # n8n 工作流说明
│   ├── email_translate_workflow.json  # 🌟 翻译工作流
│   ├── email_monitoring_http_workflow.json  # HTTP API 工作流
│   └── email_monitoring_workflow.json       # 旧版工作流
│
├── 📋 配置示例 (examples/)
│   ├── README.md                    # 配置说明
│   ├── accounts.example.json        # 邮箱账号示例
│   ├── sync_config.json.example     # 同步配置示例
│   └── .env.example                 # 环境变量示例
│
├── 📦 配置模板 (config_templates/)
│   ├── ai_filter_config.example.json
│   ├── notification_config.example.json
│   └── env.n8n.example
│
├── 🐳 Docker (docker/)
│   ├── README.md                    # Docker 使用说明
│   ├── Dockerfile.optimized         # 优化版 Dockerfile
│   ├── Dockerfile.optional          # 可选 Dockerfile
│   └── .dockerignore                # Docker 忽略规则
│
├── 🔐 Smithery 配置（根目录）
│   ├── smithery.yaml                # Smithery 主配置
│   ├── smithery-minimal.yaml        # 最小配置
│   └── smithery-debug.yaml          # 调试配置
│
└── .smithery/                       # Smithery 内部文件
    └── smithery_wrapper.py          # 启动包装器

```

---

## 📝 文件类别说明

### 🚀 核心入口
| 文件 | 说明 |
|------|------|
| `README.md` | 项目主页，新用户从这里开始 |
| `run.sh` | 启动 MCP 服务 |
| `setup.py` | 交互式配置邮箱账号 |

### 📚 必读文档
| 文件 | 用途 |
|------|------|
| `docs/README.md` | 📍 文档导航入口 |
| `docs/guides/EMAIL_TRANSLATE_WORKFLOW_GUIDE.md` | 🌟 邮件翻译功能完整指南 |
| `docs/guides/HTTP_API_QUICK_START.md` | API 服务快速上手 |
| `docs/guides/SECURITY_SETUP_GUIDE.md` | 安全配置必读 |

### 🌟 核心功能
| 模块 | 说明 |
|------|------|
| `scripts/email_monitor_api.py` | FastAPI 服务（翻译、监控） |
| `scripts/email_translator.py` | 邮件翻译和总结 |
| `n8n/email_translate_workflow.json` | n8n 自动化工作流 |

### ⚙️  配置文件（需要创建）
| 文件 | 从哪里复制 | 说明 |
|------|----------|------|
| `accounts.json` | `examples/accounts.example.json` | 邮箱账号配置 |
| `.env` | `examples/.env.example` | 环境变量（用于 n8n） |
| `sync_config.json` | `examples/sync_config.json.example` | 同步配置（可选） |

---

## 🗂️ 目录用途

### `src/` - 核心源代码
MCP 服务的主要实现代码，包含：
- 邮件操作（IMAP/SMTP）
- 账号管理
- 工具注册和处理
- 数据库和同步

### `scripts/` - 独立脚本
可以独立运行的脚本：
- **email_monitor_api.py** - FastAPI HTTP 服务
- **email_translator.py** - 翻译模块
- **deploy_http_workflow.py** - 部署工具
- **test_*.py** - 测试脚本

### `docs/` - 完整文档
- `docs/README.md` - 文档导航（从这里开始）
- `docs/guides/` - 用户指南和教程
- `docs/archive/` - 历史文档归档
- `docs/*.md` - 技术文档

### `n8n/` - 自动化工作流
n8n 工作流配置文件，可直接导入 n8n：
- **email_translate_workflow.json** - 🌟 主要工作流

### `examples/` - 配置示例
所有配置文件的示例模板，复制后修改使用

### `docker/` - Docker 部署
Docker 相关文件和文档

### `tests/` - 测试套件
单元测试和集成测试

---

## 🔍 快速查找

### 我想...

**开始使用项目**
→ 阅读 `README.md`

**配置邮箱账号**
→ 运行 `python setup.py` 或复制 `examples/accounts.example.json`

**部署翻译功能**
→ 阅读 `docs/guides/EMAIL_TRANSLATE_WORKFLOW_GUIDE.md`

**查看所有文档**
→ 打开 `docs/README.md`

**安全配置**
→ 阅读 `docs/guides/SECURITY_SETUP_GUIDE.md`

**Docker 部署**
→ 查看 `docker/README.md`

**贡献代码**
→ 阅读 `README.md` 中的 Contributing 部分

**查看 API 文档**
→ 运行 `uvicorn scripts.email_monitor_api:app` 访问 `/docs`

---

## 📦 数据文件（.gitignore 忽略）

以下文件不会被 git 跟踪：
- `accounts.json` - 邮箱账号配置（敏感）
- `.env` - 环境变量（敏感）
- `*.db`, `*.db-wal`, `*.db-shm` - 数据库文件
- `sync_config.json` - 同步配置（可能包含敏感信息）
- `sync_health_history.json` - 健康监控历史
- `test_sync.log` - 测试日志

---

## ✨ 最佳实践

### 新用户
1. 阅读 `README.md`
2. 查看 `docs/README.md` 了解文档结构
3. 选择合适的指南开始

### 开发者
1. 核心代码在 `src/`
2. 测试在 `tests/`
3. 文档在 `docs/`
4. 提交前运行 `uv run pytest`

### 部署者
1. 阅读 `docs/guides/PRODUCTION_DEPLOYMENT_GUIDE.md`
2. 查看 `docs/guides/SECURITY_SETUP_GUIDE.md`
3. 使用 `docs/guides/FINAL_DEPLOYMENT_CHECKLIST.md`

---

**维护**: 保持此文档与实际结构同步  
**最后更新**: 2025-10-16  
**版本**: 1.0.0

