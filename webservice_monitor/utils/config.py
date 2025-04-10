"""
配置管理
"""

import os
import json
import logging
from typing import Any, Dict, Optional

# 默认配置
DEFAULT_CONFIG = {
    "DB_PATH": "data/webservice_monitor.db",
    "LOG_DIR": "logs",
    "REPORT_DIR": "reports",
    "LOG_LEVEL": "INFO",
    "MAX_LOG_SIZE": 10 * 1024 * 1024,  # 10MB
    "LOG_BACKUP_COUNT": 5,
    "MAX_WORKERS": 10,
    "DATA_RETENTION_DAYS": 30,
}

# 全局配置对象
_config = DEFAULT_CONFIG.copy()


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """加载配置文件"""
    global _config

    # 如果未指定配置文件，尝试默认路径
    if not config_file:
        default_paths = [
            "config.json",
            os.path.join(os.path.expanduser("~"), ".webservice_monitor", "config.json"),
            "/etc/webservice_monitor/config.json",
        ]

        for path in default_paths:
            if os.path.exists(path):
                config_file = path
                break

    # 如果找到配置文件，则加载
    if config_file and os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                _config.update(file_config)
                logging.info(f"已加载配置文件: {config_file}")
        except Exception as e:
            logging.error(f"加载配置文件 {config_file} 时出错: {str(e)}")
    else:
        logging.warning("未找到配置文件，使用默认配置")

    # 检查环境变量
    for key in DEFAULT_CONFIG:
        env_key = f"WEBSVC_MONITOR_{key}"
        if env_key in os.environ:
            env_value = os.environ[env_key]

            # 尝试转换为原始类型
            original_type = type(DEFAULT_CONFIG[key])
            try:
                if original_type == bool:
                    _config[key] = env_value.lower() in ("true", "yes", "1", "y")
                elif original_type == int:
                    _config[key] = int(env_value)
                elif original_type == float:
                    _config[key] = float(env_value)
                else:
                    _config[key] = env_value

                logging.debug(f"从环境变量加载配置: {key}={_config[key]}")
            except (ValueError, TypeError):
                _config[key] = env_value
                logging.warning(
                    f"无法将环境变量 {env_key} 转换为 {original_type.__name__} 类型"
                )

    # 创建必要的目录
    for dir_key in ["LOG_DIR", "REPORT_DIR"]:
        dir_path = _config.get(dir_key)
        if dir_path and not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
                logging.debug(f"已创建目录: {dir_path}")
            except Exception as e:
                logging.error(f"创建目录 {dir_path} 时出错: {str(e)}")

    return _config


def get_setting(key: str, default: Any = None) -> Any:
    """获取配置项"""
    return _config.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """设置配置项"""
    _config[key] = value


# 初始化时加载配置
load_config()
