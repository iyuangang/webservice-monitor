"""
数据模型定义
"""

import json
import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List


class AlertType(Enum):
    """告警类型枚举"""

    AVAILABILITY = "availability"
    PERFORMANCE = "performance"


@dataclass
class Configuration:
    """接口配置数据类"""

    id: Optional[int] = None
    name: str = ""
    url: str = ""
    method: str = "GET"
    headers: Dict = field(default_factory=dict)
    payload: str = ""
    call_interval: int = 5
    calls_per_batch: int = 5
    timeout: int = 10
    alert_threshold: float = 2.0
    is_active: bool = True
    monitoring_hours: str = "0-23"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at

    @property
    def is_post(self):
        """是否是POST请求"""
        return self.method.upper() == "POST"

    @property
    def headers_json(self):
        """获取头信息的JSON字符串"""
        return json.dumps(self.headers)

    @classmethod
    def from_row(cls, row):
        """从数据库行创建配置对象"""
        if not row:
            return None

        config = cls(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            method=row["method"],
            payload=row["payload"],
            call_interval=row["call_interval"],
            calls_per_batch=row["calls_per_batch"],
            timeout=row["timeout"],
            alert_threshold=row["alert_threshold"],
            is_active=bool(row["is_active"]),
            monitoring_hours=row["monitoring_hours"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

        # 解析头信息
        if row["headers"]:
            try:
                config.headers = json.loads(row["headers"])
            except json.JSONDecodeError:
                config.headers = {}

        return config

    @classmethod
    def from_json(cls, json_data, name=None):
        """从JSON数据创建配置对象"""
        config = cls()
        config.name = name if name else json_data.get("name", "")
        config.url = json_data.get("url", "")
        config.method = "POST" if "xml_payload" in json_data else "GET"
        config.headers = json_data.get("headers", {})
        config.payload = json_data.get("xml_payload", "")
        config.call_interval = json_data.get("call_interval", 5)
        config.calls_per_batch = json_data.get("calls_per_batch", 5)
        config.timeout = json_data.get("timeout", 10)
        config.alert_threshold = json_data.get("alert_threshold", 2.0)
        config.monitoring_hours = json_data.get("monitoring_hours", "0-23")

        return config


@dataclass
class CallDetail:
    """调用详情数据类"""

    id: Optional[int] = None
    timestamp: Optional[str] = None
    response_time: float = 0.0
    status_code: int = 0
    error_message: Optional[str] = None
    config_id: Optional[int] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.datetime.now().isoformat()

    @property
    def is_success(self):
        """是否调用成功"""
        return 200 <= self.status_code < 300


@dataclass
class MinuteStats:
    """每分钟统计数据类"""

    id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = 0.0
    call_count: int = 0
    success_count: int = 0
    config_id: Optional[int] = None


@dataclass
class Alert:
    """告警数据类"""

    id: Optional[int] = None
    config_id: Optional[int] = None
    timestamp: Optional[str] = None
    type: AlertType = AlertType.AVAILABILITY
    message: str = ""
    resolved: bool = False
    resolved_at: Optional[str] = None
    config_name: Optional[str] = None  # 非数据库字段，用于显示

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.datetime.now().isoformat()
