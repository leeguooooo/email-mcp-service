"""
同步健康监控 - 跟踪同步状态和失败情况
"""
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
import json
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class SyncEvent:
    """同步事件记录"""
    timestamp: datetime
    account_id: str
    sync_type: str  # 'full' or 'incremental'
    status: str  # 'success', 'failed', 'partial'
    emails_synced: int = 0
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class AccountHealthStatus:
    """账户健康状态"""
    account_id: str
    account_email: str
    last_sync_time: Optional[datetime] = None
    last_sync_status: str = 'unknown'  # 'success', 'failed', 'never'
    consecutive_failures: int = 0
    total_syncs: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    total_emails_synced: int = 0
    average_sync_duration: float = 0.0
    last_error: Optional[str] = None
    health_score: float = 100.0  # 0-100
    is_stale: bool = False  # 数据是否过期
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        if self.last_sync_time:
            data['last_sync_time'] = self.last_sync_time.isoformat()
        return data
    
    def calculate_health_score(self, max_stale_hours: int = 24) -> float:
        """
        计算健康分数
        
        考虑因素：
        - 连续失败次数
        - 成功率
        - 数据新鲜度
        """
        score = 100.0
        
        # 连续失败惩罚（每次失败 -15分）
        score -= min(self.consecutive_failures * 15, 60)
        
        # 成功率奖励
        if self.total_syncs > 0:
            success_rate = self.successful_syncs / self.total_syncs
            score = score * success_rate
        
        # 数据新鲜度惩罚
        if self.last_sync_time:
            hours_since_sync = (datetime.now() - self.last_sync_time).total_seconds() / 3600
            if hours_since_sync > max_stale_hours:
                self.is_stale = True
                # 超过24小时没同步，每小时-5分
                score -= min((hours_since_sync - max_stale_hours) * 5, 40)
        else:
            # 从未同步过
            score -= 50
        
        self.health_score = max(0.0, min(100.0, score))
        return self.health_score


class SyncHealthMonitor:
    """同步健康监控器"""
    
    def __init__(self, history_file: Optional[str] = None, 
                 max_history_days: int = 30):
        """
        初始化监控器
        
        Args:
            history_file: 历史记录文件路径
            max_history_days: 保留历史记录天数
        """
        self.history_file = Path(history_file) if history_file else None
        self.max_history_days = max_history_days
        
        # 账户健康状态
        self._account_health: Dict[str, AccountHealthStatus] = {}
        
        # 同步事件历史
        self._sync_history: List[SyncEvent] = []
        
        # 失败统计
        self._failure_stats = defaultdict(lambda: {
            'count': 0,
            'last_occurrence': None,
            'error_types': defaultdict(int)
        })
        
        # 锁
        self._lock = threading.Lock()
        
        # 告警回调
        self._alert_callbacks = []
        
        # 加载历史记录
        if self.history_file and self.history_file.exists():
            self._load_history()
    
    def record_sync_start(self, account_id: str, account_email: str, sync_type: str):
        """记录同步开始"""
        with self._lock:
            if account_id not in self._account_health:
                self._account_health[account_id] = AccountHealthStatus(
                    account_id=account_id,
                    account_email=account_email
                )
    
    def record_sync_result(self, account_id: str, sync_type: str, 
                          status: str, emails_synced: int = 0,
                          error_message: Optional[str] = None,
                          duration_seconds: float = 0.0):
        """
        记录同步结果
        
        Args:
            account_id: 账户ID
            sync_type: 同步类型 ('full' 或 'incremental')
            status: 状态 ('success', 'failed', 'partial')
            emails_synced: 同步的邮件数
            error_message: 错误消息（如果有）
            duration_seconds: 同步耗时
        """
        with self._lock:
            # 创建同步事件
            event = SyncEvent(
                timestamp=datetime.now(),
                account_id=account_id,
                sync_type=sync_type,
                status=status,
                emails_synced=emails_synced,
                error_message=error_message,
                duration_seconds=duration_seconds
            )
            
            self._sync_history.append(event)
            
            # 更新账户健康状态
            if account_id in self._account_health:
                health = self._account_health[account_id]
                
                health.last_sync_time = datetime.now()
                health.last_sync_status = status
                health.total_syncs += 1
                
                if status == 'success':
                    health.successful_syncs += 1
                    health.consecutive_failures = 0
                    health.total_emails_synced += emails_synced
                else:
                    health.failed_syncs += 1
                    health.consecutive_failures += 1
                    health.last_error = error_message
                    
                    # 记录失败统计
                    self._failure_stats[account_id]['count'] += 1
                    self._failure_stats[account_id]['last_occurrence'] = datetime.now()
                    
                    if error_message:
                        # 提取错误类型
                        error_type = self._classify_error(error_message)
                        self._failure_stats[account_id]['error_types'][error_type] += 1
                
                # 更新平均同步时长
                if health.total_syncs > 0:
                    total_duration = (health.average_sync_duration * (health.total_syncs - 1) + 
                                    duration_seconds)
                    health.average_sync_duration = total_duration / health.total_syncs
                
                # 重新计算健康分数
                health.calculate_health_score()
                
                # 触发告警
                self._check_and_alert(health)
        
        # 清理旧历史
        self._cleanup_old_history()
        
        # 保存历史
        if self.history_file:
            self._save_history()
    
    def _classify_error(self, error_message: str) -> str:
        """分类错误类型"""
        error_lower = error_message.lower()
        
        if 'auth' in error_lower or 'login' in error_lower or 'password' in error_lower:
            return 'authentication'
        elif 'timeout' in error_lower or 'timed out' in error_lower:
            return 'timeout'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'network'
        elif 'permission' in error_lower or 'denied' in error_lower:
            return 'permission'
        elif 'limit' in error_lower or 'quota' in error_lower or 'throttle' in error_lower:
            return 'rate_limit'
        else:
            return 'other'
    
    def _check_and_alert(self, health: AccountHealthStatus):
        """检查并触发告警"""
        alerts = []
        
        # 连续失败告警
        if health.consecutive_failures >= 3:
            alerts.append({
                'type': 'consecutive_failures',
                'severity': 'high',
                'account_id': health.account_id,
                'account_email': health.account_email,
                'message': f'账户 {health.account_email} 连续失败 {health.consecutive_failures} 次',
                'last_error': health.last_error
            })
        
        # 健康分数低告警
        if health.health_score < 50:
            alerts.append({
                'type': 'low_health_score',
                'severity': 'medium',
                'account_id': health.account_id,
                'account_email': health.account_email,
                'message': f'账户 {health.account_email} 健康分数过低: {health.health_score:.1f}/100',
                'health_score': health.health_score
            })
        
        # 数据过期告警
        if health.is_stale:
            alerts.append({
                'type': 'stale_data',
                'severity': 'low',
                'account_id': health.account_id,
                'account_email': health.account_email,
                'message': f'账户 {health.account_email} 数据已过期，上次同步: {health.last_sync_time}',
                'last_sync_time': health.last_sync_time.isoformat() if health.last_sync_time else None
            })
        
        # 触发回调
        for alert in alerts:
            self._notify_alert(alert)
    
    def _notify_alert(self, alert: Dict[str, Any]):
        """通知告警"""
        logger.warning(f"⚠️ 同步告警: {alert['message']}")
        
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def add_alert_callback(self, callback):
        """添加告警回调"""
        self._alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback):
        """移除告警回调"""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)
    
    def get_account_health(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """获取账户健康状态"""
        with self._lock:
            if account_id:
                health = self._account_health.get(account_id)
                return health.to_dict() if health else None
            else:
                return {
                    account_id: health.to_dict()
                    for account_id, health in self._account_health.items()
                }
    
    def get_sync_history(self, account_id: Optional[str] = None, 
                        hours: int = 24) -> List[Dict[str, Any]]:
        """获取同步历史"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            history = [
                event.to_dict()
                for event in self._sync_history
                if event.timestamp >= cutoff and 
                   (account_id is None or event.account_id == account_id)
            ]
        
        return sorted(history, key=lambda x: x['timestamp'], reverse=True)
    
    def get_failure_stats(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """获取失败统计"""
        with self._lock:
            if account_id:
                stats = self._failure_stats.get(account_id, {})
                if stats and stats.get('last_occurrence'):
                    stats = stats.copy()
                    stats['last_occurrence'] = stats['last_occurrence'].isoformat()
                return stats
            else:
                result = {}
                for acc_id, stats in self._failure_stats.items():
                    stats_copy = stats.copy()
                    if stats_copy.get('last_occurrence'):
                        stats_copy['last_occurrence'] = stats_copy['last_occurrence'].isoformat()
                    result[acc_id] = stats_copy
                return result
    
    def get_overall_health(self) -> Dict[str, Any]:
        """获取整体健康状况"""
        with self._lock:
            if not self._account_health:
                return {
                    'status': 'no_accounts',
                    'message': '没有配置账户'
                }
            
            total_accounts = len(self._account_health)
            healthy_accounts = sum(
                1 for h in self._account_health.values()
                if h.health_score >= 70 and h.consecutive_failures == 0
            )
            warning_accounts = sum(
                1 for h in self._account_health.values()
                if 50 <= h.health_score < 70 or h.consecutive_failures == 1
            )
            critical_accounts = sum(
                1 for h in self._account_health.values()
                if h.health_score < 50 or h.consecutive_failures >= 2
            )
            
            average_health = sum(
                h.health_score for h in self._account_health.values()
            ) / total_accounts
            
            total_syncs = sum(h.total_syncs for h in self._account_health.values())
            total_failures = sum(h.failed_syncs for h in self._account_health.values())
            
            return {
                'status': 'healthy' if critical_accounts == 0 else 'degraded',
                'total_accounts': total_accounts,
                'healthy_accounts': healthy_accounts,
                'warning_accounts': warning_accounts,
                'critical_accounts': critical_accounts,
                'average_health_score': round(average_health, 2),
                'total_syncs': total_syncs,
                'total_failures': total_failures,
                'success_rate': round((total_syncs - total_failures) / total_syncs * 100, 2) if total_syncs > 0 else 0,
                'timestamp': datetime.now().isoformat()
            }
    
    def _cleanup_old_history(self):
        """清理旧历史记录"""
        cutoff = datetime.now() - timedelta(days=self.max_history_days)
        
        with self._lock:
            self._sync_history = [
                event for event in self._sync_history
                if event.timestamp >= cutoff
            ]
    
    def _save_history(self):
        """保存历史到文件"""
        if not self.history_file:
            return
        
        try:
            with self._lock:
                data = {
                    'account_health': {
                        account_id: health.to_dict()
                        for account_id, health in self._account_health.items()
                    },
                    'sync_history': [event.to_dict() for event in self._sync_history[-1000:]],  # 只保存最近1000条
                    'failure_stats': dict(self._failure_stats)
                }
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                
        except Exception as e:
            logger.error(f"Failed to save sync history: {e}")
    
    def _load_history(self):
        """从文件加载历史"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 加载账户健康状态
            for account_id, health_data in data.get('account_health', {}).items():
                if health_data.get('last_sync_time'):
                    health_data['last_sync_time'] = datetime.fromisoformat(health_data['last_sync_time'])
                self._account_health[account_id] = AccountHealthStatus(**health_data)
            
            # 加载同步历史（最近的部分）
            for event_data in data.get('sync_history', [])[:1000]:
                event_data['timestamp'] = datetime.fromisoformat(event_data['timestamp'])
                self._sync_history.append(SyncEvent(**event_data))
            
            logger.info(f"Loaded sync history from {self.history_file}")
            
        except Exception as e:
            logger.warning(f"Failed to load sync history: {e}")
    
    def reset_account(self, account_id: str):
        """重置账户统计"""
        with self._lock:
            if account_id in self._account_health:
                health = self._account_health[account_id]
                # 保留账户信息，重置统计
                health.consecutive_failures = 0
                health.last_error = None
                health.calculate_health_score()
                logger.info(f"Reset health stats for account {account_id}")


# 全局健康监控实例
_monitor_instance: Optional[SyncHealthMonitor] = None

def get_health_monitor() -> SyncHealthMonitor:
    """获取全局健康监控实例"""
    global _monitor_instance
    if _monitor_instance is None:
        from ..config.paths import SYNC_HEALTH_HISTORY_JSON
        _monitor_instance = SyncHealthMonitor(
            history_file=SYNC_HEALTH_HISTORY_JSON,
            max_history_days=30
        )
    return _monitor_instance

