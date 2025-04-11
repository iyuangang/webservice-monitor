# 构建阶段
FROM python:3.9-slim AS builder

WORKDIR /app

# 安装必要的工具
RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*

# 创建一个标记文件夹来检查wheel包和zip包
RUN mkdir -p /tmp/wheel_check /tmp/zip_extract

# 复制 wheel 包 - 使用通配符匹配多种可能位置
COPY dist/*.whl /tmp/wheel_check/ 2>/dev/null || echo "No wheel files in dist/"
COPY python-package/*.whl /tmp/wheel_check/ 2>/dev/null || echo "No wheel files in python-package/"
COPY *.whl /tmp/wheel_check/ 2>/dev/null || echo "No wheel files in root directory"

# 复制并解压zip文件
COPY dist/*.zip /tmp/ 2>/dev/null || echo "No zip files in dist/"
COPY python-package/*.zip /tmp/ 2>/dev/null || echo "No zip files in python-package/"
COPY *.zip /tmp/ 2>/dev/null || echo "No zip files in root directory"

# 添加调试信息 - 列出目录内容
RUN echo "==== Listing all available files ====" &&
    ls -la /tmp/ &&
    ls -la dist/ 2>/dev/null || echo "dist/ directory not found" &&
    ls -la python-package/ 2>/dev/null || echo "python-package/ directory not found"

# 解压zip文件并查找wheel包
RUN echo "==== Extracting zip files ====" &&
    find /tmp -maxdepth 1 -name "*.zip" -exec sh -c 'echo "Extracting {}"; unzip -o {} -d /tmp/zip_extract' \; 2>/dev/null || echo "No zip files found or could not extract" &&
    echo "==== Looking for wheel files in extracted contents ====" &&
    find /tmp/zip_extract -type f -name "*.whl" -exec sh -c 'echo "Found wheel file: {}"; cp {} /tmp/wheel_check/' \; 2>/dev/null || echo "No wheel files found in zip archives"

# 复制源代码（作为备选安装方式）
COPY webservice_monitor/ /app/webservice_monitor/ 2>/dev/null || echo "No source code directory found"
COPY setup.py README.md /app/ 2>/dev/null || echo "No setup files found"

# 创建安装脚本 - 尝试从wheel或源代码安装
RUN echo '#!/bin/sh' >/app/install.sh &&
    echo 'set -e' >>/app/install.sh &&
    echo '' >>/app/install.sh &&
    echo 'echo "==== Available wheel files ====" ' >>/app/install.sh &&
    echo 'find /tmp/wheel_check -type f -name "*.whl" -exec ls -la {} \;' >>/app/install.sh &&
    echo '' >>/app/install.sh &&
    echo 'if find /tmp/wheel_check -name "*.whl" | grep . > /dev/null; then' >>/app/install.sh &&
    echo '    echo "Found wheel files, installing from wheels"' >>/app/install.sh &&
    echo '    cp /tmp/wheel_check/*.whl ./' >>/app/install.sh &&
    echo '    pip install --no-cache-dir --target=/install *.whl' >>/app/install.sh &&
    echo 'elif [ -f "/app/setup.py" ]; then' >>/app/install.sh &&
    echo '    echo "No wheel files found, installing from source"' >>/app/install.sh &&
    echo '    echo "==== Contents of setup.py ====" ' >>/app/install.sh &&
    echo '    cat /app/setup.py' >>/app/install.sh &&
    echo '    pip install --no-cache-dir --target=/install .' >>/app/install.sh &&
    echo 'else' >>/app/install.sh &&
    echo '    echo "ERROR: No installation method available!"' >>/app/install.sh &&
    echo '    echo "Please provide either wheel files or source code"' >>/app/install.sh &&
    echo '    exit 1' >>/app/install.sh &&
    echo 'fi' >>/app/install.sh &&
    chmod +x /app/install.sh &&
    /app/install.sh

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
