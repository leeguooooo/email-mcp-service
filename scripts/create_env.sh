#!/bin/bash
# 创建 .env 文件的辅助脚本

echo "🔧 创建 .env 配置文件"
echo ""

# 检查 .env 是否已存在
if [ -f .env ]; then
    echo "⚠️  .env 文件已存在"
    read -p "是否覆盖? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 已取消"
        exit 1
    fi
fi

# 复制模板
if [ ! -f config_templates/env.example ]; then
    echo "❌ 错误: 找不到模板文件 config_templates/env.example"
    exit 1
fi

cp config_templates/env.example .env
echo "✅ 已创建 .env 文件"
echo ""

# 交互式配置
echo "📝 配置必需的环境变量"
echo ""

# 检测操作系统，处理 sed -i 的跨平台问题
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    SED_INPLACE="sed -i ''"
else
    # Linux
    SED_INPLACE="sed -i"
fi

# FEISHU_WEBHOOK
echo "1️⃣  Lark/Feishu Webhook"
read -p "   请输入 FEISHU_WEBHOOK (可留空): " feishu_webhook
if [ -n "$feishu_webhook" ]; then
    escaped_hook=$(printf '%s\n' "$feishu_webhook" | sed 's/[&/\\#|]/\\&/g')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|FEISHU_WEBHOOK=.*|FEISHU_WEBHOOK=$escaped_hook|" .env
    else
        sed -i "s|FEISHU_WEBHOOK=.*|FEISHU_WEBHOOK=$escaped_hook|" .env
    fi
    echo "   ✅ 已设置"
fi
echo ""

# OPENAI_API_KEY
echo "2️⃣  OpenAI API Key"
read -p "   请输入 OPENAI_API_KEY (可留空): " openai_key
if [ -n "$openai_key" ]; then
    escaped_key=$(printf '%s\n' "$openai_key" | sed 's/[&/\\#|]/\\&/g')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|OPENAI_API_KEY=.*|OPENAI_API_KEY=$escaped_key|" .env
    else
        sed -i "s|OPENAI_API_KEY=.*|OPENAI_API_KEY=$escaped_key|" .env
    fi
    echo "   ✅ 已设置"
fi
echo ""

# TELEGRAM
echo "3️⃣  Telegram Bot (可选)"
read -p "   请输入 TELEGRAM_BOT_TOKEN (可留空): " tg_token
if [ -n "$tg_token" ]; then
    escaped_tg=$(printf '%s\n' "$tg_token" | sed 's/[&/\\#|]/\\&/g')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$escaped_tg|" .env
    else
        sed -i "s|TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$escaped_tg|" .env
    fi
    echo "   ✅ 已设置"
fi

read -p "   请输入 TELEGRAM_CHAT_ID (可留空): " tg_chat
if [ -n "$tg_chat" ]; then
    escaped_chat=$(printf '%s\n' "$tg_chat" | sed 's/[&/\\#|]/\\&/g')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|TELEGRAM_CHAT_ID=.*|TELEGRAM_CHAT_ID=$escaped_chat|" .env
    else
        sed -i "s|TELEGRAM_CHAT_ID=.*|TELEGRAM_CHAT_ID=$escaped_chat|" .env
    fi
    echo "   ✅ 已设置"
fi
echo ""

# 显示配置
echo "✅ 配置完成！"
echo ""
echo "📋 当前配置:"
echo "   FEISHU_WEBHOOK: ${feishu_webhook:0:20}..."
echo "   OPENAI_API_KEY: ${openai_key:0:20}..."
echo "   TELEGRAM_BOT_TOKEN: ${tg_token:0:20}..."
echo "   TELEGRAM_CHAT_ID: ${tg_chat:0:20}..."
echo ""

# 提示下一步
echo "🚀 下一步:"
echo "   1. 查看配置: cat .env"
echo "   2. 运行本地定时任务: uv run python scripts/daily_email_digest.py daemon"
echo ""

echo "💡 提示: .env 文件包含敏感信息，不会被 git 提交"
