# -*- coding: utf-8 -*-
"""鲸鱼.py —— DshFatWhale：DeepSeek 余额鲸鱼桌宠入口。

独立运行（不依赖 DSH/浏览器）：透明置顶桌宠，显示 DeepSeek 余额与今日已用。
运行：双击 启动鲸鱼.bat，或 .venv\\Scripts\\pythonw.exe 鲸鱼.py

日志：logs/whale.log（pythonw / 打包 exe 都没有控制台，所有异常都落这里）
"""
import sys
import traceback

from PySide6.QtWidgets import QApplication

from log import get_logger, log_path
from menu import create_tray
from widget import WhaleWindow


def _install_excepthook() -> None:
    """把未捕获异常（含 Qt 槽函数里的）写进日志，避免静默死亡。"""

    def hook(exc_type, exc, tb):
        get_logger().error(
            "未捕获异常: %s\n%s", exc_type.__name__, "".join(traceback.format_exception(exc_type, exc, tb))
        )

    sys.excepthook = hook


def main():
    _install_excepthook()
    get_logger().info(
        "启动 DshFatWhale (frozen=%s, python=%s)", getattr(sys, "frozen", False), sys.version.split()[0]
    )
    app = QApplication(sys.argv)
    app.setApplicationName("DeepSeek 余额鲸鱼")
    app.setQuitOnLastWindowClosed(False)
    win = WhaleWindow()
    tray = create_tray(win)
    win._tray = tray  # 保持引用，防止被回收
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        # 先落日志（用户看不到的异常必须留痕），再尽量弹一个能看懂的框
        try:
            get_logger().error("启动失败: %s\n%s", ex, traceback.format_exc())
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QApplication as _QA, QMessageBox

            app = _QA.instance() or _QA(sys.argv)
            QMessageBox.critical(
                None,
                "DeepSeek 余额鲸鱼出错",
                "启动失败：%s\n\n详细堆栈见 %s" % (ex, log_path()),
            )
        except Exception:
            pass
        raise
