"""
输出格式化工具
"""

from webservice_monitor.db.models import Configuration, Alert


def format_config(config: Configuration, verbose: bool = False):
    """格式化配置信息用于表格显示"""
    if verbose:
        return [
            config.id,
            config.name,
            config.url,
            config.method,
            config.call_interval,
            config.calls_per_batch,
            config.timeout,
            config.alert_threshold,
            config.monitoring_hours,
            "活跃" if config.is_active else "禁用",
        ]
    else:
        return [
            config.id,
            config.name,
            config.url,
            "活跃" if config.is_active else "禁用",
        ]


def format_alert(alert: Alert):
    """格式化告警信息用于表格显示"""
    return [
        alert.id,
        alert.timestamp.split("T")[0] + " " + alert.timestamp.split("T")[1][:8],
        alert.config_name,
        "可用性" if alert.type.value == "availability" else "性能",
        alert.message,
    ]
