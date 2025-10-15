#!/usr/bin/env python3
"""
n8n 邮件监控系统快速设置脚本
自动创建配置文件、检查依赖、验证环境
"""
import json
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))


class N8NMonitoringSetup:
    """n8n 监控系统设置器"""
    
    def __init__(self):
        self.repo_root = repo_root
        self.scripts_dir = self.repo_root / "scripts"
        self.config_templates_dir = self.repo_root / "config_templates"
        self.n8n_dir = self.repo_root / "n8n"
    
    def check_dependencies(self) -> Dict[str, bool]:
        """检查依赖项"""
        print("🔍 检查依赖项...")
        
        dependencies = {
            "python": False,
            "n8n": False,
            "uv": False,
            "openai": False,
            "anthropic": False,
            "requests": False
        }
        
        # 检查 Python
        try:
            result = subprocess.run([sys.executable, "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                dependencies["python"] = True
                print(f"  ✅ Python: {result.stdout.strip()}")
            else:
                print("  ❌ Python: 未找到")
        except Exception:
            print("  ❌ Python: 检查失败")
        
        # 检查 n8n
        try:
            result = subprocess.run(["n8n", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                dependencies["n8n"] = True
                print(f"  ✅ n8n: {result.stdout.strip()}")
            else:
                print("  ❌ n8n: 未安装")
        except Exception:
            print("  ❌ n8n: 未安装或不在 PATH 中")
        
        # 检查 uv
        try:
            result = subprocess.run(["uv", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                dependencies["uv"] = True
                print(f"  ✅ uv: {result.stdout.strip()}")
            else:
                print("  ❌ uv: 未安装")
        except Exception:
            print("  ❌ uv: 未安装或不在 PATH 中")
        
        # 检查 Python 包
        python_packages = ["openai", "anthropic", "requests"]
        for package in python_packages:
            try:
                __import__(package)
                dependencies[package] = True
                print(f"  ✅ {package}: 已安装")
            except ImportError:
                print(f"  ❌ {package}: 未安装")
        
        return dependencies
    
    def install_dependencies(self) -> bool:
        """安装缺失的依赖"""
        print("\\n📦 安装 Python 依赖...")
        
        try:
            # 尝试使用 uv
            if shutil.which("uv"):
                print("  使用 uv 安装依赖...")
                result = subprocess.run(
                    ["uv", "add", "openai", "anthropic", "requests"],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print("  ✅ 依赖安装成功")
                    return True
                else:
                    print(f"  ❌ uv 安装失败: {result.stderr}")
            
            # 回退到 pip
            print("  使用 pip 安装依赖...")
            packages = ["openai", "anthropic", "requests"]
            for package in packages:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(f"    ✅ {package} 安装成功")
                else:
                    print(f"    ❌ {package} 安装失败: {result.stderr}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"  ❌ 依赖安装失败: {e}")
            return False
    
    def create_config_files(self) -> bool:
        """创建配置文件"""
        print("\\n📝 创建配置文件...")
        
        config_mappings = {
            "ai_filter_config.example.json": "ai_filter_config.json",
            "notification_config.example.json": "notification_config.json", 
            "email_monitor_config.example.json": "email_monitor_config.json"
        }
        
        try:
            for template_name, config_name in config_mappings.items():
                template_path = self.config_templates_dir / template_name
                config_path = self.repo_root / config_name
                
                if config_path.exists():
                    print(f"  ⚠️  {config_name} 已存在，跳过")
                    continue
                
                if not template_path.exists():
                    print(f"  ❌ 模板文件不存在: {template_path}")
                    continue
                
                # 复制模板文件
                shutil.copy2(template_path, config_path)
                print(f"  ✅ 创建 {config_name}")
            
            return True
            
        except Exception as e:
            print(f"  ❌ 配置文件创建失败: {e}")
            return False
    
    def setup_environment_variables(self) -> None:
        """设置环境变量指南"""
        print("\\n🔧 环境变量设置指南:")
        print("  请根据需要设置以下环境变量:")
        print()
        
        env_vars = {
            "FEISHU_WEBHOOK": "飞书 Webhook URL (n8n 工作流需要)",
            "OPENAI_API_KEY": "OpenAI API 密钥 (如果使用 OpenAI)",
            "ANTHROPIC_API_KEY": "Anthropic API 密钥 (如果使用 Claude)",
            "PYTHONPATH": f"Python 路径: {self.repo_root}"
        }
        
        for var, description in env_vars.items():
            current_value = os.getenv(var)
            if current_value:
                if var == "FEISHU_WEBHOOK":
                    # 隐藏 webhook URL 的敏感部分
                    masked_value = current_value[:50] + "..." if len(current_value) > 50 else current_value
                    print(f"  ✅ {var}: {masked_value}")
                else:
                    print(f"  ✅ {var}: 已设置")
            else:
                print(f"  ❌ {var}: 未设置")
                print(f"     {description}")
                if var == "PYTHONPATH":
                    print(f"     export {var}=\"{self.repo_root}:$PYTHONPATH\"")
                elif var == "FEISHU_WEBHOOK":
                    print(f"     export {var}=\"https://open.larksuite.com/open-apis/bot/v2/hook/YOUR_TOKEN\"")
                else:
                    print(f"     export {var}=\"your_api_key_here\"")
                print()
        
        # 创建环境变量模板文件
        env_template_path = self.config_templates_dir / "env.example"
        if env_template_path.exists():
            print(f"\\n💡 提示: 可以参考环境变量模板文件: {env_template_path}")
            print("     复制并修改为实际的环境变量文件")
    
    def test_components(self) -> Dict[str, bool]:
        """测试各个组件"""
        print("\\n🧪 测试组件...")
        
        test_results = {
            "email_tool": False,
            "ai_filter": False,
            "notification": False,
            "monitor": False
        }
        
        # 测试邮件工具
        try:
            result = subprocess.run(
                [sys.executable, str(self.scripts_dir / "call_email_tool.py"), "list_accounts"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                test_results["email_tool"] = True
                print("  ✅ 邮件工具: 正常")
            else:
                print(f"  ❌ 邮件工具: 失败 - {result.stderr}")
        except Exception as e:
            print(f"  ❌ 邮件工具: 异常 - {e}")
        
        # 测试 AI 过滤（如果有 API 密钥）
        if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
            try:
                test_email = json.dumps([{
                    "id": "test_123",
                    "subject": "Test Email",
                    "from": "test@example.com",
                    "date": "2024-01-15",
                    "body_preview": "This is a test email"
                }])
                
                result = subprocess.run(
                    [sys.executable, str(self.scripts_dir / "ai_email_filter.py"), test_email],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    test_results["ai_filter"] = True
                    print("  ✅ AI 过滤: 正常")
                else:
                    print(f"  ❌ AI 过滤: 失败 - {result.stderr}")
            except Exception as e:
                print(f"  ❌ AI 过滤: 异常 - {e}")
        else:
            print("  ⚠️  AI 过滤: 跳过 (缺少 API 密钥)")
        
        # 测试通知服务
        try:
            result = subprocess.run(
                [sys.executable, str(self.scripts_dir / "notification_service.py"), "stats"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                test_results["notification"] = True
                print("  ✅ 通知服务: 正常")
            else:
                print(f"  ❌ 通知服务: 失败 - {result.stderr}")
        except Exception as e:
            print(f"  ❌ 通知服务: 异常 - {e}")
        
        # 测试监控器
        try:
            result = subprocess.run(
                [sys.executable, str(self.scripts_dir / "email_monitor.py"), "status"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                test_results["monitor"] = True
                print("  ✅ 邮件监控: 正常")
            else:
                print(f"  ❌ 邮件监控: 失败 - {result.stderr}")
        except Exception as e:
            print(f"  ❌ 邮件监控: 异常 - {e}")
        
        return test_results
    
    def generate_n8n_instructions(self) -> None:
        """生成 n8n 配置说明"""
        print("\\n📋 n8n 配置说明:")
        print()
        print("1. 导入工作流:")
        print(f"   - 文件路径: {self.n8n_dir / 'email_monitoring_workflow.json'}")
        print("   - 在 n8n 界面中选择 'Import from file'")
        print()
        print("2. 修改脚本路径:")
        print("   - 编辑 '邮件监控' 节点")
        print(f"   - 命令: python {self.scripts_dir / 'email_monitor.py'} run")
        print()
        print("3. 配置 Webhook URL:")
        print("   - 编辑通知节点中的 webhook URL")
        print("   - 钉钉: https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN")
        print("   - 飞书: https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN")
        print()
        print("4. 测试工作流:")
        print("   - 点击 'Test workflow' 按钮")
        print("   - 手动触发定时器节点")
        print()
    
    def run_setup(self) -> bool:
        """运行完整设置流程"""
        print("🚀 开始设置 n8n 邮件监控系统\\n")
        
        # 1. 检查依赖
        deps = self.check_dependencies()
        missing_deps = [k for k, v in deps.items() if not v]
        
        if missing_deps:
            print(f"\\n⚠️  发现缺失依赖: {', '.join(missing_deps)}")
            
            # 尝试安装 Python 包
            python_deps = [d for d in missing_deps if d in ["openai", "anthropic", "requests"]]
            if python_deps:
                if input("\\n是否尝试自动安装 Python 依赖? (y/n): ").lower() == 'y':
                    if not self.install_dependencies():
                        print("❌ 依赖安装失败，请手动安装")
                        return False
            
            # 提醒安装其他依赖
            other_deps = [d for d in missing_deps if d not in python_deps]
            if other_deps:
                print(f"\\n请手动安装以下依赖: {', '.join(other_deps)}")
                if "n8n" in other_deps:
                    print("  安装 n8n: npm install -g n8n")
                if "uv" in other_deps:
                    print("  安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
        
        # 2. 创建配置文件
        if not self.create_config_files():
            print("❌ 配置文件创建失败")
            return False
        
        # 3. 环境变量设置
        self.setup_environment_variables()
        
        # 4. 测试组件
        test_results = self.test_components()
        failed_tests = [k for k, v in test_results.items() if not v]
        
        if failed_tests:
            print(f"\\n⚠️  部分组件测试失败: {', '.join(failed_tests)}")
            print("请检查配置和依赖后重新测试")
        
        # 5. 生成 n8n 配置说明
        self.generate_n8n_instructions()
        
        # 6. 总结
        print("\\n✅ 设置完成!")
        print("\\n📚 下一步:")
        print("1. 配置邮件账户 (accounts.json)")
        print("2. 设置 API 密钥环境变量")
        print("3. 配置 webhook URL")
        print("4. 导入 n8n 工作流")
        print("5. 测试完整流程")
        
        return True


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("n8n 邮件监控系统设置脚本")
        print()
        print("用法: python setup_n8n_monitoring.py [选项]")
        print()
        print("选项:")
        print("  -h, --help     显示帮助信息")
        print("  --check-only   仅检查依赖，不进行设置")
        print("  --test-only    仅运行测试")
        print()
        return
    
    setup = N8NMonitoringSetup()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--check-only":
        setup.check_dependencies()
        return
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test-only":
        setup.test_components()
        return
    
    try:
        success = setup.run_setup()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\\n\\n⚠️  设置被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\\n❌ 设置失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
