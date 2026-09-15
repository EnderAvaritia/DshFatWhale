# -*- coding: utf-8 -*-
"""menu.py —— 右键菜单与系统托盘（桌面版"汉堡菜单"）。

仅依赖传入的 widget 实例方法，不反向 import widget，避免循环引用。
"""
import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSlider,
    QSystemTrayIcon,
    QWidget,
    QWidgetAction,
)

from config import app_dir, assets_dir

SIZE_LEVELS = (("小", 0.7), ("中", 1.0), ("大", 1.3), ("特大", 1.6))


class _VolumeAction(QWidgetAction):
    """菜单内嵌音量滑块。"""

    def __init__(self, parent, widget):
        super().__init__(parent)
        self._widget = widget
        self._slider = None
        self._pct = None

    def createWidget(self, parent):
        box = QWidget(parent)
        lay = QHBoxLayout(box)
        lay.setContentsMargins(24, 2, 16, 2)
        label = QLabel("音量")
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(int(widget_vol(self._widget) * 100))
        self._pct = QLabel(str(int(widget_vol(self._widget) * 100)) + "%")
        self._pct.setFixedWidth(36)
        self._slider.valueChanged.connect(self._on_change)
        lay.addWidget(label)
        lay.addWidget(self._slider, 1)
        lay.addWidget(self._pct)
        return box

    def _on_change(self, v):
        self._pct.setText(str(v) + "%")
        self._widget.set_volume(v / 100.0)


def widget_vol(widget) -> float:
    try:
        return float(widget.cfg.get("vol", 0.9))
    except (TypeError, ValueError):
        return 0.9


def build_menu(widget) -> QMenu:
    """构建完整右键菜单（每次调用重建，保证勾选状态最新）。"""
    m = QMenu(widget)

    mode_menu = m.addMenu("用量模式")
    for label, key in (("小鲸鱼记账 (推荐)", "ledger"), ("实时·令牌", "token")):
        a = mode_menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(widget.cfg.get("usage_mode", "ledger") == key)
        a.triggered.connect(lambda _=False, k=key: widget.set_usage_mode(k))

    sound_menu = m.addMenu("音效")
    sa = sound_menu.addAction("开启音效")
    sa.setCheckable(True)
    sa.setChecked(bool(widget.cfg.get("sound_on", True)))
    sa.triggered.connect(lambda on: widget.set_sound_on(on))
    sound_menu.addSeparator()
    for label, key in (("小黄鸭", "duck"), ("音效1", "fx1")):
        a = sound_menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(widget.cfg.get("sound_set", "duck") == key)
        a.triggered.connect(lambda _=False, k=key: widget.set_sound_set(k))

    m.addAction(_VolumeAction(m, widget))

    pb = m.addAction("余额气泡（常驻）")
    pb.setCheckable(True)
    pb.setChecked(bool(widget.cfg.get("persistent_bubble", True)))
    pb.triggered.connect(lambda on: widget.set_persistent(on))

    size_menu = m.addMenu("大小")
    for label, mult in SIZE_LEVELS:
        a = size_menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(abs(float(widget.cfg.get("size", 1.0)) - mult) < 0.001)
        a.triggered.connect(lambda _=False, v=mult: widget.set_size(v))

    m.addSeparator()
    m.addAction("设置 DeepSeek Key…", lambda: _set_key(widget))
    m.addAction("设置平台令牌…（令牌模式用）", lambda: _set_token(widget))
    m.addSeparator()

    m.addAction("显示/隐藏", widget.toggle_visible)
    m.addAction("回到屏幕内", widget.snap_into_screen)

    pa = m.addAction("鼠标穿透（点不到它）")
    pa.setCheckable(True)
    pa.setChecked(bool(widget.cfg.get("passthrough", False)))
    pa.triggered.connect(lambda on: widget.set_passthrough(on))

    ta = m.addAction("窗口置顶")
    ta.setCheckable(True)
    ta.setChecked(bool(widget.cfg.get("topmost", True)))
    ta.triggered.connect(lambda on: widget.set_topmost(on))

    aa = m.addAction("开机自启")
    aa.setCheckable(True)
    aa.setChecked(bool(widget.cfg.get("autostart", False)))
    aa.triggered.connect(lambda on: widget.set_autostart(on))

    m.addSeparator()
    m.addAction("退出", widget.quit_app)
    return m


def _set_key(widget):
    key, ok = QInputDialog.getText(
        widget, "设置 DeepSeek Key",
        "输入 API Key（platform.deepseek.com 获取，环境变量 DEEPSEEK_API_KEY 优先于此处）:",
        QLineEdit.EchoMode.Normal,
        widget.cfg.get("ds_api_key", ""),
    )
    if ok and key.strip():
        widget.cfg["ds_api_key"] = key.strip()
        widget.save_cfg()
        widget.say("Key 已设置，试试点我刷新吧~")
        widget.refresh(True)
    elif ok:
        widget.say("Key 不能为空")


def _set_token(widget):
    token, ok = QInputDialog.getText(
        widget, "设置平台令牌",
        "输入平台会话令牌（浏览器 DevTools 用量请求的 Authorization 头，仅令牌模式使用）:",
        QLineEdit.EchoMode.Normal,
        widget.cfg.get("platform_token", ""),
    )
    if ok and token.strip():
        widget.cfg["platform_token"] = token.strip()
        widget.save_cfg()
        widget.say("令牌已设置~")
        widget.refresh(True)


def create_tray(widget) -> QSystemTrayIcon:
    """系统托盘：左键切换显隐，右键同款菜单（穿透后靠它解除）。"""
    icon = QIcon(os.path.join(assets_dir(), "icon.ico"))
    tray = QSystemTrayIcon(icon, widget)
    tray.setToolTip("DshFatWhale · DeepSeek 余额鲸鱼")
    tray.setContextMenu(build_menu(widget))
    tray.activated.connect(lambda reason: _on_tray_activated(reason, tray, widget))
    tray.show()
    return tray


def _on_tray_activated(reason, tray, widget):
    if reason == QSystemTrayIcon.ActivationReason.Trigger:
        widget.toggle_visible()
    elif reason == QSystemTrayIcon.ActivationReason.Context:
        tray.setContextMenu(build_menu(widget))


def _ps_quote(path: str) -> str:
    """PowerShell 单引号字符串里的单引号需要写成两个。"""
    return str(path).replace("'", "''")


def set_autostart(widget, on: bool):
    """开机自启：Startup 目录快捷方式（同 dafeiyu-pet 实现）。"""
    prev = bool(widget.cfg.get("autostart", False))
    lnk = os.path.join(
        os.environ["APPDATA"], "Microsoft", "Windows",
        "Start Menu", "Programs", "Startup", "大肥鱼鲸鱼.lnk",
    )
    frozen = getattr(sys, "frozen", False)
    if not frozen:
        target = os.path.join(app_dir(), ".venv", "Scripts", "pythonw.exe")
        if not os.path.exists(target):
            target = sys.executable
        args = os.path.join(app_dir(), "鲸鱼.py")
    else:
        target = sys.executable
        args = ""
    try:
        if on:
            ps = (
                "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{}');"
                "$s.TargetPath='{}';$s.Arguments='{}';$s.WorkingDirectory='{}';$s.Save()"
            ).format(_ps_quote(lnk), _ps_quote(target), _ps_quote(args), _ps_quote(app_dir()))
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=True,
            )
            widget.cfg["autostart"] = True
            widget.save_cfg()
            widget.say("已开机自启，明天见～")
        else:
            if os.path.exists(lnk):
                os.remove(lnk)
            widget.cfg["autostart"] = False
            widget.save_cfg()
            widget.say("已取消开机自启")
    except Exception as ex:
        # 失败要落日志（用户看不到的异常一律进 logs/whale.log），并把开关状态回滚，
        # 避免菜单勾选状态与真实情况不一致
        try:
            from log import get_logger

            get_logger().exception("开机自启设置失败 on=%s", on)
        except Exception:
            pass
        widget.cfg["autostart"] = prev
        widget.save_cfg()
        QMessageBox.warning(
            widget, "开机自启",
            "设置失败：%s\n\n详细原因见程序目录 logs/whale.log" % ex,
        )
