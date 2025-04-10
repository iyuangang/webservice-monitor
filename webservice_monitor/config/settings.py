"""
默认应用设置
"""

import os
import tempfile

# 数据库设置
DB_PATH = os.path.join(
    os.path.expanduser("~"), ".webservice_monitor", "data", "webservice_monitor.db"
)

# 日志设置
LOG_DIR = os.path.join(os.path.expanduser("~"), ".webservice_monitor", "logs")
LOG_LEVEL = "INFO"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# 报告设置
REPORT_DIR = os.path.join(os.path.expanduser("~"), ".webservice_monitor", "reports")

# 监控设置
MAX_WORKERS = 10
DATA_RETENTION_DAYS = 30

# 临时文件夹 (用于图表生成等)
TEMP_DIR = tempfile.gettempdir()
