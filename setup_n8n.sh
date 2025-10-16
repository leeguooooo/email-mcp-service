#!/bin/bash
# n8n 工作流自动设置脚本

echo "🚀 n8n 工作流自动设置"
echo ""

# 设置环境变量
export N8N_URL="https://n8n.ifoodme.com"
export FEISHU_WEBHOOK="https://open.larksuite.com/open-apis/bot/v2/hook/a56c9638-cb65-4f95-bb11-9eb19e09692a"
export PYTHONPATH="/Users/leo/github.com/mcp-email-service:$PYTHONPATH"

# 检查 N8N_API_KEY
if [ -z "$N8N_API_KEY" ]; then
    echo "❌ 错误: 未设置 N8N_API_KEY 环境变量"
    echo ""
    echo "请先设置 N8N_API_KEY:"
    echo "   export N8N_API_KEY='your_api_key'"
    echo ""
    echo "然后运行:"
    echo "   ./setup_n8n.sh"
    exit 1
fi

# 显示配置
echo "⚙️  配置信息:"
echo "   n8n URL: $N8N_URL"
echo "   飞书 Webhook: ${FEISHU_WEBHOOK:0:50}..."
echo "   脚本路径: $(pwd)"
echo ""

# 运行设置脚本
uv run python scripts/setup_n8n_workflow.py

echo ""
echo "✅ 设置完成！"
echo ""
echo "📝 下一步:"
echo "   1. 访问 $N8N_URL"
echo "   2. 检查工作流配置"
echo "   3. 设置 OPENAI_API_KEY (可选)"
echo "   4. 激活工作流"
echo ""
