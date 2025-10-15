# 🚀 生产环境部署指南

基于 Leo 的 review 建议，这里是生产环境稳定运行的完整配置指南。

## 🔧 Leo Review 要点修复

### 1. Execute Command 节点配置

**问题**: 缺少工作目录、超时、失败处理配置  
**解决方案**: 在 n8n 工作流的 "邮件监控" 节点中添加完整的 options 配置

```json
{
  "parameters": {
    "command": "python",
    "arguments": "/Users/leo/github.com/mcp-email-service/scripts/email_monitor.py run",
    "options": {
      "cwd": "/Users/leo/github.com/mcp-email-service",
      "timeout": 600000,
      "output": "json", 
      "continueOnFail": true
    }
  }
}
```

### 2. Webhook URL 去硬编码

**问题**: Webhook URL 写死在工作流中，无法复用  
**解决方案**: 使用环境变量

```json
{
  "parameters": {
    "url": "={{ $env.FEISHU_WEBHOOK }}",
    "options": {
      "allowUnauthorizedCerts": false
    }
  }
}
```

### 3. 完善的错误处理

**问题**: 只检查 `result.success`，忽略了 `exitCode` 和 `stderr`  
**解决方案**: 在 "解析结果" 节点中先检查脚本执行状态

```javascript
// 解析邮件监控结果
const input = $input.first().json;
const exitCode = input.exitCode || 0;
const stderr = input.stderr || '';
const stdout = input.stdout || '';

// 首先检查脚本执行状态
if (exitCode !== 0) {
  throw new Error(`脚本执行失败 (退出码: ${exitCode})\n错误信息: ${stderr}\n输出: ${stdout}`);
}

// 检查是否有输出
if (!stdout || stdout.trim() === '') {
  throw new Error('脚本没有返回任何输出');
}

// 解析 JSON 输出
let result;
try {
  result = JSON.parse(stdout);
} catch (parseError) {
  throw new Error(`JSON 解析失败: ${parseError.message}\n原始输出: ${stdout}`);
}

// 检查业务逻辑是否成功
if (!result.success) {
  throw new Error(`邮件监控失败: ${result.error || '未知错误'}`);
}
```

## 🛠️ 生产环境配置步骤

### 1. 环境变量设置

创建环境变量文件或在系统中设置：

```bash
# 必需的环境变量
export FEISHU_WEBHOOK="https://open.larksuite.com/open-apis/bot/v2/hook/a56c9638-cb65-4f95-bb11-9eb19e09692a"
export OPENAI_API_KEY="your_openai_api_key"
export PYTHONPATH="/Users/leo/github.com/mcp-email-service:$PYTHONPATH"

# 可选的 n8n 配置
export N8N_LOG_LEVEL="info"
export N8N_BASIC_AUTH_ACTIVE="false"
```

### 2. n8n 工作流导入

1. 导入更新后的工作流文件: `n8n/email_monitoring_workflow.json`
2. 确认所有节点配置正确
3. 测试工作流执行

### 3. 脚本权限和路径

```bash
# 确保脚本可执行
chmod +x /Users/leo/github.com/mcp-email-service/scripts/*.py

# 验证 Python 路径
which python
python --version

# 测试脚本执行
cd /Users/leo/github.com/mcp-email-service
python scripts/email_monitor.py status
```

### 4. 配置文件验证

确保所有配置文件格式正确：

```bash
# 验证 JSON 格式
python -m json.tool notification_config.json
python -m json.tool ai_filter_config.json
python -m json.tool email_monitor_config.json
```

## 📊 监控和日志

### 1. n8n 执行监控

- 查看 n8n 执行历史
- 监控工作流成功率
- 设置执行失败告警

### 2. 系统日志

```bash
# 查看邮件监控日志
tail -f email_monitor.log

# 查看 n8n 日志
tail -f ~/.n8n/logs/n8n.log

# 查看系统资源使用
htop
df -h
```

### 3. 健康检查

```bash
# 定期运行健康检查
python scripts/email_monitor.py status

# 查看通知统计
python scripts/notification_service.py stats 7

# 测试组件
python scripts/setup_n8n_monitoring.py --test-only
```

## 🔒 安全配置

### 1. API 密钥管理

- 使用环境变量存储敏感信息
- 定期轮换 API 密钥
- 限制 API 密钥权限范围

### 2. Webhook 安全

- 使用 HTTPS URL
- 配置 webhook 签名验证（如果支持）
- 限制 webhook 访问 IP

### 3. 文件权限

```bash
# 设置合适的文件权限
chmod 600 notification_config.json
chmod 600 ai_filter_config.json
chmod 600 accounts.json
```

## ⚡ 性能优化

### 1. 调整监控频率

根据邮件量调整 cron 表达式：

```javascript
// 高频率 (每2分钟)
"*/2 * * * *"

// 中频率 (每5分钟) - 推荐
"*/5 * * * *"

// 低频率 (每15分钟)
"*/15 * * * *"
```

### 2. 脚本超时设置

```json
{
  "options": {
    "timeout": 600000  // 10分钟超时
  }
}
```

### 3. 批量处理优化

```json
{
  "email": {
    "fetch_limit": 50,  // 增加批量大小
    "unread_only": true
  }
}
```

## 🚨 故障排除

### 1. 常见错误处理

| 错误类型 | 可能原因 | 解决方案 |
|----------|----------|----------|
| 退出码非零 | 脚本执行失败 | 检查 stderr，修复脚本问题 |
| JSON 解析失败 | 脚本输出格式错误 | 检查脚本输出，修复格式 |
| Webhook 发送失败 | 网络或 URL 问题 | 验证 URL 和网络连接 |
| 权限错误 | 文件或目录权限不足 | 检查并修复文件权限 |

### 2. 调试技巧

```bash
# 手动执行脚本查看详细输出
cd /Users/leo/github.com/mcp-email-service
python scripts/email_monitor.py run --verbose

# 检查环境变量
env | grep -E "(FEISHU|OPENAI|PYTHONPATH)"

# 测试 webhook
curl -X POST "$FEISHU_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"测试消息"}}'
```

### 3. 日志分析

```bash
# 查找错误模式
grep -i error email_monitor.log | tail -10

# 统计成功率
grep -c "SUCCESS" email_monitor.log
grep -c "ERROR" email_monitor.log

# 查看最近的执行
tail -50 email_monitor.log | grep -E "(INFO|ERROR|WARNING)"
```

## 📈 扩展配置

### 1. 多环境支持

```bash
# 开发环境
export N8N_ENV="development"
export FEISHU_WEBHOOK="$DEV_FEISHU_WEBHOOK"

# 生产环境  
export N8N_ENV="production"
export FEISHU_WEBHOOK="$PROD_FEISHU_WEBHOOK"
```

### 2. 负载均衡

如果有多个 n8n 实例：

```bash
# 使用不同的 cron 偏移
# 实例1: "0 */5 * * *"  (每5分钟的0秒)
# 实例2: "2 */5 * * *"  (每5分钟的2秒)
```

### 3. 备份和恢复

```bash
# 备份配置文件
tar -czf email_monitor_backup_$(date +%Y%m%d).tar.gz \
  *.json scripts/ n8n/ config_templates/

# 恢复配置
tar -xzf email_monitor_backup_YYYYMMDD.tar.gz
```

## ✅ 部署检查清单

- [ ] 环境变量已设置并验证
- [ ] n8n 工作流已导入并测试
- [ ] 脚本权限和路径正确
- [ ] 配置文件格式验证通过
- [ ] Webhook 连接测试成功
- [ ] 完整流程测试通过
- [ ] 日志监控已配置
- [ ] 错误告警已设置
- [ ] 备份策略已制定
- [ ] 文档已更新

## 📞 技术支持

遇到问题时的排查顺序：

1. 检查 n8n 执行历史和错误信息
2. 查看脚本日志文件
3. 手动执行脚本验证
4. 检查环境变量和配置
5. 验证网络连接和权限
6. 查看系统资源使用情况

---

**注意**: 这个配置已经根据 Leo 的 review 建议进行了完整的生产环境优化，可以稳定运行。
