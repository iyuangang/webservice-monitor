"""
接口调用实现
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple

import requests

from webservice_monitor.db.models import CallDetail, Configuration

logger = logging.getLogger(__name__)


class WebServiceCaller:
    """WebService调用实现类"""

    @staticmethod
    def call(config: Configuration) -> CallDetail:
        """调用WebService接口并返回结果"""
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
        except requests.exceptions.Timeout:
            call_detail.status_code = -1
            call_detail.error_message = "请求超时"
        except requests.exceptions.ConnectionError:
            call_detail.status_code = -1
            call_detail.error_message = "连接错误"
        except Exception as e:
            call_detail.status_code = -1
            call_detail.error_message = str(e)

        call_detail.response_time = time.time() - start_time
        return call_detail

    @staticmethod
    def test_connection(
        url: str,
        method: str = "GET",
        headers: Dict = None,
        payload: str = None,
        timeout: int = 10,
    ) -> Tuple[bool, str, float]:
        """测试连接，返回(成功标志, 消息, 响应时间)"""
        headers = headers or {"Content-Type": "application/xml; charset=utf-8"}

        start_time = time.time()
        try:
            if method.upper() == "POST":
                response = requests.post(
                    url, data=payload, headers=headers, timeout=timeout
                )
            else:
                response = requests.get(url, headers=headers, timeout=timeout)

            response_time = time.time() - start_time

            if 200 <= response.status_code < 300:
                return True, f"连接成功，状态码: {response.status_code}", response_time
            else:
                return (
                    False,
                    f"请求返回非成功状态码: {response.status_code}",
                    response_time,
                )

        except requests.exceptions.Timeout:
            return False, "请求超时", time.time() - start_time
        except requests.exceptions.ConnectionError:
            return False, "连接错误，请检查URL是否正确", time.time() - start_time
        except Exception as e:
            return False, f"请求错误: {str(e)}", time.time() - start_time
