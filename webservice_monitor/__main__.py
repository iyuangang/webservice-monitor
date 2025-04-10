#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WebService监控工具主入口点
"""

import sys
import logging

from webservice_monitor.cli.commands import cli
from webservice_monitor.utils.logger import setup_logger


def main():
    """应用主入口函数"""
    # 设置日志
    setup_logger()

    try:
        # 启动命令行界面
        cli()
    except KeyboardInterrupt:
        logging.info("程序被用户中断")
        print("\n程序已停止")
        return 0
    except Exception as e:
        logging.exception("程序运行出错")
        print(f"错误: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
