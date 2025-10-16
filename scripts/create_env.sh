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
if [ ! -f config_templates/env.n8n.example ]; then
    echo "❌ 错误: 找不到模板文件 config_templates/env.n8n.example"
    exit 1
fi

cp config_templates/env.n8n.example .env
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

# N8N_API_KEY
echo "1️⃣  n8n API Key"
echo "   从 https://n8n.ifoodme.com/ 的 Settings → API 获取"
read -p "   请输入 N8N_API_KEY: " n8n_key
if [ -n "$n8n_key" ]; then
    # 使用 | 作为分隔符（更安全），转义 & / \ # | 等特殊字符
    # 注意：需要正确转义反斜杠本身
    escaped_key=$(printf '%s\n' "$n8n_key" | sed 's/[&/\\#|]/\\&/g')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|N8N_API_KEY=.*|N8N_API_KEY=$escaped_key|" .env
    else
        sed -i "s|N8N_API_KEY=.*|N8N_API_KEY=$escaped_key|" .env
    fi
    echo "   ✅ 已设置"
fi
echo ""

# OPENAI_API_KEY (可选)
echo "2️⃣  OpenAI API Key (可选 - 用于 AI 智能过滤)"
echo "   留空将使用关键词过滤"
read -p "   请输入 OPENAI_API_KEY (或按回车跳过): " openai_key
if [ -n "$openai_key" ]; then
    # 使用 | 作为分隔符（更安全），转义 & / \ # | 等特殊字符
    # 注意：需要正确转义反斜杠本身
    escaped_openai_key=$(printf '%s\n' "$openai_key" | sed 's/[&/\\#|]/\\&/g')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|OPENAI_API_KEY=.*|OPENAI_API_KEY=$escaped_openai_key|" .env
    else
        sed -i "s|OPENAI_API_KEY=.*|OPENAI_API_KEY=$escaped_openai_key|" .env
    fi
    echo "   ✅ 已设置"
else
    echo "   ⏭️  跳过 (将使用关键词过滤)"
fi
echo ""

# 显示配置
echo "✅ 配置完成！"
echo ""
echo "📋 当前配置:"
echo "   N8N_URL: https://n8n.ifoodme.com"
echo "   N8N_API_KEY: ${n8n_key:0:20}..."
echo "   FEISHU_WEBHOOK: 已配置"
if [ -n "$openai_key" ]; then
    echo "   OPENAI_API_KEY: ${openai_key:0:20}..."
else
    echo "   OPENAI_API_KEY: 未设置 (将使用关键词过滤)"
fi
echo ""

# 提示下一步
echo "🚀 下一步:"
echo "   1. 查看配置: cat .env"
echo "   2. 测试连接: ./setup_n8n.sh"
echo "   或直接运行: uv run python scripts/test_n8n_api.py"
echo ""

echo "💡 提示: .env 文件包含敏感信息，不会被 git 提交"
