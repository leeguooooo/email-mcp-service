"""
时区处理工具
"""
import logging
from datetime import datetime
from typing import Optional, Dict
import pytz

logger = logging.getLogger(__name__)

def get_local_timezone():
    """
    获取本地时区
    
    Returns:
        pytz.timezone: 本地时区对象
    """
    try:
        # 方法1: 使用tzlocal
        import tzlocal
        return tzlocal.get_localzone()
    except ImportError:
        logger.debug("tzlocal not available, trying alternative methods")
    except Exception as e:
        logger.debug(f"tzlocal failed: {e}")
    
    try:
        # 方法2: 从系统时间获取
        import time
        import os
        
        # 获取系统时区名称
        if hasattr(time, 'tzname'):
            tz_name = time.tzname[0]
            if tz_name and tz_name != 'UTC':
                try:
                    return pytz.timezone(tz_name)
                except:
                    pass
        
        # 方法3: 从环境变量获取
        tz_env = os.environ.get('TZ')
        if tz_env:
            try:
                return pytz.timezone(tz_env)
            except:
                pass
        
        # 方法4: 通过时间偏移推断
        import time
        if time.daylight:
            offset_seconds = -time.altzone
        else:
            offset_seconds = -time.timezone
        
        offset_hours = offset_seconds / 3600
        
        # 常见时区映射
        timezone_map = {
            -8: 'US/Pacific',      # PST/PDT
            -7: 'US/Mountain',     # MST/MDT
            -6: 'US/Central',      # CST/CDT
            -5: 'US/Eastern',      # EST/EDT
            0: 'UTC',
            1: 'Europe/London',    # GMT/BST
            2: 'Europe/Paris',     # CET/CEST
            3: 'Europe/Moscow',    # MSK
            8: 'Asia/Shanghai',    # CST (China)
            9: 'Asia/Tokyo',       # JST
            10: 'Australia/Sydney', # AEST/AEDT
        }
        
        if offset_hours in timezone_map:
            try:
                return pytz.timezone(timezone_map[offset_hours])
            except:
                pass
    
    except Exception as e:
        logger.debug(f"Failed to detect timezone: {e}")
    
    # 最后返回UTC
    logger.info("Could not detect local timezone, using UTC")
    return pytz.UTC

def format_timestamp(timestamp: Optional[str], 
                    format_str: str = '%Y-%m-%d %H:%M:%S',
                    show_timezone: bool = True) -> str:
    """
    格式化时间戳为本地时间
    
    Args:
        timestamp: ISO格式的时间戳
        format_str: 输出格式
        show_timezone: 是否显示时区
        
    Returns:
        str: 格式化的本地时间字符串
    """
    if not timestamp:
        return "从未"
    
    try:
        # 获取本地时区
        local_tz = get_local_timezone()
        
        # 解析时间戳
        # SQLite的CURRENT_TIMESTAMP返回的格式可能是 "2025-06-20 07:56:09"
        if 'T' not in timestamp:
            # 假设是UTC时间
            timestamp = timestamp.replace(' ', 'T') + '+00:00'
        
        # 处理各种可能的格式
        timestamp = timestamp.replace('Z', '+00:00')
        
        # 解析为datetime对象
        dt = datetime.fromisoformat(timestamp)
        
        # 确保有时区信息
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        
        # 转换为本地时间
        local_dt = dt.astimezone(local_tz)
        
        # 格式化
        if show_timezone and local_tz != pytz.UTC:
            # 获取时区缩写
            tz_name = local_dt.strftime('%Z')
            if tz_name:
                format_str += f' {tz_name}'
        
        return local_dt.strftime(format_str)
        
    except Exception as e:
        logger.error(f"Failed to format timestamp {timestamp}: {e}")
        # 返回原始时间戳的简单格式
        try:
            if 'T' in str(timestamp):
                return timestamp.split('T')[0] + ' ' + timestamp.split('T')[1].split('+')[0]
            else:
                return str(timestamp)
        except:
            return str(timestamp)

def get_timezone_info() -> Dict[str, str]:
    """
    获取当前时区信息
    
    Returns:
        dict: 包含时区名称、偏移等信息
    """
    local_tz = get_local_timezone()
    now = datetime.now(local_tz)
    
    return {
        'timezone': str(local_tz),
        'timezone_abbr': now.strftime('%Z'),
        'utc_offset': now.strftime('%z'),
        'current_time': now.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'is_dst': bool(now.dst())
    }