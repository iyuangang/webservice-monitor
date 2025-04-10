"""
HTML报告生成
"""

import os
import logging
import datetime
from typing import Dict, List, Optional, Any

import pandas as pd
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader
import numpy as np
import matplotlib.dates as mdates

from webservice_monitor.db import repository
from webservice_monitor.utils.config import get_setting
from webservice_monitor.db.models import Configuration

logger = logging.getLogger(__name__)


class HTMLReportGenerator:
    """HTML报告生成器"""

    def __init__(self):
        """初始化报告生成器"""
        template_dir = os.path.join(os.path.dirname(__file__), "../config/templates")
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.report_dir = get_setting("REPORT_DIR", "reports")

        # 确保报告目录存在
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)

    def generate_report(
        self, date: datetime.date, config_id: Optional[int] = None
    ) -> str:
        """生成HTML报告并返回文件路径"""
        # 获取报告数据
        data = self._prepare_report_data(date, config_id)

        # 生成图表
        charts = self._generate_charts(data, date, config_id)

        # 渲染HTML模板
        template = self.env.get_template("report_template.html")
        html_content = template.render(
            title=data["title"],
            date=date.strftime("%Y-%m-%d"),
            summary=data["summary"],
            performance_data=data["performance_data"],
            alerts=data["alerts"],
            charts=charts,
            configs=data["configs"],
        )

        # 保存报告
        report_filename = f"report_{date.strftime('%Y%m%d')}"
        if config_id:
            config = repository.get_configuration(config_id)
            if config:
                report_filename += f"_{config.name}"

        report_filename += ".html"
        report_path = os.path.join(self.report_dir, report_filename)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"已生成HTML报告: {report_path}")
        return report_path

    def _prepare_report_data(
        self, date: datetime.date, config_id: Optional[int] = None
    ) -> Dict:
        """准备报告数据"""
        # 获取配置信息
        configs = []
        if config_id:
            config = repository.get_configuration(config_id)
            if config:
                configs = [config]
                title = f"{config.name} 监控报告 - {date.strftime('%Y-%m-%d')}"
        else:
            configs = repository.get_all_configurations()
            title = f"WebService监控报告 - {date.strftime('%Y-%m-%d')}"

        # 获取统计数据
        stats_df = repository.get_stats_for_report(date, config_id)

        # 确保datetime列可用于分钟级别聚合
        if not stats_df.empty:
            stats_df["datetime"] = pd.to_datetime(stats_df["start_time"])

        # 计算汇总信息
        summary = {
            "total_calls": stats_df["call_count"].sum() if not stats_df.empty else 0,
            "success_rate": (
                stats_df["success_count"].sum() / stats_df["call_count"].sum() * 100
            )
            if not stats_df.empty and stats_df["call_count"].sum() > 0
            else 0,
            "avg_response_time": stats_df["avg_response_time"].mean()
            if not stats_df.empty
            else 0,
            "max_response_time": stats_df["max_response_time"].max()
            if not stats_df.empty
            else 0,
            "total_configs": len(configs),
            "date": date.strftime("%Y-%m-%d"),
        }

        # 获取告警数据
        alerts = []
        with repository.get_connection() as conn:
            cursor = conn.cursor()
            query = """
            SELECT a.*, c.name as config_name
            FROM alerts a
            JOIN configurations c ON a.config_id = c.id
            WHERE date(a.timestamp) = ?
            """
            params = [date.isoformat()]

            if config_id:
                query += " AND a.config_id = ?"
                params.append(config_id)

            query += " ORDER BY a.timestamp DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                alerts.append(
                    {
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "config_name": row["config_name"],
                        "type": row["type"],
                        "message": row["message"],
                        "resolved": bool(row["resolved"]),
                        "resolved_at": row["resolved_at"],
                    }
                )

        # 准备性能数据
        performance_data = []
        for config in configs:
            config_stats = (
                stats_df[stats_df["config_id"] == config.id]
                if not stats_df.empty
                else pd.DataFrame()
            )

            if not config_stats.empty:
                perf = {
                    "config_id": config.id,
                    "config_name": config.name,
                    "url": config.url,
                    "total_calls": config_stats["call_count"].sum(),
                    "success_rate": (
                        config_stats["success_count"].sum()
                        / config_stats["call_count"].sum()
                        * 100
                    )
                    if config_stats["call_count"].sum() > 0
                    else 0,
                    "avg_response_time": config_stats["avg_response_time"].mean(),
                    "max_response_time": config_stats["max_response_time"].max(),
                    "min_response_time": config_stats["min_response_time"].min(),
                }
                performance_data.append(perf)

        return {
            "title": title,
            "summary": summary,
            "performance_data": performance_data,
            "alerts": alerts,
            "configs": configs,
            "stats_df": stats_df,
        }

    def _generate_charts(
        self, data: Dict, date: datetime.date, config_id: Optional[int] = None
    ) -> Dict:
        """生成报表图表"""
        stats_df = data["stats_df"]
        charts = {}

        if stats_df.empty:
            return charts

        # 确保图表目录存在
        charts_dir = os.path.join(self.report_dir, "charts")
        if not os.path.exists(charts_dir):
            os.makedirs(charts_dir)

        # 生成响应时间趋势图
        chart_id = f"response_time_{date.strftime('%Y%m%d')}"
        if config_id:
            chart_id += f"_{config_id}"

        # 将时间字符串转换为datetime对象，便于按分钟分组
        stats_df["datetime"] = pd.to_datetime(stats_df["start_time"])

        # 设置更好的图表样式
        plt.style.use("ggplot")

        # 创建一个更大的图形，以获得更好的分辨率
        plt.figure(figsize=(15, 8), dpi=100)

        # 定义颜色循环 - 使用明亮、易区分的颜色
        colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]

        # 为每个配置绘制响应时间趋势图
        for i, config in enumerate(data["configs"]):
            # 为每个配置选择一个颜色
            color = colors[i % len(colors)]

            config_stats = stats_df[stats_df["config_id"] == config.id]

            if not config_stats.empty:
                # 按分钟分组数据
                minute_groups = config_stats.groupby(
                    pd.Grouper(key="datetime", freq="1min")
                )

                # 提取时间和平均响应时间
                times = []
                avg_times = []

                for name, group in minute_groups:
                    if not group.empty:
                        times.append(name)
                        avg_times.append(group["avg_response_time"].mean())

                if times:
                    # 绘制实际数据点 - 使用与线条相同的颜色
                    plt.scatter(
                        times,
                        avg_times,
                        s=30,
                        color=color,
                        alpha=0.6,
                        label=f"{config.name} (actual data)",
                    )

                    # 绘制平滑曲线 - 使用与点相同的颜色
                    try:
                        import statsmodels.api as sm

                        # 如果数据点足够多，使用LOWESS进行平滑
                        if len(times) > 10:
                            x_numeric = np.arange(len(times))
                            lowess = sm.nonparametric.lowess(
                                avg_times, x_numeric, frac=0.3
                            )
                            # 使用相同的颜色但线条更粗
                            plt.plot(
                                times,
                                lowess[:, 1],
                                color=color,
                                linestyle="-",
                                linewidth=2.5,
                                label=f"{config.name} (smooth trend)",
                            )
                        else:
                            # 数据点较少时使用简单连线
                            plt.plot(
                                times,
                                avg_times,
                                color=color,
                                linestyle="-",
                                linewidth=2.5,
                                label=f"{config.name}",
                            )
                    except ImportError:
                        # 如果没有statsmodels，使用简单的移动平均
                        window = min(5, len(avg_times))
                        if window > 1:
                            smooth_avg = np.convolve(
                                avg_times, np.ones(window) / window, mode="valid"
                            )
                            # 计算合适的时间点，确保对齐
                            smooth_times = times[window - 1 :]
                            plt.plot(
                                smooth_times,
                                smooth_avg,
                                color=color,
                                linestyle="-",
                                linewidth=2.5,
                                label=f"{config.name} (smooth trend)",
                            )
                        else:
                            # 数据点太少，直接连线
                            plt.plot(
                                times,
                                avg_times,
                                color=color,
                                linestyle="-",
                                linewidth=2.5,
                                label=f"{config.name}",
                            )

        # 美化图表
        plt.title(
            f'average response time trend ({date.strftime("%Y-%m-%d")})', fontsize=16
        )
        plt.xlabel("time", fontsize=12)
        plt.ylabel("average response time (seconds)", fontsize=12)
        plt.grid(True, linestyle="--", alpha=0.7)

        # 优化X轴标签，避免拥挤
        ax = plt.gca()
        # 格式化x轴标签为小时:分钟
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        # 设置合适的刻度间隔
        hours = mdates.HourLocator()
        minutes = mdates.MinuteLocator(interval=15)  # 每15分钟一个刻度
        ax.xaxis.set_major_locator(hours)
        ax.xaxis.set_minor_locator(minutes)

        # 旋转标签以防重叠
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

        # 添加网格以提高可读性
        plt.grid(True, which="both", linestyle="--", alpha=0.5)

        # 添加图例 - 改进图例位置和样式
        legend = plt.legend(loc="best", fontsize=10, framealpha=0.7)
        legend.get_frame().set_edgecolor("lightgray")

        # 紧凑布局
        plt.tight_layout()

        # 保存图表
        response_time_chart = f"{chart_id}_resp_time.png"
        plt.savefig(os.path.join(charts_dir, response_time_chart), dpi=100)
        plt.close()

        # 生成成功率图表 - 使用类似方法并确保使用不同颜色
        plt.figure(figsize=(15, 8), dpi=100)

        for i, config in enumerate(data["configs"]):
            # 选择一个唯一的颜色
            color = colors[i % len(colors)]

            config_stats = stats_df[stats_df["config_id"] == config.id]

            if not config_stats.empty:
                # 按分钟分组数据
                minute_groups = config_stats.groupby(
                    pd.Grouper(key="datetime", freq="1min")
                )

                # 提取时间和成功率
                times = []
                success_rates = []

                for name, group in minute_groups:
                    if not group.empty:
                        times.append(name)
                        # 计算成功率
                        success_rate = (
                            (
                                group["success_count"].sum()
                                / group["call_count"].sum()
                                * 100
                            )
                            if group["call_count"].sum() > 0
                            else 0
                        )
                        success_rates.append(success_rate)

                if times:
                    # 绘制实际数据点 - 使用相同颜色
                    plt.scatter(
                        times,
                        success_rates,
                        s=30,
                        color=color,
                        alpha=0.6,
                        label=f"{config.name} (actual data)",
                    )

                    # 绘制平滑曲线 - 使用相同颜色
                    try:
                        import statsmodels.api as sm

                        if len(times) > 10:
                            x_numeric = np.arange(len(times))
                            lowess = sm.nonparametric.lowess(
                                success_rates, x_numeric, frac=0.3
                            )
                            plt.plot(
                                times,
                                lowess[:, 1],
                                color=color,
                                linestyle="-",
                                linewidth=2.5,
                                label=f"{config.name} (smooth trend)",
                            )
                        else:
                            plt.plot(
                                times,
                                success_rates,
                                color=color,
                                linestyle="-",
                                linewidth=2.5,
                                label=f"{config.name}",
                            )
                    except ImportError:
                        # 如果没有statsmodels，使用简单的移动平均
                        window = min(5, len(success_rates))
                        if window > 1:
                            smooth_rates = np.convolve(
                                success_rates, np.ones(window) / window, mode="valid"
                            )
                            smooth_times = times[window - 1 :]
                            plt.plot(
                                smooth_times,
                                smooth_rates,
                                color=color,
                                linestyle="-",
                                linewidth=2.5,
                                label=f"{config.name} (smooth trend)",
                            )
                        else:
                            plt.plot(
                                times,
                                success_rates,
                                color=color,
                                linestyle="-",
                                linewidth=2.5,
                                label=f"{config.name}",
                            )

        # 美化图表
        plt.title(f'call success rate trend ({date.strftime("%Y-%m-%d")})', fontsize=16)
        plt.xlabel("time", fontsize=12)
        plt.ylabel("success rate (%)", fontsize=12)
        plt.grid(True, linestyle="--", alpha=0.7)

        # 优化X轴标签
        ax = plt.gca()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(hours)
        ax.xaxis.set_minor_locator(minutes)

        # 旋转标签
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

        # Y轴范围设置为0-100%
        plt.ylim(0, 101)

        # 添加网格
        plt.grid(True, which="both", linestyle="--", alpha=0.5)

        # 添加图例 - 改进图例样式
        legend = plt.legend(loc="best", fontsize=10, framealpha=0.7)
        legend.get_frame().set_edgecolor("lightgray")

        # 紧凑布局
        plt.tight_layout()

        # 保存图表
        success_rate_chart = f"{chart_id}_success_rate.png"
        plt.savefig(os.path.join(charts_dir, success_rate_chart), dpi=100)
        plt.close()

        # 添加小时峰值响应时间图表 - 使用不同颜色
        plt.figure(figsize=(15, 6), dpi=100)

        for i, config in enumerate(data["configs"]):
            # 选择一个唯一的颜色
            color = colors[i % len(colors)]

            config_stats = stats_df[stats_df["config_id"] == config.id]

            if not config_stats.empty:
                # 提取小时
                config_stats["hour"] = config_stats["datetime"].dt.hour

                # 按小时分组并获取最大响应时间
                hourly_max = config_stats.groupby("hour")["max_response_time"].max()

                # 如果有数据，绘制柱状图
                if not hourly_max.empty:
                    hours = hourly_max.index
                    plt.bar(
                        [h + 0.1 * (i + 1) for h in hours],  # 轻微错开不同配置的柱状图
                        hourly_max.values,
                        width=0.2,
                        alpha=0.7,
                        color=color,
                        label=config.name,
                    )

        # 美化图表
        plt.title(
            f'hourly peak response time ({date.strftime("%Y-%m-%d")})', fontsize=16
        )
        plt.xlabel("hour", fontsize=12)
        plt.ylabel("peak response time (seconds)", fontsize=12)
        plt.grid(True, linestyle="--", alpha=0.7)

        # 设置X轴刻度
        plt.xticks(range(0, 24))

        # 添加网格
        plt.grid(True, axis="y", linestyle="--", alpha=0.5)

        # 添加图例 - 改进图例样式
        legend = plt.legend(loc="best", fontsize=10, framealpha=0.7)
        legend.get_frame().set_edgecolor("lightgray")

        # 紧凑布局
        plt.tight_layout()

        # 保存图表
        hourly_peak_chart = f"{chart_id}_hourly_peak.png"
        plt.savefig(os.path.join(charts_dir, hourly_peak_chart), dpi=100)
        plt.close()

        # 返回图表路径
        charts["response_time_chart"] = os.path.join("charts", response_time_chart)
        charts["success_rate_chart"] = os.path.join("charts", success_rate_chart)
        charts["hourly_peak_chart"] = os.path.join("charts", hourly_peak_chart)

        # 新增：1. 响应时间分布热图
        charts["response_time_heatmap"] = self._generate_response_time_heatmap(
            stats_df, date, chart_id, charts_dir, data["configs"]
        )

        # 新增：2. 状态码分布图
        charts["status_code_chart"] = self._generate_status_code_chart(
            data, date, chart_id, charts_dir
        )

        # 新增：3. 性能趋势对比图
        charts["performance_comparison"] = self._generate_performance_comparison(
            stats_df, date, chart_id, charts_dir, data["configs"]
        )

        # 新增：4. 可用性雷达图
        charts["availability_radar"] = self._generate_availability_radar(
            stats_df, date, chart_id, charts_dir, data["configs"]
        )

        # 新增：5. 每日对比图（如果有历史数据）
        past_days = 7
        charts["daily_comparison"] = self._generate_daily_comparison(
            date, chart_id, charts_dir, data["configs"], past_days
        )

        return charts

    def _generate_response_time_heatmap(
        self, stats_df, date, chart_id, charts_dir, configs
    ):
        """生成响应时间分布热图"""
        if stats_df.empty:
            return None

        try:
            import seaborn as sns

            # 创建图形
            plt.figure(figsize=(15, 8))

            # 准备热图数据
            stats_df["hour"] = stats_df["datetime"].dt.hour
            stats_df["minute_group"] = (
                stats_df["datetime"].dt.minute // 10
            ) * 10  # 10分钟一组

            # 对于每个配置创建一个热图
            for i, config in enumerate(configs):
                plt.subplot(len(configs), 1, i + 1)

                config_stats = stats_df[stats_df["config_id"] == config.id]
                if not config_stats.empty:
                    # 聚合数据
                    heatmap_data = config_stats.pivot_table(
                        index="minute_group",
                        columns="hour",
                        values="avg_response_time",
                        aggfunc="mean",
                    ).fillna(0)

                    # 绘制热图
                    sns.heatmap(
                        heatmap_data,
                        cmap="YlOrRd",
                        annot=False,
                        fmt=".2f",
                        cbar_kws={"label": "average response time (seconds)"},
                    )

                    plt.title(f"{config.name} - response time heatmap")
                    plt.xlabel("hour")
                    plt.ylabel("minute (10 minutes group)")

            plt.tight_layout()

            # 保存图表
            heatmap_file = f"{chart_id}_resp_heatmap.png"
            plt.savefig(os.path.join(charts_dir, heatmap_file), dpi=100)
            plt.close()

            return os.path.join("charts", heatmap_file)
        except Exception as e:
            logger.warning(f"生成热图时出错: {str(e)}")
            return None

    def _generate_status_code_chart(self, data, date, chart_id, charts_dir):
        """生成状态码分布图"""
        try:
            # 获取状态码数据
            status_data = {}

            # 从数据库获取状态码分布
            with repository.get_connection() as conn:
                cursor = conn.cursor()
                for config in data["configs"]:
                    cursor.execute(
                        """
                        SELECT status_code, COUNT(*) as count 
                        FROM call_details 
                        WHERE date(timestamp) = ? AND config_id = ?
                        GROUP BY status_code
                        ORDER BY count DESC
                    """,
                        (date.isoformat(), config.id),
                    )

                    status_data[config.name] = {
                        row["status_code"]: row["count"] for row in cursor.fetchall()
                    }

            if not status_data or all(not codes for codes in status_data.values()):
                return None

            # 创建图形
            plt.figure(figsize=(15, 8))

            # 设置颜色映射
            colors = {
                "2xx": "#2ca02c",  # 成功 - 绿色
                "3xx": "#1f77b4",  # 重定向 - 蓝色
                "4xx": "#ff7f0e",  # 客户端错误 - 橙色
                "5xx": "#d62728",  # 服务器错误 - 红色
                "other": "#7f7f7f",  # 其他 - 灰色
            }

            # 创建子图
            fig, axes = plt.subplots(
                len(status_data), 1, figsize=(15, 5 * len(status_data))
            )
            if len(status_data) == 1:
                axes = [axes]

            for i, (config_name, codes) in enumerate(status_data.items()):
                ax = axes[i]

                # 状态码分组
                grouped_codes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0}

                for code, count in codes.items():
                    if 200 <= code < 300:
                        grouped_codes["2xx"] += count
                    elif 300 <= code < 400:
                        grouped_codes["3xx"] += count
                    elif 400 <= code < 500:
                        grouped_codes["4xx"] += count
                    elif 500 <= code < 600:
                        grouped_codes["5xx"] += count
                    else:
                        grouped_codes["other"] += count

                # 过滤掉计数为0的分组
                grouped_codes = {k: v for k, v in grouped_codes.items() if v > 0}

                # 计算百分比
                total = sum(grouped_codes.values())
                percentages = {k: (v / total) * 100 for k, v in grouped_codes.items()}

                # 绘制饼图
                wedges, texts, autotexts = ax.pie(
                    percentages.values(),
                    labels=percentages.keys(),
                    autopct="%1.1f%%",
                    colors=[colors[code] for code in percentages.keys()],
                    startangle=90,
                    wedgeprops={"edgecolor": "w", "linewidth": 1},
                )

                # 美化文本
                for text in texts:
                    text.set_fontsize(12)
                for autotext in autotexts:
                    autotext.set_fontsize(10)
                    autotext.set_color("white")

                ax.set_title(f"{config_name} - status code distribution", fontsize=14)

                # 添加图例
                legend_labels = [
                    f"{code} ({count} times)" for code, count in grouped_codes.items()
                ]
                ax.legend(
                    wedges,
                    legend_labels,
                    loc="center left",
                    bbox_to_anchor=(1, 0, 0.5, 1),
                )

            plt.tight_layout()

            # 保存图表
            status_code_file = f"{chart_id}_status_codes.png"
            plt.savefig(os.path.join(charts_dir, status_code_file), dpi=100)
            plt.close()

            return os.path.join("charts", status_code_file)
        except Exception as e:
            logger.warning(f"生成状态码图表时出错: {str(e)}")
            return None

    def _generate_performance_comparison(
        self, stats_df, date, chart_id, charts_dir, configs
    ):
        """生成性能趋势对比图"""
        if stats_df.empty:
            return None

        try:
            # 创建图形
            plt.figure(figsize=(15, 12))

            # 定义颜色循环
            colors = [
                "#1f77b4",
                "#ff7f0e",
                "#2ca02c",
                "#d62728",
                "#9467bd",
                "#8c564b",
                "#e377c2",
                "#7f7f7f",
                "#bcbd22",
                "#17becf",
            ]

            # 创建四个子图
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))

            # 1. 平均响应时间对比
            ax1 = axes[0, 0]
            for i, config in enumerate(configs):
                color = colors[i % len(colors)]
                config_stats = stats_df[stats_df["config_id"] == config.id]

                if not config_stats.empty:
                    # 按小时分组
                    config_stats["hour"] = config_stats["datetime"].dt.hour
                    hourly_avg = config_stats.groupby("hour")[
                        "avg_response_time"
                    ].mean()

                    ax1.plot(
                        hourly_avg.index,
                        hourly_avg.values,
                        "-o",
                        color=color,
                        linewidth=2,
                        label=config.name,
                    )

            ax1.set_title("average response time comparison", fontsize=14)
            ax1.set_xlabel("hour", fontsize=12)
            ax1.set_ylabel("average response time (seconds)", fontsize=12)
            ax1.grid(True, linestyle="--", alpha=0.7)
            ax1.legend()

            # 2. 成功率对比
            ax2 = axes[0, 1]
            for i, config in enumerate(configs):
                color = colors[i % len(colors)]
                config_stats = stats_df[stats_df["config_id"] == config.id]

                if not config_stats.empty:
                    # 按小时分组
                    config_stats["hour"] = config_stats["datetime"].dt.hour
                    hourly_success = config_stats.groupby("hour").apply(
                        lambda x: (
                            x["success_count"].sum() / x["call_count"].sum() * 100
                        )
                        if x["call_count"].sum() > 0
                        else 0
                    )

                    ax2.plot(
                        hourly_success.index,
                        hourly_success.values,
                        "-o",
                        color=color,
                        linewidth=2,
                        label=config.name,
                    )

            ax2.set_title("success rate comparison", fontsize=14)
            ax2.set_xlabel("hour", fontsize=12)
            ax2.set_ylabel("success rate (%)", fontsize=12)
            ax2.set_ylim(0, 105)  # 留一点空间在顶部
            ax2.grid(True, linestyle="--", alpha=0.7)
            ax2.legend()

            # 3. 响应时间稳定性 (用标准差表示)
            ax3 = axes[1, 0]
            for i, config in enumerate(configs):
                color = colors[i % len(colors)]
                config_stats = stats_df[stats_df["config_id"] == config.id]

                if not config_stats.empty:
                    # 计算每小时响应时间的标准差
                    config_stats["hour"] = config_stats["datetime"].dt.hour
                    hourly_std = (
                        config_stats.groupby("hour")["avg_response_time"]
                        .std()
                        .fillna(0)
                    )

                    ax3.bar(
                        hourly_std.index
                        + (i * 0.2 - (len(configs) - 1) * 0.1),  # 将柱状图错开
                        hourly_std.values,
                        width=0.2,
                        color=color,
                        alpha=0.7,
                        label=config.name,
                    )

            ax3.set_title("response time stability (standard deviation)", fontsize=14)
            ax3.set_xlabel("hour", fontsize=12)
            ax3.set_ylabel("standard deviation (seconds)", fontsize=12)
            ax3.set_xticks(range(0, 24))
            ax3.grid(True, linestyle="--", alpha=0.7, axis="y")
            ax3.legend()

            # 4. 调用量对比
            ax4 = axes[1, 1]
            for i, config in enumerate(configs):
                color = colors[i % len(colors)]
                config_stats = stats_df[stats_df["config_id"] == config.id]

                if not config_stats.empty:
                    # 按小时分组
                    config_stats["hour"] = config_stats["datetime"].dt.hour
                    hourly_calls = config_stats.groupby("hour")["call_count"].sum()

                    ax4.bar(
                        hourly_calls.index + (i * 0.2 - (len(configs) - 1) * 0.1),
                        hourly_calls.values,
                        width=0.2,
                        color=color,
                        alpha=0.7,
                        label=config.name,
                    )

            ax4.set_title("hourly call count", fontsize=14)
            ax4.set_xlabel("hour", fontsize=12)
            ax4.set_ylabel("call count", fontsize=12)
            ax4.set_xticks(range(0, 24))
            ax4.grid(True, linestyle="--", alpha=0.7, axis="y")
            ax4.legend()

            plt.tight_layout()

            # 保存图表
            comparison_file = f"{chart_id}_performance_comparison.png"
            plt.savefig(os.path.join(charts_dir, comparison_file), dpi=100)
            plt.close()

            return os.path.join("charts", comparison_file)
        except Exception as e:
            logger.warning(f"生成性能对比图表时出错: {str(e)}")
            return None

    def _generate_availability_radar(
        self, stats_df, date, chart_id, charts_dir, configs
    ):
        """生成可用性雷达图"""
        if stats_df.empty:
            return None

        try:
            # 创建图形
            plt.figure(figsize=(10, 10))

            # 定义颜色循环
            colors = [
                "#1f77b4",
                "#ff7f0e",
                "#2ca02c",
                "#d62728",
                "#9467bd",
                "#8c564b",
                "#e377c2",
                "#7f7f7f",
                "#bcbd22",
                "#17becf",
            ]

            # 定义雷达图的轴（早上、上午、下午、晚上、凌晨）
            categories = [
                "morning (6-9am)",
                "morning (9-12am)",
                "afternoon (12-18pm)",
                "evening (18-24pm)",
                "night (0-6am)",
            ]
            N = len(categories)

            # 设置雷达图
            angles = [n / float(N) * 2 * np.pi for n in range(N)]
            angles += angles[:1]  # 闭合雷达图

            ax = plt.subplot(111, polar=True)

            # 设置雷达图的第一个轴在顶部
            ax.set_theta_offset(np.pi / 2)
            ax.set_theta_direction(-1)

            # 绘制轴标签
            plt.xticks(angles[:-1], categories)

            # 设置y轴范围
            ax.set_ylim(0, 100)
            ax.set_yticks([20, 40, 60, 80, 100])
            ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"])

            # 为每个配置计算并绘制可用性数据
            for i, config in enumerate(configs):
                color = colors[i % len(colors)]
                config_stats = stats_df[stats_df["config_id"] == config.id]

                if not config_stats.empty:
                    # 将时间分组到不同时段
                    config_stats["hour"] = config_stats["datetime"].dt.hour
                    config_stats["time_period"] = pd.cut(
                        config_stats["hour"],
                        bins=[-1, 5, 8, 11, 17, 23],
                        labels=[4, 0, 1, 2, 3],  # 映射到雷达图轴的索引
                    )

                    # 计算每个时段的可用性
                    availability = []
                    for period in range(5):  # 5个时段
                        period_stats = config_stats[
                            config_stats["time_period"] == period
                        ]
                        if not period_stats.empty:
                            avail = (
                                (
                                    period_stats["success_count"].sum()
                                    / period_stats["call_count"].sum()
                                    * 100
                                )
                                if period_stats["call_count"].sum() > 0
                                else 0
                            )
                            availability.append(avail)
                        else:
                            availability.append(0)

                    # 闭合雷达图数据
                    availability += availability[:1]

                    # 绘制雷达图
                    ax.plot(
                        angles,
                        availability,
                        linewidth=2,
                        linestyle="solid",
                        color=color,
                        label=config.name,
                    )
                    ax.fill(angles, availability, color=color, alpha=0.1)

            # 添加图例
            plt.legend(loc="upper right", bbox_to_anchor=(0.1, 0.1))

            plt.title("availability in different time periods (%)", size=15, y=1.1)

            # 保存图表
            radar_file = f"{chart_id}_availability_radar.png"
            plt.savefig(os.path.join(charts_dir, radar_file), dpi=100)
            plt.close()

            return os.path.join("charts", radar_file)
        except Exception as e:
            logger.warning(f"生成可用性雷达图时出错: {str(e)}")
            return None

    def _generate_daily_comparison(
        self, date, chart_id, charts_dir, configs, past_days=7
    ):
        """生成过去几天的性能对比图"""
        try:
            # 获取过去几天的日期
            dates = [date - datetime.timedelta(days=i) for i in range(past_days)]
            dates.reverse()  # 按时间升序排列

            # 为每个配置收集每天的平均响应时间和成功率
            daily_data = {
                config.id: {"name": config.name, "avg_times": [], "success_rates": []}
                for config in configs
            }
            dates_str = [d.strftime("%m-%d") for d in dates]

            # 查询每天数据
            for day in dates:
                for config in configs:
                    with repository.get_connection() as conn:
                        cursor = conn.cursor()

                        # 查询平均响应时间
                        cursor.execute(
                            """
                            SELECT AVG(avg_response_time) as avg_time
                            FROM minute_stats
                            WHERE date(start_time) = ? AND config_id = ?
                        """,
                            (day.isoformat(), config.id),
                        )
                        result = cursor.fetchone()
                        avg_time = (
                            result["avg_time"]
                            if result and result["avg_time"] is not None
                            else 0
                        )

                        # 查询成功率
                        cursor.execute(
                            """
                            SELECT SUM(success_count) as successes, SUM(call_count) as total
                            FROM minute_stats
                            WHERE date(start_time) = ? AND config_id = ?
                        """,
                            (day.isoformat(), config.id),
                        )
                        result = cursor.fetchone()
                        success_rate = (
                            (result["successes"] / result["total"] * 100)
                            if result and result["total"] > 0
                            else 0
                        )

                        # 存储数据
                        daily_data[config.id]["avg_times"].append(avg_time)
                        daily_data[config.id]["success_rates"].append(success_rate)

            # 检查是否有足够数据绘图
            has_data = any(len(data["avg_times"]) > 0 for data in daily_data.values())
            if not has_data:
                return None

            # 创建图表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

            # 定义颜色循环
            colors = [
                "#1f77b4",
                "#ff7f0e",
                "#2ca02c",
                "#d62728",
                "#9467bd",
                "#8c564b",
                "#e377c2",
                "#7f7f7f",
                "#bcbd22",
                "#17becf",
            ]

            # 绘制平均响应时间趋势
            for i, (config_id, data) in enumerate(daily_data.items()):
                color = colors[i % len(colors)]
                ax1.plot(
                    dates_str,
                    data["avg_times"],
                    marker="o",
                    color=color,
                    linewidth=2,
                    label=data["name"],
                )

            ax1.set_title("daily average response time trend", fontsize=14)
            ax1.set_xlabel("date", fontsize=12)
            ax1.set_ylabel("average response time (seconds)", fontsize=12)
            ax1.grid(True, linestyle="--", alpha=0.7)
            ax1.legend()

            # 绘制成功率趋势
            for i, (config_id, data) in enumerate(daily_data.items()):
                color = colors[i % len(colors)]
                ax2.plot(
                    dates_str,
                    data["success_rates"],
                    marker="o",
                    color=color,
                    linewidth=2,
                    label=data["name"],
                )

            ax2.set_title("daily success rate trend", fontsize=14)
            ax2.set_xlabel("date", fontsize=12)
            ax2.set_ylabel("success rate (%)", fontsize=12)
            ax2.set_ylim(0, 105)
            ax2.grid(True, linestyle="--", alpha=0.7)
            ax2.legend()

            plt.tight_layout()

            # 保存图表
            daily_file = f"{chart_id}_daily_comparison.png"
            plt.savefig(os.path.join(charts_dir, daily_file), dpi=100)
            plt.close()

            return os.path.join("charts", daily_file)
        except Exception as e:
            logger.warning(f"generate daily comparison chart error: {str(e)}")
            return None
