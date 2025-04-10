"""
调度管理模块
"""

import time
import logging
import threading
import atexit
from typing import Dict, List, Optional

from webservice_monitor.core.monitor import WebServiceMonitor
from webservice_monitor.db import repository

logger = logging.getLogger(__name__)


class MonitorScheduler:
    """监控调度器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MonitorScheduler, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化调度器"""
        if self._initialized:
            return

        self.monitor = WebServiceMonitor()
        self.status = "stopped"
        self.active_configs_count = 0
        self._initialized = True

        # 注册退出处理器
        atexit.register(self._cleanup)

    def _cleanup(self):
        """程序退出时的清理操作"""
        if self.status == "running":
            logger.info("程序退出，正在停止监控...")
            self.stop_monitoring()

    def start_monitoring(self, config_ids=None):
        """启动监控"""
        with self._lock:
            if self.status == "running":
                return False, "监控已在运行中"

            try:
                success = self.monitor.start(config_ids)
                if success:
                    self.status = "running"
                    self.active_configs_count = len(self.monitor.configurations)
                    return (
                        True,
                        f"监控已启动，正在监控 {self.active_configs_count} 个配置",
                    )
                else:
                    return False, "启动监控失败，可能没有可用配置"
            except Exception as e:
                logger.exception("启动监控时出错")
                return False, f"启动监控时出错: {str(e)}"

    def stop_monitoring(self):
        """停止监控"""
        with self._lock:
            if self.status != "running":
                return False, "监控未运行"

            try:
                success = self.monitor.stop()
                if success:
                    self.status = "stopped"
                    return True, "监控已停止"
                else:
                    return False, "停止监控失败"
            except Exception as e:
                logger.exception("停止监控时出错")
                # 即使出错，也将状态设为stopped以避免状态不一致
                self.status = "stopped"
                return False, f"停止监控时出错: {str(e)}"

    def get_status(self):
        """获取监控状态"""
        with self._lock:
            return {
                "status": self.status,
                "active_configs": self.active_configs_count
                if self.status == "running"
                else 0,
            }

    def reload_configurations(self):
        """重新加载配置"""
        with self._lock:
            if self.status != "running":
                return False, "监控未运行，无需重新加载配置"

            try:
                # 停止当前监控
                self.monitor.stop()

                # 重新启动监控
                success = self.monitor.start()
                if success:
                    self.active_configs_count = len(self.monitor.configurations)
                    return (
                        True,
                        f"配置已重新加载，正在监控 {self.active_configs_count} 个配置",
                    )
                else:
                    self.status = "stopped"
                    return False, "重新加载配置失败，可能没有可用配置"
            except Exception as e:
                logger.exception("重新加载配置时出错")
                self.status = "stopped"
                return False, f"重新加载配置时出错: {str(e)}"
