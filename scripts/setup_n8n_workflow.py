#!/usr/bin/env python3
"""
通过 n8n API 自动导入和配置工作流
"""
import json
import os
import sys
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    env_path = repo_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"📝 已加载 .env 文件")
except ImportError:
    pass  # python-dotenv 不是必需的


class N8NWorkflowManager:
    """n8n 工作流管理器"""
    
    def __init__(self, api_url: str, api_key: str):
        """
        初始化 n8n 管理器
        
        Args:
            api_url: n8n API 地址
            api_key: n8n API 密钥
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-N8N-API-KEY': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def test_connection(self) -> bool:
        """测试 n8n API 连接"""
        try:
            response = requests.get(
                f'{self.api_url}/api/v1/workflows',
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                print(f"✅ n8n API 连接成功: {self.api_url}")
                return True
            else:
                print(f"❌ n8n API 连接失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
                return False
        except Exception as e:
            print(f"❌ n8n API 连接失败: {e}")
            return False
    
    def list_workflows(self) -> list:
        """列出所有工作流"""
        try:
            response = requests.get(
                f'{self.api_url}/api/v1/workflows',
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                workflows = response.json()
                print(f"📋 当前工作流数量: {len(workflows.get('data', []))}")
                return workflows.get('data', [])
            else:
                print(f"❌ 获取工作流列表失败: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ 获取工作流列表失败: {e}")
            return []
    
    def find_workflow_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """通过名称查找工作流"""
        workflows = self.list_workflows()
        for workflow in workflows:
            if workflow.get('name') == name:
                return workflow
        return None
    
    def create_workflow(self, workflow_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建新工作流"""
        try:
            # 准备工作流数据（不包含 active 字段，创建后默认为未激活）
            payload = {
                'name': workflow_data.get('name', '智能邮件监控与通知'),
                'nodes': workflow_data.get('nodes', []),
                'connections': workflow_data.get('connections', {}),
                'settings': workflow_data.get('settings', {})
            }
            
            print(f"📤 正在创建工作流: {payload['name']}")
            
            response = requests.post(
                f'{self.api_url}/api/v1/workflows',
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                workflow = response.json()
                print(f"✅ 工作流创建成功!")
                print(f"   工作流 ID: {workflow.get('id')}")
                print(f"   名称: {workflow.get('name')}")
                return workflow
            else:
                print(f"❌ 工作流创建失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 工作流创建失败: {e}")
            return None
    
    def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新现有工作流"""
        try:
            payload = {
                'name': workflow_data.get('name', '智能邮件监控与通知'),
                'nodes': workflow_data.get('nodes', []),
                'connections': workflow_data.get('connections', {}),
                'settings': workflow_data.get('settings', {})
            }
            
            print(f"📤 正在更新工作流 ID: {workflow_id}")
            
            response = requests.patch(
                f'{self.api_url}/api/v1/workflows/{workflow_id}',
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                workflow = response.json()
                print(f"✅ 工作流更新成功!")
                return workflow
            else:
                print(f"❌ 工作流更新失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 工作流更新失败: {e}")
            return None
    
    def activate_workflow(self, workflow_id: str) -> bool:
        """激活工作流"""
        try:
            response = requests.patch(
                f'{self.api_url}/api/v1/workflows/{workflow_id}',
                headers=self.headers,
                json={'active': True},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ 工作流已激活")
                return True
            else:
                print(f"❌ 工作流激活失败: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 工作流激活失败: {e}")
            return False
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        try:
            print(f"🗑️  正在删除工作流 ID: {workflow_id}")
            response = requests.delete(
                f'{self.api_url}/api/v1/workflows/{workflow_id}',
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ 工作流已删除")
                return True
            else:
                print(f"❌ 删除失败: HTTP {response.status_code}")
                print(f"   响应: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 删除时发生错误: {e}")
            return False
    
    def update_workflow_environment(self, workflow_data: Dict[str, Any], 
                                   feishu_webhook: str,
                                   script_path: str) -> Dict[str, Any]:
        """更新工作流中的环境变量"""
        # 使用 python3 命令（需要在 n8n 服务器上可用）
        # 注意：这要求在 n8n 服务器上安装了 Python 3 和项目依赖
        
        # 更新脚本路径
        for node in workflow_data.get('nodes', []):
            if node.get('name') == '邮件监控':
                if 'parameters' in node:
                    # 保持使用 python3 命令
                    if 'command' not in node['parameters']:
                        node['parameters']['command'] = 'python3'
                    
                    # 更新脚本参数
                    node['parameters']['arguments'] = f'{script_path}/scripts/email_monitor.py run'
                    
                    # 更新工作目录
                    if 'options' not in node['parameters']:
                        node['parameters']['options'] = {}
                    node['parameters']['options']['cwd'] = script_path
                    
                    # 确保设置 PYTHONPATH 环境变量
                    if 'env' not in node['parameters']['options']:
                        node['parameters']['options']['env'] = {}
                    node['parameters']['options']['env']['PYTHONPATH'] = script_path
        
        return workflow_data
    
    def import_workflow_from_file(self, workflow_file: str, 
                                  feishu_webhook: str,
                                  script_path: str,
                                  update_if_exists: bool = True) -> Optional[Dict[str, Any]]:
        """从文件导入工作流"""
        try:
            # 读取工作流文件
            with open(workflow_file, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            
            workflow_name = workflow_data.get('name', '智能邮件监控与通知')
            print(f"\n📁 读取工作流文件: {workflow_file}")
            print(f"   工作流名称: {workflow_name}")
            
            # 更新环境配置
            workflow_data = self.update_workflow_environment(
                workflow_data, feishu_webhook, script_path
            )
            
            # 检查是否已存在同名工作流
            existing = self.find_workflow_by_name(workflow_name)
            
            if existing:
                print(f"\n⚠️  发现同名工作流: {workflow_name} (ID: {existing['id']})")
                if update_if_exists:
                    # 删除旧工作流，重新创建
                    print("   将删除旧工作流并重新创建...")
                    if self.delete_workflow(existing['id']):
                        print("   正在创建新工作流...")
                        return self.create_workflow(workflow_data)
                    else:
                        print("   ⚠️  删除失败，尝试更新...")
                        return self.update_workflow(existing['id'], workflow_data)
                else:
                    print("   跳过导入 (已存在)")
                    return existing
            else:
                return self.create_workflow(workflow_data)
                
        except Exception as e:
            print(f"❌ 导入工作流失败: {e}")
            return None


def main():
    """主函数"""
    print("🚀 n8n 工作流自动设置工具\n")
    
    # 获取配置
    n8n_url = os.getenv('N8N_URL', 'https://n8n.ifoodme.com')
    n8n_api_key = os.getenv('N8N_API_KEY')
    feishu_webhook = os.getenv('FEISHU_WEBHOOK', 'https://open.larksuite.com/open-apis/bot/v2/hook/a56c9638-cb65-4f95-bb11-9eb19e09692a')
    script_path = str(repo_root)
    
    # 检查必需的配置
    if not n8n_api_key:
        print("❌ 错误: 未设置 N8N_API_KEY 环境变量")
        print("\n请设置环境变量:")
        print("   export N8N_API_KEY='your_api_key'")
        print("   export N8N_URL='https://n8n.ifoodme.com'  # 可选，默认值已设置")
        print("   export FEISHU_WEBHOOK='your_webhook_url'  # 可选，默认值已设置")
        sys.exit(1)
    
    print(f"⚙️  配置信息:")
    print(f"   n8n URL: {n8n_url}")
    print(f"   n8n API Key: {'*' * 20}{n8n_api_key[-8:]}")
    print(f"   飞书 Webhook: {feishu_webhook[:50]}...")
    print(f"   脚本路径: {script_path}")
    
    # 初始化管理器
    manager = N8NWorkflowManager(n8n_url, n8n_api_key)
    
    # 测试连接
    print("\n🔍 测试 n8n API 连接...")
    if not manager.test_connection():
        print("\n❌ 无法连接到 n8n API，请检查:")
        print("   1. n8n URL 是否正确")
        print("   2. n8n API Key 是否有效")
        print("   3. 网络连接是否正常")
        sys.exit(1)
    
    # 导入工作流
    workflow_file = repo_root / 'n8n' / 'email_monitoring_workflow.json'
    if not workflow_file.exists():
        print(f"\n❌ 工作流文件不存在: {workflow_file}")
        sys.exit(1)
    
    print(f"\n📦 开始导入工作流...")
    workflow = manager.import_workflow_from_file(
        str(workflow_file),
        feishu_webhook,
        script_path,
        update_if_exists=True
    )
    
    if workflow:
        workflow_id = workflow.get('id')
        workflow_name = workflow.get('name')
        
        print(f"\n✅ 工作流设置完成!")
        print(f"   ID: {workflow_id}")
        print(f"   名称: {workflow_name}")
        print(f"   URL: {n8n_url}/workflow/{workflow_id}")
        
        # 询问是否激活
        print(f"\n💡 提示:")
        print(f"   1. 请在 n8n 界面中检查工作流配置")
        print(f"   2. 确认环境变量设置正确:")
        print(f"      - FEISHU_WEBHOOK")
        print(f"      - OPENAI_API_KEY (可选)")
        print(f"      - PYTHONPATH")
        print(f"   3. 测试工作流执行")
        
        activate = input(f"\n是否立即激活工作流? (y/N): ").strip().lower()
        if activate == 'y':
            if manager.activate_workflow(workflow_id):
                print(f"\n🎉 工作流已激活！系统将每5分钟自动运行。")
            else:
                print(f"\n⚠️  工作流激活失败，请手动在 n8n 界面中激活。")
        else:
            print(f"\n📝 工作流已创建但未激活，请在 n8n 界面中手动激活。")
        
        print(f"\n🔗 访问工作流: {n8n_url}/workflow/{workflow_id}")
        
    else:
        print(f"\n❌ 工作流设置失败")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  操作已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
