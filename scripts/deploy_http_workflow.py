#!/usr/bin/env python3
"""
部署 HTTP API 工作流到 n8n
"""
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = repo_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"📝 已加载 .env 文件\n")
except ImportError:
    pass

from scripts.setup_n8n_workflow import N8NWorkflowManager


def main():
    """部署 HTTP 工作流"""
    print("🚀 部署 HTTP API 工作流到 n8n\n")
    
    # 获取配置
    n8n_url = os.getenv('N8N_URL', 'https://n8n.ifoodme.com')
    n8n_api_key = os.getenv('N8N_API_KEY')
    
    if not n8n_api_key:
        print("❌ 错误: 未设置 N8N_API_KEY")
        print("\n请设置:")
        print("   export N8N_API_KEY='your_api_key'")
        sys.exit(1)
    
    print(f"⚙️  配置:")
    print(f"   n8n URL: {n8n_url}")
    print(f"   API Key: {'*' * 20}{n8n_api_key[-8:]}")
    print()
    
    # 创建管理器
    manager = N8NWorkflowManager(n8n_url, n8n_api_key)
    
    # 测试连接
    print("🔍 测试 n8n 连接...")
    if not manager.test_connection():
        print("❌ 连接失败")
        sys.exit(1)
    
    # 读取 HTTP 工作流
    workflow_file = repo_root / 'n8n' / 'email_monitoring_http_workflow.json'
    print(f"\n📁 读取工作流: {workflow_file}")
    
    with open(workflow_file, 'r', encoding='utf-8') as f:
        workflow_data = json.load(f)
    
    workflow_name = workflow_data.get('name', '智能邮件监控与通知 (HTTP API)')
    print(f"   工作流名称: {workflow_name}")
    
    # 检查是否存在旧工作流
    existing = manager.find_workflow_by_name(workflow_name)
    
    if existing:
        print(f"\n⚠️  发现同名工作流 (ID: {existing['id']})")
        print("   将删除并重新创建...")
        
        if manager.delete_workflow(existing['id']):
            print("   ✅ 旧工作流已删除")
        else:
            print("   ⚠️  删除失败，继续创建...")
    
    # 创建新工作流
    print(f"\n📤 创建工作流: {workflow_name}")
    result = manager.create_workflow(workflow_data)
    
    if result:
        workflow_id = result.get('id')
        print(f"\n✅ 工作流部署成功!")
        print(f"   ID: {workflow_id}")
        print(f"   名称: {workflow_name}")
        print(f"   URL: {n8n_url}/workflow/{workflow_id}")
        
        print(f"\n🔒 重要: 在 n8n 中设置环境变量")
        print(f"   1. 访问 n8n: {n8n_url}/settings/environments")
        print(f"   2. 添加以下环境变量:")
        print(f"")
        print(f"      变量名: EMAIL_API_URL")
        print(f"      变量值: 你的邮件 API 基础地址（不要包含 /api/xxx 路径）")
        print(f"      示例: https://your-domain.com")
        print(f"      ⚠️  注意：只填域名，具体端点由工作流自动拼接")
        print(f"")
        print(f"      变量名: EMAIL_API_KEY")
        print(f"      变量值: 你的 API 密钥")
        print(f"      生成: openssl rand -hex 32")
        print(f"")
        print(f"   3. 保存环境变量")
        
        print(f"\n📝 然后:")
        print(f"   1. 访问工作流: {n8n_url}/workflow/{workflow_id}")
        print(f"   2. 测试工作流: 点击 'Execute Workflow'")
        print(f"   3. 激活工作流: 点击右上角的开关")
        
        print(f"\n⚠️  安全提示:")
        print(f"   - 不要在代码中硬编码 API 地址")
        print(f"   - 使用 n8n 环境变量存储敏感信息")
        print(f"   - 确保 API 服务有适当的访问控制")
        
        return 0
    else:
        print("\n❌ 工作流部署失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

