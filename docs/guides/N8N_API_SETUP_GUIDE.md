# 🚀 n8n API 自动设置指南

使用 n8n API 自动导入和配置邮件监控工作流。

## 📋 前提条件

### 1. n8n API Key

你需要从 n8n 实例获取 API Key：

1. 登录 [n8n](https://n8n.ifoodme.com/)
2. 进入 **Settings** → **API**
3. 创建新的 API Key
4. 复制生成的 API Key

### 2. 环境变量

需要设置以下环境变量：

```bash
# 必需
export N8N_API_KEY="your_n8n_api_key_here"

# 可选 (已有默认值)
export N8N_URL="https://n8n.ifoodme.com"
export FEISHU_WEBHOOK="https://open.larksuite.com/open-apis/bot/v2/hook/a56c9638-cb65-4f95-bb11-9eb19e09692a"
export PYTHONPATH="/Users/leo/github.com/mcp-email-service:$PYTHONPATH"

# AI 过滤 (可选)
export OPENAI_API_KEY="your_openai_api_key"  # 用于 AI 智能过滤
```

## 🎯 快速开始

### 方法 1: 使用便捷脚本

```bash
# 1. 设置 N8N_API_KEY
export N8N_API_KEY="your_api_key"

# 2. 运行设置脚本
./setup_n8n.sh
```

### 方法 2: 直接运行 Python 脚本

```bash
# 1. 设置环境变量
export N8N_API_KEY="your_api_key"
export N8N_URL="https://n8n.ifoodme.com"
export FEISHU_WEBHOOK="your_webhook_url"

# 2. 运行 Python 脚本
python scripts/setup_n8n_workflow.py
```

## 📝 脚本功能

自动设置脚本会：

1. ✅ 测试 n8n API 连接
2. ✅ 读取工作流配置文件
3. ✅ 更新脚本路径和环境变量
4. ✅ 检查是否存在同名工作流
5. ✅ 创建或更新工作流
6. ✅ 提供激活选项

## 🔧 手动配置步骤

如果自动脚本遇到问题，可以手动配置：

### 1. 登录 n8n

访问 https://n8n.ifoodme.com/

### 2. 导入工作流

1. 点击右上角的 **+** 按钮
2. 选择 **Import from file**
3. 选择 `n8n/email_monitoring_workflow.json`
4. 点击 **Import**

### 3. 配置环境变量

在 n8n 界面中：

1. 进入 **Settings** → **Environments**
2. 添加以下变量：
   - `FEISHU_WEBHOOK`: 你的飞书 webhook URL
   - `OPENAI_API_KEY`: OpenAI API 密钥 (可选)
   - `PYTHONPATH`: 项目路径

### 4. 更新节点配置

编辑 **邮件监控** 节点：

```json
{
  "command": "python",
  "arguments": "/Users/leo/github.com/mcp-email-service/scripts/email_monitor.py run",
  "options": {
    "cwd": "/Users/leo/github.com/mcp-email-service",
    "timeout": 600000,
    "output": "json",
    "continueOnFail": true
  }
}
```

### 5. 激活工作流

点击右上角的 **Inactive** 按钮激活工作流。

## 🧪 测试工作流

### 1. 手动测试

在 n8n 界面中点击 **Execute Workflow** 按钮。

### 2. 检查执行历史

查看 **Executions** 页面，确认工作流运行正常。

### 3. 验证通知

检查飞书群组是否收到测试通知。

## 📊 脚本输出示例

```bash
🚀 n8n 工作流自动设置工具

⚙️  配置信息:
   n8n URL: https://n8n.ifoodme.com
   n8n API Key: ********************abcd1234
   飞书 Webhook: https://open.larksuite.com/open-apis/bot/v2/hook...
   脚本路径: /Users/leo/github.com/mcp-email-service

🔍 测试 n8n API 连接...
✅ n8n API 连接成功: https://n8n.ifoodme.com
📋 当前工作流数量: 3

📦 开始导入工作流...

📁 读取工作流文件: n8n/email_monitoring_workflow.json
   工作流名称: 智能邮件监控与通知

⚠️  发现同名工作流: 智能邮件监控与通知 (ID: 123)
   将更新现有工作流...
📤 正在更新工作流 ID: 123
✅ 工作流更新成功!

✅ 工作流设置完成!
   ID: 123
   名称: 智能邮件监控与通知
   URL: https://n8n.ifoodme.com/workflow/123

💡 提示:
   1. 请在 n8n 界面中检查工作流配置
   2. 确认环境变量设置正确:
      - FEISHU_WEBHOOK
      - OPENAI_API_KEY (可选)
      - PYTHONPATH
   3. 测试工作流执行

是否立即激活工作流? (y/N):
```

## 🛠️ 故障排除

### 1. API 连接失败

**错误**: `❌ n8n API 连接失败: HTTP 401`

**解决方案**:
- 检查 N8N_API_KEY 是否正确
- 确认 API Key 是否已激活
- 验证 n8n URL 是否正确

### 2. 工作流导入失败

**错误**: `❌ 工作流创建失败: HTTP 400`

**解决方案**:
- 检查工作流 JSON 文件格式
- 确认节点配置是否有效
- 查看详细错误信息

### 3. 权限错误

**错误**: `Permission denied`

**解决方案**:
```bash
# 给脚本添加执行权限
chmod +x scripts/setup_n8n_workflow.py
chmod +x setup_n8n.sh
```

### 4. 环境变量未生效

**解决方案**:
```bash
# 检查环境变量
env | grep -E "(N8N|FEISHU|OPENAI)"

# 重新设置
source ~/.bashrc  # 或 ~/.zshrc
```

## 📚 相关文档

- [n8n API 文档](https://docs.n8n.io/api/)
- [N8N_EMAIL_MONITORING_GUIDE.md](N8N_EMAIL_MONITORING_GUIDE.md) - 完整设置指南
- [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) - 生产部署指南

## 💡 高级用法

### 批量管理多个工作流

```python
from scripts.setup_n8n_workflow import N8NWorkflowManager

manager = N8NWorkflowManager(
    'https://n8n.ifoodme.com',
    'your_api_key'
)

# 列出所有工作流
workflows = manager.list_workflows()

# 批量激活
for workflow in workflows:
    manager.activate_workflow(workflow['id'])
```

### 自定义工作流配置

修改 `n8n/email_monitoring_workflow.json` 后重新运行：

```bash
python scripts/setup_n8n_workflow.py
```

脚本会自动检测并更新现有工作流。

## 🔒 安全建议

1. **API Key 保护**
   - 不要将 API Key 提交到 git
   - 使用环境变量存储
   - 定期轮换 API Key

2. **访问控制**
   - 限制 API Key 权限
   - 使用最小权限原则
   - 监控 API 使用情况

3. **Webhook 安全**
   - 使用 HTTPS URL
   - 配置签名验证
   - 限制访问 IP

---

**🎉 现在你可以通过一个命令自动设置 n8n 工作流了！**
