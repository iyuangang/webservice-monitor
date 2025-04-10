"""
PDF报告生成
"""

import os
import logging
import datetime
from typing import Optional

from webservice_monitor.reports.html_generator import HTMLReportGenerator
from webservice_monitor.utils.config import get_setting

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """PDF报告生成器"""

    def __init__(self):
        """初始化PDF报告生成器"""
        self.html_generator = HTMLReportGenerator()
        self.report_dir = get_setting("REPORT_DIR", "reports")

        # 确保报告目录存在
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)

    def generate_report(
        self, date: datetime.date, config_id: Optional[int] = None
    ) -> str:
        """生成PDF报告并返回文件路径"""
        # 先生成HTML报告
        html_path = self.html_generator.generate_report(date, config_id)

        # 生成PDF文件名
        pdf_filename = os.path.splitext(os.path.basename(html_path))[0] + ".pdf"
        pdf_path = os.path.join(self.report_dir, pdf_filename)

        try:
            # 尝试导入WeasyPrint
            from weasyprint import HTML

            # 将HTML转换为PDF
            HTML(html_path).write_pdf(pdf_path)
            logger.info(f"已生成PDF报告: {pdf_path}")

            return pdf_path
        except ImportError:
            logger.warning("未安装WeasyPrint库，无法生成PDF报告")
            return html_path
        except Exception as e:
            logger.exception(f"生成PDF报告时出错: {str(e)}")
            return html_path
