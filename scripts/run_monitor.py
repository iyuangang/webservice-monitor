#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WebService监控工具运行脚本
作为独立进程运行监控服务
"""

import os
import sys
import time
import signal
import logging
import argparse
import multiprocessing
from pathlib import Path
import json
import datetime

# 确保能找到包
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from webservice_monitor.utils.logger import setup_logger
from webservice_monitor.core.monitor import WebServiceMonitor
from webservice_monitor.utils.config import load_config

# 全局变量
monitor = None
running = True
logger = None


def signal_handler(signum, frame):
    """处理终止信号"""
    global running, monitor, logger

    signal_name = "UNKNOWN"
    for name, value in signal.__dict__.items():
        if isinstance(value, int) and value == signum and name.startswith("SIG"):
            signal_name = name
            break

    logger.info(f"收到信号 {signal_name} ({signum})，准备处理...")

    # SIGHUP信号用于重新加载配置（仅Unix）
    if hasattr(signal, "SIGHUP") and signum == signal.SIGHUP:
        logger.info("处理配置重载请求...")
        try:
            # 保存当前配置ID
            current_configs = list(monitor.configurations.keys()) if monitor else []

            # 重新启动监控
            if monitor:
                logger.info("停止当前监控...")
                monitor.stop()

            logger.info("启动带有更新配置的监控...")
            monitor = WebServiceMonitor()
            success = monitor.start(current_configs)

            if success:
                logger.info(
                    f"配置已重新加载，正在监控 {len(monitor.configurations)} 个配置"
                )
            else:
                logger.error("重新加载配置失败")
        except Exception as e:
            logger.exception(f"重新加载配置时出错: {e}")
    else:
        # 其他信号（如SIGTERM, SIGINT）用于终止程序
        logger.info(f"准备终止程序...")
        running = False


def write_pid_file(pid):
    """写入PID文件"""
    pid_dir = os.path.join(os.path.expanduser("~"), ".webservice_monitor")
    os.makedirs(pid_dir, exist_ok=True)

    pid_file = os.path.join(pid_dir, "monitor.pid")
    with open(pid_file, "w") as f:
        f.write(str(pid))

    return pid_file


def update_status_file(status):
    """更新状态文件"""
    status_dir = os.path.join(os.path.expanduser("~"), ".webservice_monitor")
    os.makedirs(status_dir, exist_ok=True)

    status_file = os.path.join(status_dir, "monitor_status.json")

    # 添加时间戳
    status["last_update"] = datetime.datetime.now().isoformat()

    with open(status_file, "w") as f:
        json.dump(status, f)


def run_monitor(config_file=None, config_ids=None):
    """运行监控服务"""
    global monitor, logger, running

    # 初始化时记录启动时间
    start_time = datetime.datetime.now()

    # 设置日志
    logger = setup_logger()

    # 写入PID
    pid_file = write_pid_file(os.getpid())
    logger.info(f"进程ID: {os.getpid()}, PID文件: {pid_file}")

    # 加载配置
    if config_file:
        load_config(config_file)

    # 设置信号处理
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if hasattr(signal, "SIGHUP"):  # Windows没有SIGHUP
        signal.signal(signal.SIGHUP, signal_handler)

    # 初始化监控器
    try:
        monitor = WebServiceMonitor()
        success = monitor.start(config_ids)

        if success:
            logger.info(f"监控已启动，正在监控 {len(monitor.configurations)} 个配置")

            # 初始状态更新
            update_status(monitor, start_time)
            last_status_update = time.time()

            # 保持程序运行，直到收到退出信号
            while running:
                time.sleep(1)

                # 每60秒更新一次状态
                current_time = time.time()
                if current_time - last_status_update >= 60:
                    update_status(monitor, start_time)
                    last_status_update = current_time

            # 优雅退出
            logger.info("正在停止监控...")
            if monitor:
                monitor.stop()
            logger.info("监控已安全停止")

        else:
            logger.error("启动监控失败，可能没有可用配置")
            return 1

    except Exception as e:
        logger.exception(f"监控运行出错: {e}")
        return 1
    finally:
        # 清理状态
        try:
            update_status_stopped()
        except Exception:
            pass

        # 清理PID文件
        try:
            if os.path.exists(pid_file):
                os.unlink(pid_file)
        except Exception:
            pass

    return 0


def update_status(monitor, start_time):
    """更新状态文件"""
    if not monitor:
        return

    try:
        status_dir = os.path.join(os.path.expanduser("~"), ".webservice_monitor")
        os.makedirs(status_dir, exist_ok=True)

        status_file = os.path.join(status_dir, "monitor_status.json")

        # 收集状态信息
        status = {
            "running": True,
            "start_time": start_time.isoformat(),
            "configs_count": len(monitor.configurations),
            "configs": [
                {"id": k, "name": v.name} for k, v in monitor.configurations.items()
            ],
            "pid": os.getpid(),
            "last_update": datetime.datetime.now().isoformat(),
        }

        with open(status_file, "w") as f:
            json.dump(status, f)

        logger.debug("状态文件已更新")
    except Exception as e:
        logger.exception(f"更新状态文件时出错: {e}")


def update_status_stopped():
    """更新状态为已停止"""
    try:
        status_dir = os.path.join(os.path.expanduser("~"), ".webservice_monitor")
        status_file = os.path.join(status_dir, "monitor_status.json")

        # 如果文件存在，读取然后更新
        if os.path.exists(status_file):
            with open(status_file, "r") as f:
                status = json.load(f)
        else:
            status = {}

        status.update(
            {
                "running": False,
                "stop_time": datetime.datetime.now().isoformat(),
                "last_update": datetime.datetime.now().isoformat(),
            }
        )

        with open(status_file, "w") as f:
            json.dump(status, f)
    except Exception as e:
        if logger:
            logger.exception(f"更新停止状态时出错: {e}")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="WebService监控工具运行脚本")
    parser.add_argument("--config-file", "-f", help="配置文件路径")
    parser.add_argument("--config-ids", "-c", help="要监控的配置ID，用逗号分隔")

    args = parser.parse_args()

    config_ids = None
    if args.config_ids:
        try:
            config_ids = [int(x.strip()) for x in args.config_ids.split(",")]
            logger.info(f"将监控以下配置ID: {config_ids}")
        except ValueError as e:
            print(f"错误: 配置ID必须是整数: {e}")
            return 1
        except Exception as e:
            print(f"解析配置ID时出错: {e}")
            return 1

    return run_monitor(args.config_file, config_ids)


if __name__ == "__main__":
    # 使用multiprocessing启动，解决Windows上的daemon线程问题
    multiprocessing.freeze_support()
    sys.exit(main())

    multiprocessing.freeze_support()
    sys.exit(main())
