# 构建阶段
FROM python:3.9-slim AS builder

WORKDIR /app

# 创建一个标记文件夹来检查wheel包是否成功复制
RUN mkdir -p /tmp/wheel_check

# 复制 wheel 包 - 使用通配符匹配多种可能位置
COPY dist/*.whl /tmp/wheel_check/ 2>/dev/null || echo "No wheel files in dist/"
COPY python-package/*.whl /tmp/wheel_check/ 2>/dev/null || echo "No wheel files in python-package/"
COPY *.whl /tmp/wheel_check/ 2>/dev/null || echo "No wheel files in root directory"

# 复制源代码（作为备选安装方式）
COPY webservice_monitor/ /app/webservice_monitor/ 2>/dev/null || echo "No source code directory found"
COPY setup.py README.md /app/ 2>/dev/null || echo "No setup files found"

# 安装脚本 - 尝试从wheel或源代码安装
COPY /app/install.sh <<EOF
#!/bin/sh
set -e

if find /tmp/wheel_check -name "*.whl" | grep . > /dev/null; then
    echo "Found wheel files, installing from wheels"
    cp /tmp/wheel_check/*.whl ./
    pip install --no-cache-dir --target=/install *.whl
elif [ -f "/app/setup.py" ]; then
    echo "No wheel files found, installing from source"
    pip install --no-cache-dir --target=/install .
else
    echo "ERROR: No installation method available!"
    echo "Please provide either wheel files or source code"
    exit 1
fi
EOF

RUN chmod +x /app/install.sh && /app/install.sh

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
