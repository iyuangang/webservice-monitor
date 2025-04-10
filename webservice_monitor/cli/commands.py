"""
命令行界面命令定义
"""

import os
import sys
import json
import click
import logging
import datetime
import signal
import time
from tabulate import tabulate
from typing import List, Dict, Optional, Any
import psutil  # 需要添加到依赖中

from webservice_monitor.db import repository
from webservice_monitor.db.models import Configuration
from webservice_monitor.core.scheduler import MonitorScheduler
from webservice_monitor.core.caller import WebServiceCaller
from webservice_monitor.reports.html_generator import HTMLReportGenerator
from webservice_monitor.reports.pdf_generator import PDFReportGenerator
from webservice_monitor.utils.config import get_setting, load_config
from webservice_monitor.cli.formatters import format_config, format_alert

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def cli():
    """WebService监控工具 - 监控多个Web服务接口的性能和可用性"""
    pass


@cli.group()
def config():
    """配置管理命令"""
    pass


@config.command("add")
@click.option("--name", "-n", required=True, help="配置名称")
@click.option("--url", "-u", required=True, help="接口URL")
@click.option(
    "--method", "-m", default="GET", type=click.Choice(["GET", "POST"]), help="请求方法"
)
@click.option("--headers", "-h", help="请求头 (JSON格式)")
@click.option("--payload", "-p", help="请求正文 (POST方法)")
@click.option("--interval", "-i", default=5, type=int, help="调用间隔 (秒)")
@click.option("--batch", "-b", default=5, type=int, help="每批调用次数")
@click.option("--timeout", "-t", default=10, type=int, help="超时时间 (秒)")
@click.option("--alert-threshold", "-a", default=2.0, type=float, help="告警阈值 (秒)")
@click.option("--hours", default="0-23", help="监控时段 (如 9-17 表示工作时间)")
@click.option("--test/--no-test", default=True, help="添加前测试连接")
def add_config(
    name,
    url,
    method,
    headers,
    payload,
    interval,
    batch,
    timeout,
    alert_threshold,
    hours,
    test,
):
    """添加新配置"""
    if headers:
        try:
            headers_dict = json.loads(headers)
        except json.JSONDecodeError:
            click.echo(f"错误: 请求头必须是有效的JSON格式")
            return
    else:
        headers_dict = {}

    # 创建配置对象
    config = Configuration(
        name=name,
        url=url,
        method=method,
        headers=headers_dict,
        payload=payload,
        call_interval=interval,
        calls_per_batch=batch,
        timeout=timeout,
        alert_threshold=alert_threshold,
        monitoring_hours=hours,
    )

    # 测试连接
    if test:
        click.echo(f"测试连接 {url} ...")
        success, message, response_time = WebServiceCaller.test_connection(
            url, method, headers_dict, payload, timeout
        )

        click.echo(f"测试结果: {message}")
        click.echo(f"响应时间: {response_time:.4f}秒")

        if not success and not click.confirm("连接测试失败。是否仍要添加此配置?"):
            click.echo("已取消添加配置")
            return

    # 保存配置
    try:
        config_id, action = repository.save_configuration(config)
        click.echo(f"已{action}配置 '{name}' (ID: {config_id})")
    except Exception as e:
        click.echo(f"错误: {str(e)}")


@config.command("list")
@click.option("--active/--all", default=False, help="只显示活跃配置")
@click.option("--verbose", "-v", is_flag=True, help="显示详细信息")
def list_configs(active, verbose):
    """列出所有配置"""
    configs = repository.get_all_configurations(active_only=active)

    if not configs:
        click.echo("没有找到配置")
        return

    if verbose:
        click.echo(
            "\n"
            + tabulate(
                [format_config(config, verbose=True) for config in configs],
                headers=[
                    "ID",
                    "名称",
                    "URL",
                    "方法",
                    "间隔",
                    "批量",
                    "超时",
                    "告警阈值",
                    "时段",
                    "状态",
                ],
                tablefmt="grid",
            )
        )
    else:
        click.echo(
            "\n"
            + tabulate(
                [format_config(config) for config in configs],
                headers=["ID", "名称", "URL", "状态"],
                tablefmt="simple",
            )
        )

    click.echo(f"\n共 {len(configs)} 个配置")


@config.command("show")
@click.argument("id_or_name")
def show_config(id_or_name):
    """显示配置详情"""
    config = None

    # 尝试按ID查找
    try:
        config_id = int(id_or_name)
        config = repository.get_configuration(config_id=config_id)
    except ValueError:
        # 按名称查找
        config = repository.get_configuration(name=id_or_name)

    if not config:
        click.echo(f"错误: 未找到配置 '{id_or_name}'")
        return

    click.echo("\n配置详情:")
    click.echo(f"ID: {config.id}")
    click.echo(f"名称: {config.name}")
    click.echo(f"URL: {config.url}")
    click.echo(f"方法: {config.method}")
    click.echo(f"请求头: {json.dumps(config.headers, indent=2, ensure_ascii=False)}")

    if config.payload:
        click.echo(f"请求正文: {config.payload}")

    click.echo(f"调用间隔: {config.call_interval}秒")
    click.echo(f"每批调用次数: {config.calls_per_batch}")
    click.echo(f"超时时间: {config.timeout}秒")
    click.echo(f"告警阈值: {config.alert_threshold}秒")
    click.echo(f"监控时段: {config.monitoring_hours}")
    click.echo(f"活跃状态: {'是' if config.is_active else '否'}")
    click.echo(f"创建时间: {config.created_at}")
    click.echo(f"更新时间: {config.updated_at}")


@config.command("enable")
@click.argument("id_or_name")
def enable_config(id_or_name):
    """启用配置"""
    success = False

    try:
        config_id = int(id_or_name)
        success = repository.toggle_configuration(config_id=config_id, active=True)
    except ValueError:
        success = repository.toggle_configuration(name=id_or_name, active=True)

    if success:
        click.echo(f"已启用配置 '{id_or_name}'")
    else:
        click.echo(f"错误: 未找到配置 '{id_or_name}' 或无法启用")


@config.command("disable")
@click.argument("id_or_name")
def disable_config(id_or_name):
    """禁用配置"""
    success = False

    try:
        config_id = int(id_or_name)
        success = repository.toggle_configuration(config_id=config_id, active=False)
    except ValueError:
        success = repository.toggle_configuration(name=id_or_name, active=False)

    if success:
        click.echo(f"已禁用配置 '{id_or_name}'")
    else:
        click.echo(f"错误: 未找到配置 '{id_or_name}' 或无法禁用")


@config.command("delete")
@click.argument("id_or_name")
@click.option("--force", "-f", is_flag=True, help="强制删除，不提示确认")
def delete_config(id_or_name, force):
    """删除配置"""
    config = None

    # 尝试按ID查找
    try:
        config_id = int(id_or_name)
        config = repository.get_configuration(config_id=config_id)
    except ValueError:
        # 按名称查找
        config = repository.get_configuration(name=id_or_name)

    if not config:
        click.echo(f"错误: 未找到配置 '{id_or_name}'")
        return

    if not force and not click.confirm(f"确定要删除配置 '{config.name}' 吗?"):
        click.echo("已取消删除操作")
        return

    success = False
    if config.id:
        success = repository.delete_configuration(config_id=config.id)
    else:
        success = repository.delete_configuration(name=config.name)

    if success:
        click.echo(f"已删除配置 '{config.name}'")
    else:
        click.echo(f"错误: 无法删除配置 '{config.name}'")


@config.command("import")
@click.argument("json_file", type=click.Path(exists=True))
@click.option("--test/--no-test", default=True, help="导入前测试连接")
def import_config(json_file, test):
    """从JSON文件导入配置"""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        click.echo(f"错误: 无法读取JSON文件: {str(e)}")
        return

    configs = []

    # 支持单个配置或配置数组
    if isinstance(data, dict):
        config_name = (
            data.get("name") or os.path.splitext(os.path.basename(json_file))[0]
        )
        configs.append((config_name, data))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                click.echo(f"警告: 跳过第 {i+1} 项，不是有效的对象")
                continue

            config_name = item.get("name") or f"config_{i+1}"
            configs.append((config_name, item))
    else:
        click.echo("错误: JSON文件必须包含对象或对象数组")
        return

    success_count = 0
    for name, config_data in configs:
        # 创建配置对象
        try:
            config = Configuration.from_json(config_data, name)
        except Exception as e:
            click.echo(f"错误: 配置 '{name}' 解析失败: {str(e)}")
            continue

        # 测试连接
        if test:
            click.echo(f"测试连接 {config.url} ...")
            success, message, response_time = WebServiceCaller.test_connection(
                config.url,
                config.method,
                config.headers,
                config.payload,
                config.timeout,
            )

            click.echo(f"测试结果: {message}")
            click.echo(f"响应时间: {response_time:.4f}秒")

            if not success and not click.confirm(
                f"配置 '{name}' 连接测试失败。是否仍要导入?"
            ):
                click.echo(f"已跳过配置 '{name}'")
                continue

        # 保存配置
        try:
            config_id, action = repository.save_configuration(config)
            click.echo(f"已{action}配置 '{name}' (ID: {config_id})")
            success_count += 1
        except Exception as e:
            click.echo(f"错误: 无法保存配置 '{name}': {str(e)}")

    click.echo(f"导入完成: 成功 {success_count}/{len(configs)} 个配置")


@config.command("export")
@click.argument("output_file", type=click.Path())
@click.option("--ids", "-i", help="要导出的配置ID，用逗号分隔")
@click.option("--active-only", "-a", is_flag=True, help="只导出活跃配置")
def export_config(output_file, ids, active_only):
    """导出配置到JSON文件"""
    if ids:
        try:
            id_list = [int(x.strip()) for x in ids.split(",")]
            configs = []
            for config_id in id_list:
                config = repository.get_configuration(config_id=config_id)
                if config:
                    configs.append(config)
        except ValueError:
            click.echo("错误: 配置ID必须是整数")
            return
    else:
        configs = repository.get_all_configurations(active_only=active_only)

    if not configs:
        click.echo("没有找到要导出的配置")
        return

    # 准备导出数据
    export_data = []
    for config in configs:
        config_dict = {
            "name": config.name,
            "url": config.url,
            "method": config.method,
            "headers": config.headers,
            "call_interval": config.call_interval,
            "calls_per_batch": config.calls_per_batch,
            "timeout": config.timeout,
            "alert_threshold": config.alert_threshold,
            "monitoring_hours": config.monitoring_hours,
            "is_active": config.is_active,
        }

        if config.payload:
            if config.is_post:
                config_dict["xml_payload"] = config.payload
            else:
                config_dict["payload"] = config.payload

        export_data.append(config_dict)

    # 写入文件
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        click.echo(f"已导出 {len(configs)} 个配置到 {output_file}")
    except Exception as e:
        click.echo(f"错误: 无法写入文件: {str(e)}")


@cli.command("start")
@click.option("--config", "-c", help="要监控的配置ID，用逗号分隔")
@click.option("--foreground", "-f", is_flag=True, help="在前台运行，显示实时日志")
@click.option("--config-file", help="使用指定的配置文件")
def start_monitoring(config, foreground, config_file):
    """启动监控"""
    import subprocess
    import os
    import sys

    # 处理配置ID
    config_ids = None
    if config:
        try:
            config_ids = [int(x.strip()) for x in config.split(",")]
        except ValueError:
            click.echo("错误: 配置ID必须是整数")
            return

    # 脚本路径
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "scripts", "run_monitor.py"
    )

    if not os.path.exists(script_path):
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "scripts",
            "run_monitor.py",
        )

    if not os.path.exists(script_path):
        click.echo(f"错误: 未找到运行脚本 {script_path}")
        return

    # 构建命令参数
    cmd = [sys.executable, script_path]

    if config:
        cmd.extend(["--config-ids", config])

    if config_file:
        cmd.extend(["--config-file", config_file])

    # 运行方式
    if foreground:
        # 前台运行
        click.echo(f"正在前台启动监控...")
        try:
            process = subprocess.Popen(cmd)
            click.echo(f"监控进程已启动 (PID: {process.pid})，按Ctrl+C停止...")
            process.wait()
        except KeyboardInterrupt:
            click.echo("\n正在停止监控...")
            process.terminate()
            process.wait(timeout=10)
            click.echo("监控已停止")
    else:
        # 后台运行
        if os.name == "nt":  # Windows
            try:
                from subprocess import CREATE_NO_WINDOW

                process = subprocess.Popen(
                    cmd,
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except AttributeError:
                # 如果CREATE_NO_WINDOW不可用，使用标准方式
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
        else:  # Unix/Linux
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

        # 等待短暂时间，检查进程是否立即失败
        import time

        time.sleep(1)

        if process.poll() is not None:
            click.echo(f"错误: 监控进程启动失败 (退出码: {process.returncode})")
            stdout, stderr = process.communicate()
            if stdout:
                click.echo(f"输出: {stdout.decode('utf-8', errors='replace').strip()}")
            if stderr:
                click.echo(f"错误: {stderr.decode('utf-8', errors='replace').strip()}")
        else:
            click.echo(f"监控已在后台启动 (PID: {process.pid})")

            # 写入PID用于后续停止
            pid_dir = os.path.join(os.path.expanduser("~"), ".webservice_monitor")
            os.makedirs(pid_dir, exist_ok=True)

            pid_file = os.path.join(pid_dir, "monitor.pid")
            with open(pid_file, "w") as f:
                f.write(str(process.pid))


@cli.command("stop")
def stop_monitoring():
    """停止监控"""
    import os
    import signal

    pid_file = os.path.join(
        os.path.expanduser("~"), ".webservice_monitor", "monitor.pid"
    )

    if not os.path.exists(pid_file):
        click.echo("未找到运行中的监控进程")
        return

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())

        click.echo(f"正在停止监控进程 (PID: {pid})...")

        # 发送终止信号
        if os.name == "nt":  # Windows
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, False, pid)
            kernel32.TerminateProcess(handle, 0)
            kernel32.CloseHandle(handle)
        else:  # Unix/Linux
            os.kill(pid, signal.SIGTERM)

        # 等待进程退出
        import time

        for _ in range(10):
            try:
                if os.name == "nt":  # Windows
                    import subprocess

                    subprocess.check_call(
                        f"taskkill /F /PID {pid}",
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                    )
                else:
                    os.kill(pid, 0)
                time.sleep(1)
            except (subprocess.CalledProcessError, ProcessLookupError, OSError):
                # 进程已终止
                break
        else:
            click.echo("警告: 进程未能在10秒内退出")

        # 删除PID文件
        os.remove(pid_file)
        click.echo("监控已停止")

    except Exception as e:
        click.echo(f"停止监控时出错: {str(e)}")
        # 尝试清理PID文件
        if os.path.exists(pid_file):
            os.remove(pid_file)


@cli.command("status")
def check_status():
    """检查监控状态"""
    import os
    import json
    import psutil
    from datetime import datetime

    pid_file = os.path.join(
        os.path.expanduser("~"), ".webservice_monitor", "monitor.pid"
    )
    status_file = os.path.join(
        os.path.expanduser("~"), ".webservice_monitor", "monitor_status.json"
    )

    # 首先检查状态文件
    status_data = None
    if os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                status_data = json.load(f)

            # 检查状态文件是否过期（超过2分钟未更新）
            if "last_update" in status_data:
                last_update = datetime.fromisoformat(status_data["last_update"])
                if (datetime.now() - last_update).total_seconds() > 120:
                    click.echo("警告: 状态信息可能已过期")
        except Exception as e:
            click.echo(f"警告: 无法读取状态文件: {str(e)}")

    # 其次检查PID文件
    if not os.path.exists(pid_file):
        click.echo("监控未运行")
        return

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())

        # 检查进程是否存在
        if psutil.pid_exists(pid):
            process = None
            try:
                process = psutil.Process(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # 显示状态信息
            click.echo(f"监控正在运行 (PID: {pid})")

            # 如果有状态数据，显示更多信息
            if status_data and status_data.get("running", False):
                if "start_time" in status_data:
                    start_time = datetime.fromisoformat(status_data["start_time"])
                    runtime = datetime.now() - start_time
                    days, seconds = runtime.days, runtime.seconds
                    hours, remainder = divmod(seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    click.echo(
                        f"运行时间: {days}天 {hours}小时 {minutes}分钟 {seconds}秒"
                    )

                if "configs_count" in status_data:
                    click.echo(f"监控配置数: {status_data['configs_count']}")

                if "configs" in status_data and status_data["configs"]:
                    click.echo("\n监控的配置:")
                    for cfg in status_data["configs"]:
                        click.echo(f"  - ID: {cfg['id']}, 名称: {cfg['name']}")

            # 如果有进程信息，显示资源使用情况
            if process:
                try:
                    # 获取CPU和内存使用情况
                    cpu_percent = process.cpu_percent(interval=0.1)
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / (1024 * 1024)

                    click.echo(f"\n资源使用:")
                    click.echo(f"  CPU使用率: {cpu_percent:.1f}%")
                    click.echo(f"  内存使用: {memory_mb:.2f} MB")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    click.echo("\n无法获取资源使用情况")

        else:
            click.echo("监控可能已异常终止")
            # 清理过时的PID文件
            os.remove(pid_file)
            # 也清理状态文件
            if os.path.exists(status_file):
                os.remove(status_file)

    except Exception as e:
        click.echo(f"检查状态时出错: {str(e)}")
        click.echo("监控状态未知")


@cli.command("reload")
def reload_configurations():
    """重新加载配置"""
    import os
    import time
    import signal
    import subprocess
    import sys
    import psutil

    pid_file = os.path.join(
        os.path.expanduser("~"), ".webservice_monitor", "monitor.pid"
    )

    if not os.path.exists(pid_file):
        click.echo("错误: 监控未运行，无需重新加载配置")
        return

    try:
        with open(pid_file, "r") as f:
            pid_str = f.read().strip()

        try:
            pid = int(pid_str)
        except ValueError:
            click.echo(f"错误: PID文件包含无效的PID: {pid_str}")
            os.remove(pid_file)
            return

        # 检查进程是否存在
        if not psutil.pid_exists(pid):
            click.echo(f"错误: 找不到PID为 {pid} 的进程")
            # 清理过时的PID文件
            os.remove(pid_file)
            return

        # Windows系统重启进程
        if os.name == "nt":
            click.echo(f"Windows系统需要重启监控进程以重新加载配置...")

            # 结束进程
            try:
                process = psutil.Process(pid)
                click.echo(f"正在终止进程 {pid}...")
                process.terminate()

                # 等待进程结束
                gone, alive = psutil.wait_procs([process], timeout=5)
                if alive:
                    click.echo("进程未响应，尝试强制终止...")
                    for p in alive:
                        p.kill()
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                click.echo(f"终止进程时出错: {str(e)}")

            # 确保PID文件被删除
            if os.path.exists(pid_file):
                try:
                    os.remove(pid_file)
                except Exception as e:
                    click.echo(f"删除PID文件时出错: {str(e)}")

            # 重启进程
            click.echo("正在重新启动监控...")

            # 简单地启动新进程而不传递复杂参数
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "scripts", "run_monitor.py"
            )

            if not os.path.exists(script_path):
                script_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    "scripts",
                    "run_monitor.py",
                )

            if not os.path.exists(script_path):
                click.echo(f"错误: 未找到运行脚本 {script_path}")
                return

            try:
                if os.name == "nt":  # Windows
                    try:
                        from subprocess import CREATE_NO_WINDOW

                        process = subprocess.Popen(
                            [sys.executable, script_path],
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                    except AttributeError:
                        process = subprocess.Popen(
                            [sys.executable, script_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                else:  # Unix/Linux
                    process = subprocess.Popen(
                        [sys.executable, script_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True,
                    )

                # 等待短暂时间，检查进程是否立即失败
                time.sleep(1)

                if process.poll() is not None:
                    click.echo(f"错误: 监控进程启动失败 (退出码: {process.returncode})")
                    stdout, stderr = process.communicate()
                    if stdout:
                        click.echo(
                            f"输出: {stdout.decode('utf-8', errors='replace').strip()}"
                        )
                    if stderr:
                        click.echo(
                            f"错误: {stderr.decode('utf-8', errors='replace').strip()}"
                        )
                    return

                click.echo(f"监控已在后台重新启动 (PID: {process.pid})")

                # 更新PID文件
                with open(pid_file, "w") as f:
                    f.write(str(process.pid))

            except Exception as e:
                click.echo(f"启动新进程时出错: {str(e)}")

        else:
            # Unix系统使用信号
            try:
                # 发送SIGHUP信号，通常用于重新加载配置
                os.kill(pid, signal.SIGHUP)
                click.echo(f"已发送重新加载信号到监控进程 (PID: {pid})")
            except ProcessLookupError:
                click.echo(f"错误: 找不到PID为 {pid} 的进程")
                # 清理过时的PID文件
                os.remove(pid_file)
            except Exception as e:
                click.echo(f"发送信号时出错: {str(e)}")

    except Exception as e:
        click.echo(f"重新加载配置时出错: {str(e)}")


@cli.group()
def report():
    """报告生成命令"""
    pass


@report.command("generate")
@click.option("--date", "-d", help="报告日期 (YYYY-MM-DD)，默认为昨天")
@click.option("--config", "-c", type=int, help="配置ID，不指定则生成所有配置的报告")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["html", "pdf"]),
    default="html",
    help="报告格式",
)
def generate_report(date, config, format):
    """生成报告"""
    if date:
        try:
            report_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            click.echo("错误: 日期格式必须为 YYYY-MM-DD")
            return
    else:
        report_date = datetime.datetime.now().date() - datetime.timedelta(days=1)

    # 验证配置是否存在
    if config:
        config_obj = repository.get_configuration(config_id=config)
        if not config_obj:
            click.echo(f"错误: 未找到配置ID {config}")
            return

    try:
        if format == "pdf":
            generator = PDFReportGenerator()
        else:
            generator = HTMLReportGenerator()

        report_path = generator.generate_report(report_date, config)
        click.echo(f"报告已生成: {report_path}")
    except Exception as e:
        click.echo(f"错误: 生成报告失败: {str(e)}")


@cli.group()
def alert():
    """告警管理命令"""
    pass


@alert.command("list")
@click.option("--config", "-c", type=int, help="配置ID，不指定则显示所有告警")
def list_alerts(config):
    """列出活跃告警"""
    alerts = repository.get_active_alerts(config_id=config)

    if not alerts:
        click.echo("没有活跃告警")
        return

    click.echo(
        "\n"
        + tabulate(
            [format_alert(alert) for alert in alerts],
            headers=["ID", "时间", "配置", "类型", "消息"],
            tablefmt="grid",
        )
    )

    click.echo(f"\n共 {len(alerts)} 个活跃告警")


@alert.command("resolve")
@click.argument("alert_id", type=int)
def resolve_alert(alert_id):
    """解决告警"""
    success = repository.resolve_alert(alert_id)

    if success:
        click.echo(f"已解决告警 ID {alert_id}")
    else:
        click.echo(f"错误: 未找到告警 ID {alert_id} 或无法解决")


@cli.command("cleanup")
@click.option("--days", "-d", type=int, default=30, help="保留天数，默认30天")
@click.option("--force", "-f", is_flag=True, help="强制清理，不提示确认")
def cleanup_data(days, force):
    """清理旧数据"""
    if days < 1:
        click.echo("错误: 保留天数必须大于0")
        return

    if not force and not click.confirm(f"确定要删除 {days} 天前的数据吗?"):
        click.echo("已取消清理操作")
        return

    try:
        call_details, minute_stats, alerts = repository.cleanup_old_data(days)
        click.echo(f"已清理 {call_details} 条调用详情记录")
        click.echo(f"已清理 {minute_stats} 条分钟统计记录")
        click.echo(f"已清理 {alerts} 条已解决的告警记录")
    except Exception as e:
        click.echo(f"错误: 清理数据失败: {str(e)}")


@cli.command("test")
@click.option("--url", "-u", required=True, help="接口URL")
@click.option(
    "--method", "-m", default="GET", type=click.Choice(["GET", "POST"]), help="请求方法"
)
@click.option("--headers", "-h", help="请求头 (JSON格式)")
@click.option("--payload", "-p", help="请求正文 (POST方法)")
@click.option("--timeout", "-t", default=10, type=int, help="超时时间 (秒)")
@click.option("--repeat", "-r", default=1, type=int, help="重复次数")
def test_connection(url, method, headers, payload, timeout, repeat):
    """测试接口连接"""
    if headers:
        try:
            headers_dict = json.loads(headers)
        except json.JSONDecodeError:
            click.echo(f"错误: 请求头必须是有效的JSON格式")
            return
    else:
        headers_dict = {}

    click.echo(f"开始测试连接 {url} ({method}) ...")

    times = []
    success_count = 0

    for i in range(repeat):
        click.echo(f"测试 {i+1}/{repeat}: ", nl=False)

        success, message, response_time = WebServiceCaller.test_connection(
            url, method, headers_dict, payload, timeout
        )

        if success:
            click.echo(f"成功 - {response_time:.4f}秒")
            success_count += 1
        else:
            click.echo(f"失败 - {message}")

        times.append(response_time)

    # 显示统计结果
    if repeat > 1:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        success_rate = (success_count / repeat) * 100

        click.echo("\n测试结果统计:")
        click.echo(f"总请求数: {repeat}")
        click.echo(f"成功数: {success_count} ({success_rate:.1f}%)")
        click.echo(f"平均响应时间: {avg_time:.4f}秒")
        click.echo(f"最小响应时间: {min_time:.4f}秒")
        click.echo(f"最大响应时间: {max_time:.4f}秒")


@cli.command("stop-daemon")
def stop_daemon():
    """停止后台运行的监控守护进程"""
    pid_file = os.path.join(
        os.path.expanduser("~"), ".webservice_monitor", "monitor.pid"
    )

    if not os.path.exists(pid_file):
        click.echo("错误: 未找到监控守护进程")
        return

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())

        # 尝试发送终止信号
        os.kill(pid, signal.SIGTERM)
        click.echo(f"已发送终止信号到监控守护进程 (PID: {pid})")

        # 等待进程终止
        for _ in range(5):
            try:
                os.kill(pid, 0)  # 检查进程是否存在
                time.sleep(1)
            except OSError:
                # 进程已终止
                os.remove(pid_file)
                click.echo("监控守护进程已停止")
                return

        # 如果进程仍然存在，尝试强制终止
        click.echo("进程未响应，尝试强制终止...")
        os.kill(pid, signal.SIGKILL)
        os.remove(pid_file)
        click.echo("监控守护进程已强制停止")

    except Exception as e:
        click.echo(f"停止守护进程时出错: {str(e)}")
        if os.path.exists(pid_file):
            os.remove(pid_file)


if __name__ == "__main__":
    cli()
