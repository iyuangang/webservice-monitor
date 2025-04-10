"""
数据库操作
"""

import os
import sqlite3
import logging
import datetime
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Tuple

import pandas as pd

from webservice_monitor.db.models import (
    Configuration,
    CallDetail,
    MinuteStats,
    Alert,
    AlertType,
)
from webservice_monitor.utils.config import get_setting

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器"""
    db_path = get_setting("DB_PATH")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """初始化数据库结构"""
    db_path = get_setting("DB_PATH")
    db_dir = os.path.dirname(db_path)

    # 确保数据库目录存在
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)

    with get_connection() as conn:
        cursor = conn.cursor()

        # 创建配置表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            method TEXT NOT NULL,
            headers TEXT,
            payload TEXT,
            call_interval INTEGER DEFAULT 5,
            calls_per_batch INTEGER DEFAULT 5,
            timeout INTEGER DEFAULT 10,
            alert_threshold REAL DEFAULT 2.0,
            is_active INTEGER DEFAULT 1,
            monitoring_hours TEXT DEFAULT '0-23',
            created_at TEXT,
            updated_at TEXT
        )
        """)

        # 创建调用详情表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS call_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            response_time REAL,
            status_code INTEGER,
            error_message TEXT,
            config_id INTEGER,
            FOREIGN KEY(config_id) REFERENCES configurations(id)
        )
        """)

        # 创建统计数据表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS minute_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT,
            end_time TEXT,
            avg_response_time REAL,
            max_response_time REAL,
            min_response_time REAL,
            call_count INTEGER,
            success_count INTEGER,
            config_id INTEGER,
            FOREIGN KEY(config_id) REFERENCES configurations(id)
        )
        """)

        # 创建告警表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER,
            timestamp TEXT,
            type TEXT,
            message TEXT,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT,
            FOREIGN KEY(config_id) REFERENCES configurations(id)
        )
        """)

        # 创建索引
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_call_details_timestamp ON call_details(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_call_details_config_id ON call_details(config_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_minute_stats_start_time ON minute_stats(start_time)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_minute_stats_config_id ON minute_stats(config_id)"
        )

        conn.commit()

    logger.info("数据库初始化完成")


# 配置相关操作
def save_configuration(config: Configuration) -> Tuple[int, str]:
    """保存配置到数据库"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 检查是否已存在
        if config.id:
            cursor.execute("SELECT id FROM configurations WHERE id = ?", (config.id,))
        else:
            cursor.execute(
                "SELECT id FROM configurations WHERE name = ?", (config.name,)
            )

        existing = cursor.fetchone()
        action = "更新" if existing else "创建"

        if existing:
            # 更新
            cursor.execute(
                """UPDATE configurations 
                SET url = ?, method = ?, headers = ?, payload = ?, 
                    call_interval = ?, calls_per_batch = ?, timeout = ?,
                    alert_threshold = ?, monitoring_hours = ?, 
                    is_active = ?, updated_at = ?
                WHERE id = ?""",
                (
                    config.url,
                    config.method,
                    config.headers_json,
                    config.payload,
                    config.call_interval,
                    config.calls_per_batch,
                    config.timeout,
                    config.alert_threshold,
                    config.monitoring_hours,
                    1 if config.is_active else 0,
                    config.updated_at,
                    existing["id"],
                ),
            )
            config_id = existing["id"]
        else:
            # 创建
            cursor.execute(
                """INSERT INTO configurations
                (name, url, method, headers, payload, 
                call_interval, calls_per_batch, timeout, 
                alert_threshold, monitoring_hours, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    config.name,
                    config.url,
                    config.method,
                    config.headers_json,
                    config.payload,
                    config.call_interval,
                    config.calls_per_batch,
                    config.timeout,
                    config.alert_threshold,
                    config.monitoring_hours,
                    1 if config.is_active else 0,
                    config.created_at,
                    config.updated_at,
                ),
            )
            config_id = cursor.lastrowid

        conn.commit()
        return config_id, action


def get_configuration(
    config_id: int = None, name: str = None
) -> Optional[Configuration]:
    """获取配置"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if config_id:
            cursor.execute("SELECT * FROM configurations WHERE id = ?", (config_id,))
        elif name:
            cursor.execute("SELECT * FROM configurations WHERE name = ?", (name,))
        else:
            raise ValueError("Must provide either config_id or name")

        row = cursor.fetchone()
        return Configuration.from_row(row) if row else None


def get_all_configurations(active_only: bool = False) -> List[Configuration]:
    """获取所有配置"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if active_only:
            cursor.execute(
                "SELECT * FROM configurations WHERE is_active = 1 ORDER BY name"
            )
        else:
            cursor.execute("SELECT * FROM configurations ORDER BY name")

        rows = cursor.fetchall()
        return [Configuration.from_row(row) for row in rows]


def delete_configuration(config_id: int = None, name: str = None) -> bool:
    """删除配置"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if config_id:
            cursor.execute("DELETE FROM configurations WHERE id = ?", (config_id,))
        elif name:
            cursor.execute("DELETE FROM configurations WHERE name = ?", (name,))
        else:
            raise ValueError("Must provide either config_id or name")

        success = cursor.rowcount > 0
        conn.commit()
        return success


def toggle_configuration(
    config_id: int = None, name: str = None, active: bool = True
) -> bool:
    """启用/禁用配置"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if config_id:
            cursor.execute(
                "UPDATE configurations SET is_active = ? WHERE id = ?",
                (1 if active else 0, config_id),
            )
        elif name:
            cursor.execute(
                "UPDATE configurations SET is_active = ? WHERE name = ?",
                (1 if active else 0, name),
            )
        else:
            raise ValueError("Must provide either config_id or name")

        success = cursor.rowcount > 0
        conn.commit()
        return success


# 调用详情和统计相关操作
def save_call_detail(call_detail: CallDetail) -> int:
    """保存调用详情"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO call_details 
            (timestamp, response_time, status_code, error_message, config_id)
            VALUES (?, ?, ?, ?, ?)""",
            (
                call_detail.timestamp,
                call_detail.response_time,
                call_detail.status_code,
                call_detail.error_message,
                call_detail.config_id,
            ),
        )

        conn.commit()
        return cursor.lastrowid


def save_minute_stats(stats: MinuteStats) -> int:
    """保存分钟统计数据"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO minute_stats 
            (start_time, end_time, avg_response_time, max_response_time, 
            min_response_time, call_count, success_count, config_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                stats.start_time,
                stats.end_time,
                stats.avg_response_time,
                stats.max_response_time,
                stats.min_response_time,
                stats.call_count,
                stats.success_count,
                stats.config_id,
            ),
        )

        conn.commit()
        return cursor.lastrowid


def create_alert(config_id: int, alert_type: AlertType, message: str) -> int:
    """创建告警"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO alerts 
            (config_id, timestamp, type, message)
            VALUES (?, ?, ?, ?)""",
            (config_id, datetime.datetime.now().isoformat(), alert_type.value, message),
        )

        conn.commit()
        return cursor.lastrowid


def get_active_alerts(config_id: int = None) -> List[Alert]:
    """获取活跃告警"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if config_id:
            cursor.execute(
                """SELECT a.*, c.name as config_name
                FROM alerts a
                JOIN configurations c ON a.config_id = c.id
                WHERE a.resolved = 0 AND a.config_id = ?
                ORDER BY a.timestamp DESC""",
                (config_id,),
            )
        else:
            cursor.execute(
                """SELECT a.*, c.name as config_name
                FROM alerts a
                JOIN configurations c ON a.config_id = c.id
                WHERE a.resolved = 0
                ORDER BY a.timestamp DESC"""
            )

        rows = cursor.fetchall()
        return [
            Alert(
                id=row["id"],
                config_id=row["config_id"],
                timestamp=row["timestamp"],
                type=AlertType(row["type"]),
                message=row["message"],
                resolved=bool(row["resolved"]),
                resolved_at=row["resolved_at"],
                config_name=row["config_name"],
            )
            for row in rows
        ]


def resolve_alert(alert_id: int) -> bool:
    """解决告警"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """UPDATE alerts 
            SET resolved = 1, resolved_at = ? 
            WHERE id = ?""",
            (datetime.datetime.now().isoformat(), alert_id),
        )

        success = cursor.rowcount > 0
        conn.commit()
        return success


def cleanup_old_data(days_to_keep: int = 30) -> Tuple[int, int, int]:
    """清理旧数据"""
    cutoff_date = (
        datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
    ).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM call_details WHERE timestamp < ?", (cutoff_date,))
        call_details_count = cursor.rowcount

        cursor.execute("DELETE FROM minute_stats WHERE start_time < ?", (cutoff_date,))
        minute_stats_count = cursor.rowcount

        cursor.execute(
            "DELETE FROM alerts WHERE resolved = 1 AND timestamp < ?", (cutoff_date,)
        )
        alerts_count = cursor.rowcount

        conn.commit()

    return call_details_count, minute_stats_count, alerts_count


def get_stats_for_report(date, config_id=None):
    """获取生成报告所需的统计数据"""
    with get_connection() as conn:
        query = "SELECT * FROM minute_stats WHERE date(start_time) = ?"
        params = [date.isoformat()]

        if config_id:
            query += " AND config_id = ?"
            params.append(config_id)

        return pd.read_sql_query(query, conn, params=params)
