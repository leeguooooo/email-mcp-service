#!/usr/bin/env python3
"""
测试 n8n API 连接
"""
import os
import sys
import requests
from pathlib import Path

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))


def test_n8n_connection():
    """测试 n8n API 连接"""
    n8n_url = os.getenv('N8N_URL', 'https://n8n.ifoodme.com')
    n8n_api_key = os.getenv('N8N_API_KEY')
    
    if not n8n_api_key:
        print("❌ 错误: 未设置 N8N_API_KEY 环境变量")
        print("\n请设置:")
        print("   export N8N_API_KEY='your_api_key'")
        return False
    
    print(f"🔍 测试 n8n API 连接...")
    print(f"   URL: {n8n_url}")
    print(f"   API Key: {'*' * 20}{n8n_api_key[-8:]}")
    print()
    
    headers = {
        'X-N8N-API-KEY': n8n_api_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        # 测试获取工作流列表
        response = requests.get(
            f'{n8n_url}/api/v1/workflows',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            workflows = response.json()
            workflow_list = workflows.get('data', [])
            
            print(f"✅ n8n API 连接成功!")
            print(f"   当前工作流数量: {len(workflow_list)}")
            
            if workflow_list:
                print(f"\n📋 现有工作流:")
                for wf in workflow_list[:5]:  # 只显示前5个
                    status = "🟢 激活" if wf.get('active') else "⚪ 未激活"
                    print(f"   {status} {wf.get('name')} (ID: {wf.get('id')})")
                if len(workflow_list) > 5:
                    print(f"   ... 还有 {len(workflow_list) - 5} 个工作流")
            
            print(f"\n✨ 可以开始导入工作流了!")
            print(f"   运行: ./setup_n8n.sh")
            return True
            
        elif response.status_code == 401:
            print(f"❌ 认证失败 (HTTP 401)")
            print(f"   请检查 N8N_API_KEY 是否正确")
            return False
            
        elif response.status_code == 403:
            print(f"❌ 权限不足 (HTTP 403)")
            print(f"   请确认 API Key 有足够的权限")
            return False
            
        else:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败: 无法连接到 {n8n_url}")
        print(f"   请检查:")
        print(f"   1. URL 是否正确")
        print(f"   2. 网络连接是否正常")
        print(f"   3. n8n 服务是否运行")
        return False
        
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        print(f"   请检查网络连接")
        return False
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False


if __name__ == "__main__":
    print("🚀 n8n API 连接测试\n")
    success = test_n8n_connection()
    sys.exit(0 if success else 1)
