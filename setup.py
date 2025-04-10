#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


def package_files(directory):
    paths = []
    for path, directories, filenames in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join("..", path, filename))
    return paths


extra_files = package_files("webservice_monitor/scripts")

setup(
    name="webservice-monitor",
    version="2.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="监控多个WebService接口的性能和可用性",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/webservice-monitor",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "webservice_monitor.config": ["templates/*.html"],
        "webservice_monitor": extra_files,
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.25.0",
        "click>=8.0.0",
        "weasyprint>=53.0",
        "tabulate>=0.8.9",
        "pandas>=1.3.0",
        "matplotlib>=3.4.0",
        "jinja2>=3.0.0",
        "psutil>=5.9.0",
        "numpy>=1.20.0",
        "statsmodels>=0.13.0",
        "seaborn>=0.11.0",
    ],
    entry_points={
        "console_scripts": [
            "websvc-monitor=webservice_monitor.__main__:main",
        ],
    },
)
