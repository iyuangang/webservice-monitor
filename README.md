# WebService监控工具

一个强大的WebService接口监控工具，用于监控多个Web服务接口的性能和可用性。

## 功能特点

- 监控多个WebService接口的响应时间和可用性
- 支持GET和POST请求，包括XML有效载荷
- 根据自定义阈值生成可用性和性能告警
- 生成每日HTML和PDF格式的详细报告
- 配置灵活的监控调度，包括时间段设置
- 通过CLI管理监控配置、告警和报告
- 将监控数据存储到SQLite数据库
- 数据老化和自动清理功能

## 系统要求

- Python 3.7+
- 依赖项 (详见 `requirements.txt`)

## 安装

1. 克隆或下载仓库:

```bash
git clone https://github.com/yourusername/webservice-monitor.git
cd webservice-monitor
```

2. 安装依赖:

```bash
pip install -r requirements.txt
```

3. 安装包:

```bash
pip install -e .
```

## 使用方法

### 配置管理

```bash
# 添加新配置
websvc-monitor config add -n "API服务" -u "http://api.example.com/status" -m GET

# 查看所有配置
websvc-monitor config list

# 查看单个配置详情
websvc-monitor config show 1

# 启用配置
websvc-monitor config enable 1

# 禁用配置
websvc-monitor config disable 1

# 删除配置
websvc-monitor config delete 1

# 导入配置
websvc-monitor config import configs.json

# 导出配置
websvc-monitor config export exported_configs.json --active-only
```

### 监控管理

```bash
# 启动监控
websvc-monitor start

# 启动特定配置的监控
websvc-monitor start -c 1,2,3

# 停止监控
websvc-monitor stop

# 检查监控状态
websvc-monitor status

# 重新加载配置
websvc-monitor reload
```

### 报告生成

```bash
# 生成昨日HTML报告
websvc-monitor report generate

# 生成特定日期的报告
websvc-monitor report generate -d 2023-12-01

# 生成特定配置的PDF报告
websvc-monitor report generate -c 1 -f pdf
```

### 告警管理

```bash
# 查看所有活跃告警
websvc-monitor alert list

# 查看特定配置的告警
websvc-monitor alert list -c 1

# 解决告警
websvc-monitor alert resolve 5
```

### 数据管理

```bash
# 清理30天前的数据
websvc-monitor cleanup

# 清理60天前的数据
websvc-monitor cleanup -d 60
```

### 测试连接

```bash
# 测试简单GET请求
websvc-monitor test -u "http://api.example.com/status"

# 测试POST请求
websvc-monitor test -u "http://api.example.com/api" -m POST -p "<xml>测试</xml>" -h '{"Content-Type": "application/xml"}'

# 测试并重复多次
websvc-monitor test -u "http://api.example.com/status" -r 5
```

## 配置文件

工具可以使用JSON配置文件设置全局配置。默认配置文件路径:

- `./config.json`
- `~/.webservice_monitor/config.json`
- `/etc/webservice_monitor/config.json`

也可以通过环境变量设置，格式为 `WEBSVC_MONITOR_[SETTING]`。

## 目录结构

- `webservice_monitor/`: 主要的包目录
  - `cli/`: 命令行界面模块
  - `core/`: 核心功能模块
  - `db/`: 数据库模块
  - `reports/`: 报告生成模块
  - `utils/`: 工具模块
  - `config/`: 配置和模板

## 贡献

欢迎提交问题和拉取请求。对于重大更改，请先开issue讨论变更内容。

## 许可证

MIT
