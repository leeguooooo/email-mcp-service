# 🔧 修复 n8n 工作流 - Python 命令问题

## 问题

n8n 工作流执行时报错：`python: not found`

**原因**: 工作流使用 `python` 命令，但系统中只有通过 `uv` 管理的 Python。

## 解决方案

### 方法 1: 在 n8n 界面中手动修改 (推荐)

1. **访问工作流**
   - 打开 https://n8n.ifoodme.com/workflow/Ga8XqH1CRr7pM0rf

2. **编辑"邮件监控"节点**
   - 点击"邮件监控"节点
   - 修改配置：

**修改前**:
```json
{
  "command": "python",
  "arguments": "/Users/leo/github.com/mcp-email-service/scripts/email_monitor.py run"
}
```

**修改后**:
```json
{
  "command": "uv",
  "arguments": "run python /Users/leo/github.com/mcp-email-service/scripts/email_monitor.py run"
}
```

3. **保存工作流**
   - 点击右上角的"Save"按钮

4. **测试执行**
   - 点击"Execute Workflow"测试

### 方法 2: 删除旧工作流，重新导入

1. **在 n8n 界面中删除工作流**
   - 访问 https://n8n.ifoodme.com/workflows
   - 找到"智能邮件监控与通知"
   - 删除它

2. **重新运行部署脚本**
   ```bash
   ./setup_n8n.sh
   ```

3. **激活新工作流**
   - 在 n8n 界面中激活

### 方法 3: 使用系统 Python 路径

如果你有系统 Python，可以使用完整路径：

```json
{
  "command": "/usr/bin/python3",
  "arguments": "/Users/leo/github.com/mcp-email-service/scripts/email_monitor.py run"
}
```

## 验证修复

修改后，在 n8n 中测试执行：

1. 点击"Execute Workflow"
2. 查看"邮件监控"节点的输出
3. 应该看到 JSON 格式的结果，类似：

```json
{
  "success": true,
  "message": "Monitoring cycle completed successfully",
  "stats": {
    "fetched_emails": 20,
    "important_emails": 0,
    "notifications_sent": 0
  }
}
```

## Leo Review 问题修复

已修复以下问题：

### ✅ 1. sed 分隔符问题
- **问题**: API key 中的 `/` 会导致 sed 命令失败
- **修复**: 改用 `#` 作为分隔符，并转义特殊字符
```bash
# 修改前
sed -i '' "s/N8N_API_KEY=.*/N8N_API_KEY=$n8n_key/" .env

# 修改后
escaped_key=$(printf '%s\n' "$n8n_key" | sed 's/[&/\]/\\&/g')
sed -i '' "s#N8N_API_KEY=.*#N8N_API_KEY=$escaped_key#" .env
```

### ✅ 2. 跨平台兼容性
- **问题**: `sed -i ''` 在 Linux 上不工作
- **修复**: 检测操作系统，分别处理 macOS 和 Linux
```bash
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s#N8N_API_KEY=.*#N8N_API_KEY=$escaped_key#" .env
else
    sed -i "s#N8N_API_KEY=.*#N8N_API_KEY=$escaped_key#" .env
fi
```

## 下一步

1. **修改工作流配置** (方法 1 推荐)
2. **测试执行** - 确认能正常获取邮件
3. **激活工作流** - 开始自动监控
4. **查看执行历史** - 确认定时运行正常

## 需要帮助？

如果遇到其他问题，可以：
1. 查看 n8n 执行日志
2. 运行本地测试: `uv run python scripts/email_monitor.py run`
3. 查看详细文档: `START_HERE.md`
