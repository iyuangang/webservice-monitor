"""
数据验证工具
"""

import re
import json
from urllib.parse import urlparse
from typing import Tuple, Dict, Any, Optional


def validate_url(url: str) -> Tuple[bool, str]:
    """验证URL格式是否有效"""
    if not url:
        return False, "URL不能为空"

    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "URL必须包含协议和域名"

        if result.scheme not in ["http", "https"]:
            return False, "URL协议必须是http或https"

        return True, "URL格式有效"
    except Exception as e:
        return False, f"URL无效: {str(e)}"


def validate_json(json_str: str) -> Tuple[bool, str, Optional[Dict]]:
    """验证JSON字符串是否有效"""
    if not json_str:
        return True, "JSON为空", {}

    try:
        data = json.loads(json_str)
        return True, "JSON格式有效", data
    except json.JSONDecodeError as e:
        return False, f"JSON格式无效: {str(e)}", None


def validate_monitoring_hours(hours_str: str) -> Tuple[bool, str]:
    """验证监控时段格式是否有效"""
    if not hours_str:
        return False, "监控时段不能为空"

    # 单个小时
    if hours_str.isdigit():
        hour = int(hours_str)
        if 0 <= hour <= 23:
            return True, "监控时段有效"
        else:
            return False, "小时必须在0-23之间"

    # 时段范围
    if "-" in hours_str:
        try:
            start, end = map(int, hours_str.split("-"))
            if not (0 <= start <= 23 and 0 <= end <= 23):
                return False, "小时必须在0-23之间"
            return True, "监控时段有效"
        except ValueError:
            return False, "监控时段必须是数字或数字范围"

    return False, "监控时段格式无效，应为单个小时(如'9')或时间范围(如'9-17')"


def validate_alert_threshold(threshold: float) -> Tuple[bool, str]:
    """验证告警阈值是否有效"""
    if threshold <= 0:
        return False, "告警阈值必须大于0"

    if threshold > 60:
        return False, "告警阈值不应超过60秒"

    return True, "告警阈值有效"


def validate_call_interval(interval: int) -> Tuple[bool, str]:
    """验证调用间隔是否有效"""
    if interval < 1:
        return False, "调用间隔必须至少为1秒"

    if interval > 60:
        return False, "调用间隔不应超过60秒"

    return True, "调用间隔有效"
