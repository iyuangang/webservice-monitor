"""
监控模块的单元测试
"""

import unittest
from unittest.mock import patch, MagicMock

from webservice_monitor.core.monitor import WebServiceMonitor
from webservice_monitor.db.models import Configuration, CallDetail


class TestWebServiceMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = WebServiceMonitor()
        self.test_config = Configuration(
            id=1,
            name="Test API",
            url="http://example.com/test",
            method="GET",
            call_interval=5,
            timeout=10,
            alert_threshold=2.0,
        )

    @patch("webservice_monitor.core.monitor.WebServiceCaller.call")
    def test_call_webservice(self, mock_call):
        # 设置模拟返回值
        mock_call_detail = CallDetail(status_code=200, response_time=0.5, config_id=1)
        mock_call.return_value = mock_call_detail

        # 调用被测方法
        result = self.monitor.call_webservice(self.test_config)

        # 验证结果
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.response_time, 0.5)

        # 验证调用
        mock_call.assert_called_once_with(self.test_config)

    def test_is_in_monitoring_hours(self):
        # 测试全天监控
        self.test_config.monitoring_hours = "0-23"
        self.assertTrue(self.monitor._is_in_monitoring_hours(self.test_config))

        # 测试工作时间监控
        self.test_config.monitoring_hours = "9-17"

        with patch("webservice_monitor.core.monitor.datetime") as mock_datetime:
            # 设置为工作时间内
            mock_now = MagicMock()
            mock_now.hour = 14
            mock_datetime.datetime.now.return_value = mock_now

            self.assertTrue(self.monitor._is_in_monitoring_hours(self.test_config))

            # 设置为工作时间外
            mock_now.hour = 20
            self.assertFalse(self.monitor._is_in_monitoring_hours(self.test_config))

        # 测试跨天时间段
        self.test_config.monitoring_hours = "22-6"

        with patch("webservice_monitor.core.monitor.datetime") as mock_datetime:
            # 设置为夜间
            mock_now = MagicMock()
            mock_now.hour = 23
            mock_datetime.datetime.now.return_value = mock_now

            self.assertTrue(self.monitor._is_in_monitoring_hours(self.test_config))

            # 设置为白天
            mock_now.hour = 12
            self.assertFalse(self.monitor._is_in_monitoring_hours(self.test_config))


if __name__ == "__main__":
    unittest.main()
