# 构建阶段
FROM python:3.9-slim AS builder

WORKDIR /app

RUN ls -lah dist

# 复制 wheel 包 - 更改为通配符匹配多种可能位置
COPY dist/*.whl ./ 2>/dev/null || true
COPY python-package/*.whl ./ 2>/dev/null || true
COPY *.whl ./ 2>/dev/null || true

# 确保找到了 wheel 文件
RUN if [ -z "$(ls -A *.whl 2>/dev/null)" ]; then \
        echo "Error: No wheel files found!"; \
        exit 1; \
    fi

# 安装项目及依赖到特定目录
RUN pip install --no-cache-dir --target=/install *.whl

# 最终镜像 - 使用轻量级基础镜像
FROM python:3.9-slim

WORKDIR /app

# 复制已安装的包
COPY --from=builder /install /usr/local/lib/python3.9/site-packages

# 确保入口点脚本可用
COPY --from=builder /install/bin/websvc-monitor /usr/local/bin/ 2>/dev/null || true 
COPY --from=builder /install/Scripts/websvc-monitor /usr/local/bin/ 2>/dev/null || true
RUN chmod +x /usr/local/bin/websvc-monitor 2>/dev/null || echo "Warning: Could not find websvc-monitor script"

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/reports /app/config

# 设置环境变量
ENV WEBSVC_MONITOR_DB_PATH=/app/data/webservice_monitor.db
ENV WEBSVC_MONITOR_LOG_DIR=/app/logs
ENV WEBSVC_MONITOR_REPORT_DIR=/app/reports
ENV PYTHONPATH=/usr/local/lib/python3.9/site-packages

# 暴露配置目录为卷
VOLUME ["/app/data", "/app/logs", "/app/reports", "/app/config"]

# 设置用户为非 root
RUN useradd -m monitor 2>/dev/null || adduser --disabled-password --gecos "" monitor
RUN chown -R monitor:monitor /app

USER monitor

# 入口点
ENTRYPOINT ["websvc-monitor"]
CMD ["--help"] 
