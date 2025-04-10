"""
监控核心逻辑
"""

import time
import logging
import datetime
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Any, Tuple
import sys

import requests

from webservice_monitor.db.models import (
    Configuration,
    CallDetail,
    MinuteStats,
    Alert,
    AlertType,
)
from webservice_monitor.db import repository
from webservice_monitor.utils.config import get_setting

logger = logging.getLogger(__name__)


class WebServiceMonitor:
    """WebService监控类"""

    def __init__(self):
        """初始化监控器"""
        self.executor = None  # 延迟初始化线程池
        self.configurations = {}
        self.running = False
        self._thread = None
        self._lock = threading.Lock()  # 添加线程锁保护共享资源

    def load_configurations(self):
        """加载活跃配置"""
        configs = repository.get_all_configurations(active_only=True)
        self.configurations = {config.id: config for config in configs}
        return len(self.configurations)

    def call_webservice(self, config: Configuration) -> CallDetail:
        """调用WebService并返回结果"""
        url = config.url
        headers = config.headers or {"Content-Type": "application/xml; charset=utf-8"}

        call_detail = CallDetail(config_id=config.id)

        start_time = time.time()
        try:
            if config.is_post:
                response = requests.post(
                    url, data=config.payload, headers=headers, timeout=config.timeout
                )
            else:
                response = requests.get(url, headers=headers, timeout=config.timeout)

            call_detail.status_code = response.status_code
        except Exception as e:
            call_detail.status_code = -1
            call_detail.error_message = str(e)

        call_detail.response_time = time.time() - start_time

        # 保存调用详情
        try:
            call_detail_id = repository.save_call_detail(call_detail)

            # 检查是否需要触发告警
            if (
                not call_detail.is_success
                or call_detail.response_time > config.alert_threshold
            ):
                alert_type = (
                    AlertType.AVAILABILITY
                    if not call_detail.is_success
                    else AlertType.PERFORMANCE
                )
                alert_message = (
                    f"状态码: {call_detail.status_code}"
                    if not call_detail.is_success
                    else f"响应时间: {call_detail.response_time:.2f}秒 > {config.alert_threshold}秒"
                )

                repository.create_alert(config.id, alert_type, alert_message)

                # 记录告警日志
                logger.warning(
                    f"告警: 配置 {config.name} ({config.id}) - {alert_message}"
                )
        except Exception as e:
            logger.exception(f"保存调用详情或创建告警时出错: {str(e)}")

        return call_detail

    def batch_call_webservice(self, config: Configuration) -> List[CallDetail]:
        """批量调用WebService"""
        if not self._is_in_monitoring_hours(config):
            logger.info(
                f"配置 {config.name} 当前不在监控时间段 ({config.monitoring_hours}) 内"
            )
            return []

        results = []
        for _ in range(config.calls_per_batch):
            try:
                result = self.call_webservice(config)
                results.append(result)
                logger.info(
                    f"调用完成: {config.name} - 状态码: {result.status_code}, "
                    f"响应时间: {result.response_time:.4f}秒"
                )
            except Exception as e:
                logger.exception(f"调用 {config.name} 时出错: {str(e)}")

            # 短暂暂停避免请求过快
            time.sleep(0.2)

        return results

    def calculate_minute_stats(self, config_id: int = None):
        """计算过去一分钟的统计数据"""
        now = datetime.datetime.now()
        one_minute_ago = now - datetime.timedelta(minutes=1)

        config_ids = [config_id] if config_id else list(self.configurations.keys())

        for cid in config_ids:
            if cid not in self.configurations:
                continue

            config = self.configurations[cid]

            # 从数据库获取过去一分钟内的调用详情
            try:
                with repository.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """SELECT response_time, status_code FROM call_details 
                        WHERE timestamp >= ? AND timestamp <= ? AND config_id = ?""",
                        (one_minute_ago.isoformat(), now.isoformat(), cid),
                    )

                    results = cursor.fetchall()

                if not results:
                    continue

                response_times = [row["response_time"] for row in results]
                success_count = sum(
                    1 for row in results if 200 <= row["status_code"] < 300
                )

                # 计算统计数据
                stats = MinuteStats(
                    start_time=one_minute_ago.isoformat(),
                    end_time=now.isoformat(),
                    avg_response_time=statistics.mean(response_times),
                    max_response_time=max(response_times),
                    min_response_time=min(response_times),
                    call_count=len(response_times),
                    success_count=success_count,
                    config_id=cid,
                )

                # 保存统计数据
                repository.save_minute_stats(stats)

                # 记录日志
                success_rate = (
                    (success_count / len(response_times)) * 100 if response_times else 0
                )
                logger.info(
                    f"一分钟统计: {config.name} - 总调用: {stats.call_count}, 成功率: {success_rate:.2f}%, "
                    f"平均响应时间: {stats.avg_response_time:.4f}秒"
                )
            except Exception as e:
                logger.exception(f"计算配置 {cid} 的统计数据时出错: {str(e)}")

    def _is_in_monitoring_hours(self, config: Configuration) -> bool:
        """检查当前时间是否在监控时间段内"""
        now = datetime.datetime.now()
        current_hour = now.hour

        monitoring_hours = config.monitoring_hours

        try:
            if "-" in monitoring_hours:
                start_hour, end_hour = map(int, monitoring_hours.split("-"))
                if start_hour <= end_hour:
                    return start_hour <= current_hour <= end_hour
                else:  # 跨天的情况
                    return current_hour >= start_hour or current_hour <= end_hour
            else:
                # 单个小时
                return current_hour == int(monitoring_hours)
        except (ValueError, TypeError):
            logger.warning(
                f"配置 {config.name} 的监控时间段 '{monitoring_hours}' 格式无效，默认全天监控"
            )
            return True

    def start(self, config_ids=None):
        """启动监控"""
        with self._lock:
            if self.running:
                logger.warning("监控已经在运行中")
                return False

            # 初始化数据库
            repository.init_db()

            # 加载配置
            self.load_configurations()

            if config_ids:
                # 过滤出指定的配置
                self.configurations = {
                    k: v for k, v in self.configurations.items() if k in config_ids
                }

            if not self.configurations:
                logger.warning("没有找到活跃的配置，监控未启动")
                return False

            # 初始化线程池，延迟创建确保不会过早关闭
            max_workers = get_setting("MAX_WORKERS", 10)
            self.executor = ThreadPoolExecutor(max_workers=max_workers)

            self.running = True
            self._thread = threading.Thread(target=self._monitoring_loop)
            self._thread.daemon = False  # 非守护线程，主线程退出后继续运行
            self._thread.start()

            logger.info(f"监控已启动，正在监控 {len(self.configurations)} 个配置")
            return True

    def stop(self):
        """停止监控"""
        with self._lock:
            if not self.running:
                logger.warning("监控未运行")
                return False

            logger.info("正在停止监控...")
            self.running = False

            # 等待监控线程结束
            if self._thread and self._thread.is_alive():
                logger.info("等待监控线程结束...")
                # 仅等待一个合理的时间
                self._thread.join(timeout=10)
                if self._thread.is_alive():
                    logger.warning("监控线程未能在超时时间内结束")

            # 安全关闭线程池
            if self.executor:
                logger.info("正在关闭线程池...")
                try:
                    # 尽可能优雅地关闭线程池
                    self.executor.shutdown(
                        wait=True, cancel_futures=True
                    )  # Python 3.9+加入了cancel_futures参数
                except TypeError:
                    # 旧版本Python没有cancel_futures参数
                    self.executor.shutdown(wait=True)
                self.executor = None

            logger.info("监控已停止")
            return True

    def _monitoring_loop(self):
        """监控循环"""
        next_minute_mark = self._get_next_minute_mark()
        stats_calculated = False
        error_count = 0

        while self.running:
            try:
                # 如果解释器正在关闭，安全退出
                if sys.is_finalizing():
                    logger.warning("检测到解释器正在关闭，停止监控循环")
                    break

                now = datetime.datetime.now()

                # 每分钟计算一次统计数据
                if now >= next_minute_mark and not stats_calculated:
                    try:
                        self.calculate_minute_stats()
                        stats_calculated = True
                        logger.debug("已计算统计数据")
                    except Exception as e:
                        logger.exception("计算统计数据时出错")

                # 设置下一个分钟标记
                if now >= next_minute_mark and stats_calculated:
                    next_minute_mark = self._get_next_minute_mark()
                    stats_calculated = False
                    logger.debug(f"设置下一个分钟标记: {next_minute_mark}")

                # 对每个配置执行监控
                with self._lock:
                    # 如果监控已停止或解释器正在关闭，安全退出
                    if not self.running or sys.is_finalizing():
                        break

                    # 检查线程池是否有效
                    if not self.executor or getattr(self.executor, "_shutdown", False):
                        logger.warning("线程池已关闭，重新初始化")
                        try:
                            max_workers = get_setting("MAX_WORKERS", 10)
                            self.executor = ThreadPoolExecutor(max_workers=max_workers)
                        except Exception as e:
                            logger.exception("重新初始化线程池失败")
                            break

                    for config_id, config in list(self.configurations.items()):
                        try:
                            if self._should_call_now(config):
                                # 安全地提交任务
                                if (
                                    not getattr(self.executor, "_shutdown", False)
                                    and self.running
                                ):
                                    self.executor.submit(
                                        self.batch_call_webservice, config
                                    )
                        except Exception as e:
                            logger.exception(f"为配置 {config.name} 调度监控任务时出错")

                # 重置错误计数器
                error_count = 0

                # 短暂睡眠
                time.sleep(1)

            except Exception as e:
                error_count += 1
                logger.exception(f"监控循环出错: {str(e)}")

                # 连续错误过多，暂停较长时间
                if error_count > 5:
                    logger.warning(f"连续错误超过5次，暂停30秒")
                    time.sleep(30)
                    error_count = 0
                else:
                    time.sleep(5)

        logger.info("监控循环已退出")

    def _get_next_minute_mark(self):
        """获取下一分钟的时间点"""
        now = datetime.datetime.now()
        return (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)

    def _should_call_now(self, config):
        """判断是否应当在当前时间调用指定配置"""
        if not self._is_in_monitoring_hours(config):
            return False

        # 根据调用间隔判断是否应当调用
        now = datetime.datetime.now()
        seconds_in_minute = now.second

        return seconds_in_minute % config.call_interval == 0
