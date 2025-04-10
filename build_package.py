#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WebService监控工具打包脚本
"""

import os
import shutil
import subprocess
import sys


def run_command(command):
    """运行命令并打印输出"""
    print(f"执行: {command}")
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )

    for line in process.stdout:
        print(line.strip())

    process.wait()
    return process.returncode


def build_package():
    """构建包"""
    # 清理旧的构建文件
    print("清理旧的构建文件...")
    for directory in ["build", "dist", "webservice_monitor.egg-info"]:
        if os.path.exists(directory):
            shutil.rmtree(directory)

    # 安装/升级打包工具
    print("升级打包工具...")
    run_command(f"{sys.executable} -m pip install --upgrade pip setuptools wheel build")

    # 构建包
    print("开始构建包...")
    result = run_command(f"{sys.executable} -m build")

    if result != 0:
        print("构建失败！")
        return False

    # 显示构建的文件
    print("\n构建完成！生成的文件:")
    files = os.listdir("dist")
    for file in files:
        file_path = os.path.join("dist", file)
        size = os.path.getsize(file_path) / 1024  # KB
        print(f"  - {file} ({size:.2f} KB)")

    return True


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    success = build_package()
    sys.exit(0 if success else 1)
