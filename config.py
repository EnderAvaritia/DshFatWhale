# -*- coding: utf-8 -*-
"""config.py —— config.json 读写与路径解析。

数据文件与程序同级存放（便携、可手改），与 DSH 完全解耦。
Key 读取通道：环境变量 DEEPSEEK_API_KEY 优先，其次 config.json。
"""
import json
import os
import shutil
import sys


def app_dir() -> str:
    """程序所在目录：源码运行时为脚本目录，PyInstaller 打包后为 exe 目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundle_dir() -> str:
    """资源目录：源码运行与打包后一致（PyInstaller onefile 解包目录）。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", app_dir())
    return os.path.dirname(os.path.abspath(__file__))


def assets_dir() -> str:
    return os.path.join(bundle_dir(), "assets")


CONFIG_PATH = os.path.join(app_dir(), "config.json")
LEDGER_PATH = os.path.join(app_dir(), ".dshw-usage.json")
LINES_PATH = os.path.join(app_dir(), "台词表.md")
BUNDLED_LINES_PATH = os.path.join(bundle_dir(), "台词表.md")

DEFAULTS = {
    # 用量模式：ledger（小鲸鱼记账，默认）/ token（实时·令牌）
    "usage_mode": "ledger",
    # 常驻余额气泡（余额+今日已用+峰谷时段），右键菜单可关
    "persistent_bubble": True,
    # 显示大小档位
    "size": 1.0,
    # 音效
    "sound_set": "duck",   # duck（小黄鸭）/ fx1（音效1）
    "vol": 0.9,
    "sound_on": True,
    # 凭据（config.json 明文，注意 .gitignore 已排除）
    "ds_api_key": "",
    "platform_token": "",
    # 窗口状态
    "topmost": True,
    "passthrough": False,
    "autostart": False,
    "x": None,
    "y": None,
    # 吸附锚点：h 为 left/right/None，v 为 top/bottom/None
    "h": "right",
    "v": "bottom",
    "h_off": 0,
    "v_off": 0,
}


def load_config() -> dict:
    """读取 config.json；不存在或损坏时返回默认配置（并落盘默认值）。"""
    if not os.path.exists(CONFIG_PATH):
        cfg = dict(DEFAULTS)
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("config root is not an object")
    except Exception:
        return dict(DEFAULTS)
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    return cfg


def save_config(cfg: dict) -> bool:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except OSError as err:
        try:
            from log import get_logger  # 延迟导入，避免循环引用

            get_logger().warning("配置写入失败: %s (%s)", CONFIG_PATH, err)
        except Exception:
            pass
        return False


def lines_path() -> str:
    """台词表路径。

    优先用程序目录里的 台词表.md（用户可编辑、可分享）；
    打包版（PyInstaller）程序目录里没有时，首次运行自动从内置副本释放一份，
    否则 exe 用户改不了台词、且不会得到任何提示。
    """
    if os.path.exists(LINES_PATH):
        return LINES_PATH
    bundled = BUNDLED_LINES_PATH
    if os.path.abspath(bundled) != os.path.abspath(LINES_PATH) and os.path.exists(bundled):
        try:
            shutil.copy2(bundled, LINES_PATH)
            return LINES_PATH
        except OSError as err:
            try:
                from log import get_logger  # 延迟导入，避免循环引用

                get_logger().warning("台词表释放失败: %s (%s)", LINES_PATH, err)
            except Exception:
                pass
            return bundled
    return LINES_PATH  # 都不存在：调用方回落到内置默认台词


def resolve_api_key(cfg: dict) -> str:
    """余额 Key：环境变量优先，其次 config.json。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    return str(cfg.get("ds_api_key", "") or "").strip()


def resolve_platform_token(cfg: dict) -> str:
    """平台令牌：环境变量优先，其次 config.json。"""
    token = os.environ.get("DEEPSEEK_PLATFORM_TOKEN", "").strip()
    if token:
        return token
    return str(cfg.get("platform_token", "") or "").strip()
