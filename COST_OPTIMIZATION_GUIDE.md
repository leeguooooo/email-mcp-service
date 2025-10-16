# 💰 API 成本优化指南

## 📊 成本分析

### OpenAI API 消耗预估

#### 使用 GPT-3.5-turbo (推荐)
| 邮件量/天 | Tokens/天 | 成本/天 | 成本/月 |
|-----------|----------|---------|---------|
| 50 封 | 5K-10K | $0.01-0.02 | $0.30-0.60 |
| 100 封 | 10K-20K | $0.02-0.04 | $0.60-1.20 |
| 500 封 | 50K-100K | $0.10-0.20 | $3-6 |
| 1000 封 | 100K-200K | $0.20-0.40 | $6-12 |

**价格**: GPT-3.5-turbo 约 $0.002/1K tokens

#### 使用 GPT-4 (更智能但贵10倍)
| 邮件量/天 | 成本/月 |
|-----------|---------|
| 50 封 | $3-6 |
| 100 封 | $6-12 |
| 500 封 | $30-60 |
| 1000 封 | $60-120 |

## 🎯 优化策略

### 1. 使用规则预过滤 (免费 + 快速)

系统已经内置了规则过滤，**会先用规则筛选，大幅减少 AI 调用**：

```json
{
  "filter_rules": {
    "high_priority_senders": [
      "boss@company.com",        // 直接标记为重要，不调用 AI
      "important@client.com"
    ],
    "spam_indicators": [
      "lottery", "winner",       // 直接标记为垃圾，不调用 AI
      "中奖", "恭喜"
    ],
    "low_priority_keywords": [
      "newsletter", "unsubscribe" // 直接标记为不重要，不调用 AI
    ]
  }
}
```

**优化效果**: 可以过滤掉 30-50% 的邮件，减少 AI 调用

### 2. 限制邮件正文长度

当前配置已优化：
```json
{
  "max_body_length": 500  // 只发送前 500 字符给 AI
}
```

**省钱效果**: 每封邮件减少 50-100 tokens

### 3. 调整监控频率

减少检查频率可以减少新邮件数量：

```javascript
// n8n 工作流 cron 设置
"*/5 * * * *"   // 每5分钟 (默认) - 适合高频场景
"*/10 * * * *"  // 每10分钟 - 推荐
"*/15 * * * *"  // 每15分钟 - 低成本
"0 * * * *"     // 每小时 - 最低成本
```

### 4. 限制获取邮件数量

编辑 `email_monitor_config.json`:
```json
{
  "email": {
    "fetch_limit": 10,      // 从 20 改为 10
    "unread_only": true
  }
}
```

### 5. 完全不使用 AI (免费方案)

**选项 A**: 不设置 `OPENAI_API_KEY`
- 系统会自动回退到关键词过滤
- 完全免费
- 准确率约 70-80%

**选项 B**: 禁用 AI 过滤
编辑 `email_monitor_config.json`:
```json
{
  "ai_filter": {
    "enabled": false  // 禁用 AI
  }
}
```

## 💡 推荐配置方案

### 🟢 方案 1: 极低成本 (<$1/月)
```json
{
  "email": {
    "fetch_limit": 10,
    "unread_only": true
  },
  "ai_filter": {
    "enabled": true,
    "priority_threshold": 0.8  // 提高阈值，减少通知
  }
}
```
- ✅ 监控频率: 每 10-15 分钟
- ✅ 邮件数量: 限制 10 封
- ✅ 使用规则预过滤
- 💰 预计成本: $0.30-1.00/月

### 🟡 方案 2: 平衡方案 ($1-3/月)
```json
{
  "email": {
    "fetch_limit": 20,
    "unread_only": true
  },
  "ai_filter": {
    "enabled": true,
    "priority_threshold": 0.7
  }
}
```
- ✅ 监控频率: 每 5 分钟
- ✅ 邮件数量: 默认 20 封
- ✅ 使用规则预过滤
- 💰 预计成本: $1-3/月

### 🟠 方案 3: 完全免费
```json
{
  "ai_filter": {
    "enabled": false  // 禁用 AI
  }
}
```
或者不设置 `OPENAI_API_KEY`

- ✅ 使用关键词过滤
- ✅ 完全免费
- ⚠️ 准确率降低 10-20%
- 💰 成本: $0

## 📈 实时监控成本

### 查看 OpenAI 使用量
1. 访问 https://platform.openai.com/usage
2. 查看每日 token 使用量
3. 设置预算告警

### 本地监控
```bash
# 查看过滤统计
python scripts/email_monitor.py run

# 输出会显示:
# - 获取邮件数: X
# - AI 过滤邮件数: Y  (这是实际调用 AI 的数量)
# - 重要邮件数: Z
```

## 🔧 优化配置示例

创建 `ai_filter_config.json`:

```json
{
  "model": "gpt-3.5-turbo",
  "max_body_length": 300,  // 减少到 300 字符
  "priority_threshold": 0.75,  // 提高阈值
  "filter_rules": {
    "high_priority_senders": [
      "boss@company.com",
      "ceo@company.com",
      "important@client.com"
    ],
    "spam_indicators": [
      "lottery", "winner", "congratulations",
      "unsubscribe", "newsletter",
      "中奖", "恭喜", "退订", "广告"
    ],
    "low_priority_keywords": [
      "promotion", "marketing", "advertisement",
      "推广", "营销", "促销"
    ]
  }
}
```

**效果**: 可以减少 40-60% 的 AI 调用

## 💸 成本对比

### 典型场景: 每天 100 封新邮件

| 优化方案 | AI 调用数 | 月成本 | 说明 |
|----------|-----------|--------|------|
| 无优化 | 100/天 | $6-12 | 所有邮件都用 AI |
| 规则预过滤 | 50/天 | $3-6 | 过滤掉 50% |
| + 降低频率 | 30/天 | $2-4 | 改为每 10 分钟 |
| + 限制数量 | 20/天 | $1-3 | 限制 10 封/次 |
| 仅关键词 | 0 | $0 | 完全不用 AI |

## ✅ 推荐设置 (月成本 <$1)

1. **设置规则过滤** - 添加常见发件人和关键词
2. **监控频率** - 改为每 10 分钟
3. **邮件数量** - 限制为 10 封
4. **正文长度** - 限制为 300 字符
5. **定期检查** - 查看 OpenAI 使用统计

这样配置下，**月成本通常在 $0.5-1 之间**，非常经济！

## 🎯 总结

- 💰 **低成本**: 使用规则预过滤 + GPT-3.5 = <$1/月
- ⚡ **高性能**: 规则过滤极快，AI 只处理需要的邮件
- 🎨 **可控制**: 随时调整频率、数量、阈值
- 🆓 **免费选项**: 完全可以不用 AI，使用关键词过滤

**建议**: 先用默认配置运行一周，查看实际消耗，再根据需要优化。
