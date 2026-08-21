# -*- coding: utf-8 -*-
"""鲸鱼.py —— DeepSeek 余额鲸鱼桌宠入口。

独立运行（不依赖 DSH/浏览器）：透明置顶桌宠，显示 DeepSeek 余额与今日已用。
运行：双击 启动鲸鱼.bat，或 .venv\\Scripts\\pythonw.exe 鲸鱼.py
"""
import sys

from PySide6.QtWidgets import QApplication

from menu import create_tray
from widget import WhaleWindow


def main():
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
        try:
            from PySide6.QtWidgets import QApplication as _QA, QMessageBox
            app = _QA.instance() or _QA(sys.argv)
            QMessageBox.critical(None, "DeepSeek 余额鲸鱼出错", str(ex))
        except Exception:
            pass
        raise
