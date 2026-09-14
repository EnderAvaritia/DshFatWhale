# -*- coding: utf-8 -*-
"""log.py —— 统一日志（logs/whale.log，1MB × 3 轮转）。

桌宠类程序最常见的故障是"静默失败"：源码运行在 pythonw 下、打包后运行在 exe 里，
两者都没有控制台，print 等于丢弃。因此任何"用户看不到"的异常都必须落到这个文件。
日志不可写时（只读目录等）自动降级为无操作，绝不影响主流程。
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOGGER_NAME = "whale"
_logger = None


def log_dir() -> str:
    import config  # 延迟导入：避免 config <-> log 循环引用

    return os.path.join(config.app_dir(), "logs")


def log_path() -> str:
    return os.path.join(log_dir(), "whale.log")


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        os.makedirs(log_dir(), exist_ok=True)
        handler = RotatingFileHandler(log_path(), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    except OSError:
        # 日志不可用不能影响程序：吞掉并静默
        logger.addHandler(logging.NullHandler())
    _logger = logger
    return _logger
