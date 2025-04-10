"""
日志工具
"""

import os
import logging
import datetime
from logging.handlers import RotatingFileHandler

from webservice_monitor.utils.config import get_setting


def setup_logger():
    """设置日志"""
    # 获取配置
    log_level = getattr(logging, get_setting("LOG_LEVEL", "INFO"))
    log_dir = get_setting("LOG_DIR", "logs")
    max_log_size = get_setting("MAX_LOG_SIZE", 10 * 1024 * 1024)  # 10MB
    backup_count = get_setting("LOG_BACKUP_COUNT", 5)

    # 确保日志目录存在
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 生成日志文件名
    log_file = os.path.join(
        log_dir, f"webservice_monitor_{datetime.datetime.now().strftime('%Y%m%d')}.log"
    )

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 如果已经配置过处理器，则不重复配置
    if not root_logger.handlers:
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)

        # 创建文件处理器
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_log_size, backupCount=backup_count
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        # 添加处理器到根日志记录器
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

    # 设置第三方库的日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    return root_logger
