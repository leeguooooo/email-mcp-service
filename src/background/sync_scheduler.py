"""
后台定时同步调度器
"""
import logging
import threading
import time
import schedule
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import json
from pathlib import Path

from operations.email_sync import EmailSyncManager

logger = logging.getLogger(__name__)

class SyncScheduler:
    """邮件同步调度器"""
    
    def __init__(self, config_file: str = "sync_config.json"):
        """初始化调度器"""
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.sync_manager = EmailSyncManager(self.config.get('db_path', 'email_sync.db'))
        self.scheduler_thread = None
        self.running = False
        self.stop_event = threading.Event()
        self.last_sync_times = {}
        self.sync_callbacks = []
        
    def _load_config(self) -> Dict[str, Any]:
        """加载同步配置"""
        default_config = {
            "enabled": True,
            "sync_interval_minutes": 15,  # 默认15分钟同步一次
            "full_sync_interval_hours": 24,  # 24小时做一次完全同步
            "quiet_hours": {  # 静默时间段，不进行同步
                "enabled": False,
                "start": "23:00",
                "end": "06:00"
            },
            "retry_settings": {
                "max_retries": 3,
                "retry_delay_minutes": 5
            },
            "performance": {
                "max_concurrent_accounts": 2,
                "batch_size": 50,
                "request_delay_ms": 100
            },
            "auto_cleanup": {
                "enabled": True,
                "days_to_keep": 90,  # 保留90天的邮件
                "cleanup_interval_hours": 24
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置
                default_config.update(config)
                return default_config
            except Exception as e:
                logger.error(f"Failed to load config: {e}, using defaults")
        
        # 保存默认配置
        self._save_config(default_config)
        return default_config
    
    def _save_config(self, config: Dict[str, Any]):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def start_scheduler(self):
        """启动调度器"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        if not self.config.get('enabled', True):
            logger.info("Sync scheduler is disabled in config")
            return
        
        logger.info("Starting email sync scheduler")
        self.running = True
        self.stop_event.clear()
        
        # 设置定时任务
        self._setup_schedules()
        
        # 启动调度线程
        self.scheduler_thread = threading.Thread(target=self._scheduler_worker, daemon=True)
        self.scheduler_thread.start()
        
        logger.info(f"Scheduler started with {len(schedule.jobs)} jobs")
    
    def stop_scheduler(self):
        """停止调度器"""
        if not self.running:
            return
        
        logger.info("Stopping email sync scheduler")
        self.running = False
        self.stop_event.set()
        
        # 清除所有计划任务
        schedule.clear()
        
        # 等待线程结束
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Scheduler stopped")
    
    def _setup_schedules(self):
        """设置定时任务"""
        interval_minutes = self.config.get('sync_interval_minutes', 15)
        full_sync_hours = self.config.get('full_sync_interval_hours', 24)
        
        # 增量同步任务
        schedule.every(interval_minutes).minutes.do(self._scheduled_sync, full_sync=False)
        
        # 完全同步任务（每天凌晨2点）
        schedule.every().day.at("02:00").do(self._scheduled_sync, full_sync=True)
        
        # 清理任务（如果启用）
        if self.config.get('auto_cleanup', {}).get('enabled', False):
            cleanup_hours = self.config.get('auto_cleanup', {}).get('cleanup_interval_hours', 24)
            schedule.every(cleanup_hours).hours.do(self._cleanup_old_emails)
        
        logger.info(f"Scheduled incremental sync every {interval_minutes} minutes")
        logger.info(f"Scheduled full sync daily at 02:00")
    
    def _scheduler_worker(self):
        """调度器工作线程"""
        while self.running and not self.stop_event.is_set():
            try:
                schedule.run_pending()
                time.sleep(30)  # 每30秒检查一次
            except Exception as e:
                logger.error(f"Scheduler worker error: {e}")
                time.sleep(60)  # 出错后等待1分钟再继续
    
    def _scheduled_sync(self, full_sync: bool = False):
        """执行定时同步"""
        if not self._should_sync_now():
            logger.info("Skipping sync due to quiet hours")
            return
        
        sync_type = "full" if full_sync else "incremental"
        logger.info(f"Starting scheduled {sync_type} sync")
        
        try:
            # 执行同步
            result = self._sync_with_retry(full_sync)
            
            # 记录同步时间
            self.last_sync_times[sync_type] = datetime.now()
            
            # 通知回调
            self._notify_callbacks('sync_completed', {
                'type': sync_type,
                'result': result,
                'timestamp': datetime.now()
            })
            
            logger.info(f"Scheduled {sync_type} sync completed: "
                       f"{result.get('emails_added', 0)} added, "
                       f"{result.get('emails_updated', 0)} updated")
            
        except Exception as e:
            logger.error(f"Scheduled {sync_type} sync failed: {e}")
            self._notify_callbacks('sync_failed', {
                'type': sync_type,
                'error': str(e),
                'timestamp': datetime.now()
            })
    
    def _sync_with_retry(self, full_sync: bool) -> Dict[str, Any]:
        """带重试的同步"""
        max_retries = self.config.get('retry_settings', {}).get('max_retries', 3)
        retry_delay = self.config.get('retry_settings', {}).get('retry_delay_minutes', 5)
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Sync retry attempt {attempt}/{max_retries}")
                    time.sleep(retry_delay * 60)  # 转换为秒
                
                max_workers = self.config.get('performance', {}).get('max_concurrent_accounts', 2)
                result = self.sync_manager.sync_all_accounts(
                    full_sync=full_sync,
                    max_workers=max_workers
                )
                
                if result.get('success'):
                    return result
                else:
                    last_error = result.get('error', 'Unknown sync error')
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Sync attempt {attempt + 1} failed: {e}")
        
        raise Exception(f"Sync failed after {max_retries} retries: {last_error}")
    
    def _should_sync_now(self) -> bool:
        """检查当前是否应该执行同步"""
        quiet_hours = self.config.get('quiet_hours', {})
        if not quiet_hours.get('enabled', False):
            return True
        
        now = datetime.now().time()
        start_time = datetime.strptime(quiet_hours.get('start', '23:00'), '%H:%M').time()
        end_time = datetime.strptime(quiet_hours.get('end', '06:00'), '%H:%M').time()
        
        # 处理跨午夜的情况
        if start_time <= end_time:
            # 同一天内的时间段
            return not (start_time <= now <= end_time)
        else:
            # 跨午夜的时间段
            return not (now >= start_time or now <= end_time)
    
    def _cleanup_old_emails(self):
        """清理旧邮件"""
        if not self.config.get('auto_cleanup', {}).get('enabled', False):
            return
        
        days_to_keep = self.config.get('auto_cleanup', {}).get('days_to_keep', 90)
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        logger.info(f"Starting cleanup of emails older than {days_to_keep} days")
        
        try:
            # 软删除旧邮件
            cursor = self.sync_manager.db.conn.execute("""
                UPDATE emails SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE date_sent < ? AND is_deleted = FALSE
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            self.sync_manager.db.conn.commit()
            
            logger.info(f"Cleanup completed: {deleted_count} emails marked as deleted")
            
            # 通知回调
            self._notify_callbacks('cleanup_completed', {
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date,
                'timestamp': datetime.now()
            })
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            self._notify_callbacks('cleanup_failed', {
                'error': str(e),
                'timestamp': datetime.now()
            })
    
    def force_sync(self, full_sync: bool = False) -> Dict[str, Any]:
        """强制立即同步"""
        logger.info(f"Force sync requested (full_sync={full_sync})")
        
        try:
            result = self._sync_with_retry(full_sync)
            
            # 更新最后同步时间
            sync_type = "full" if full_sync else "incremental"
            self.last_sync_times[sync_type] = datetime.now()
            
            return result
            
        except Exception as e:
            logger.error(f"Force sync failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        status = {
            'scheduler_running': self.running,
            'config': self.config,
            'last_sync_times': {
                k: v.isoformat() if isinstance(v, datetime) else v
                for k, v in self.last_sync_times.items()
            },
            'next_jobs': []
        }
        
        # 获取下次执行时间
        for job in schedule.jobs:
            status['next_jobs'].append({
                'job': str(job.job_func),
                'next_run': job.next_run.isoformat() if job.next_run else None,
                'interval': str(job.interval)
            })
        
        # 获取数据库状态
        db_status = self.sync_manager.get_sync_status()
        status.update(db_status)
        
        return status
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            # 验证配置
            self._validate_config(new_config)
            
            # 备份当前配置
            old_config = self.config.copy()
            
            # 更新配置
            self.config.update(new_config)
            self._save_config(self.config)
            
            # 如果调度器正在运行，重新设置任务
            if self.running:
                schedule.clear()
                self._setup_schedules()
                logger.info("Scheduler jobs updated with new config")
            
            logger.info("Configuration updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            # 恢复原配置
            self.config = old_config
            return False
    
    def _validate_config(self, config: Dict[str, Any]):
        """验证配置"""
        # 检查必需的数值范围
        if 'sync_interval_minutes' in config:
            interval = config['sync_interval_minutes']
            if not isinstance(interval, int) or interval < 1 or interval > 1440:
                raise ValueError("sync_interval_minutes must be between 1 and 1440")
        
        if 'full_sync_interval_hours' in config:
            interval = config['full_sync_interval_hours']
            if not isinstance(interval, int) or interval < 1 or interval > 168:
                raise ValueError("full_sync_interval_hours must be between 1 and 168")
        
        # 验证时间格式
        quiet_hours = config.get('quiet_hours', {})
        if quiet_hours.get('enabled'):
            for time_key in ['start', 'end']:
                if time_key in quiet_hours:
                    try:
                        datetime.strptime(quiet_hours[time_key], '%H:%M')
                    except ValueError:
                        raise ValueError(f"Invalid time format for quiet_hours.{time_key}, use HH:MM")
    
    def add_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """添加同步事件回调"""
        self.sync_callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """移除同步事件回调"""
        if callback in self.sync_callbacks:
            self.sync_callbacks.remove(callback)
    
    def _notify_callbacks(self, event_type: str, data: Dict[str, Any]):
        """通知所有回调"""
        for callback in self.sync_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def close(self):
        """关闭调度器"""
        self.stop_scheduler()
        if self.sync_manager:
            self.sync_manager.close()


# 全局调度器实例
_scheduler_instance = None

def get_scheduler() -> SyncScheduler:
    """获取全局调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SyncScheduler()
    return _scheduler_instance

def start_background_sync():
    """启动后台同步"""
    scheduler = get_scheduler()
    scheduler.start_scheduler()
    return scheduler

def stop_background_sync():
    """停止后台同步"""
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.stop_scheduler()
        _scheduler_instance = None