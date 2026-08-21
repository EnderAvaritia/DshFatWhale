# -*- coding: utf-8 -*-
"""Qt 冒烟测试：offscreen 实例化主窗口，驱动 tick/绘制/菜单，验证不崩溃。
临时脚本，验证后删除。运行：.venv\\Scripts\\python.exe tests\\_smoke_qt.py
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from menu import build_menu, create_tray
from widget import WhaleWindow

app = QApplication(sys.argv)
win = WhaleWindow()

failures = []


def check(name, cond):
    print(("  ok: " if cond else "  FAIL: ") + name)
    if not cond:
        failures.append(name)


def finish():
    # 1. 窗口尺寸合理
    check("窗口尺寸 > 0", win.width() > 100 and win.height() > 200)

    # 2. 强制绘制，检查有非透明像素（鲸鱼画出来了）
    img: QImage = win.grab().toImage()
    non_transparent = 0
    for y in range(0, img.height(), 8):
        for x in range(0, img.width(), 8):
            if img.pixelColor(x, y).alpha() > 10:
                non_transparent += 1
    check("绘制出非透明内容 (samples=%d)" % non_transparent, non_transparent > 10)

    # 3. 右键菜单可构建
    m = build_menu(win)
    check("菜单可构建，条目数 >= 10", len(m.actions()) >= 10)

    # 4. 托盘可创建
    tray = create_tray(win)
    check("托盘已创建", tray is not None)

    # 5. 无 Key 时 refresh 走错误分支不崩溃
    win.cfg["ds_api_key"] = ""
    win.refresh(True)
    check("无 Key 错误分支", win.status == "error")

    # 6. 有 Key 时（假 Key）网络分支不崩溃
    win.cfg["ds_api_key"] = "sk-fake-test-key"
    win.refresh(True)

    # 7. 随机台词可挑选
    lines, inner = win._pick_random_lines()
    check("随机台词非空", len(lines) >= 1 and lines[0][0])

    # 8. 大小/音效/音量切换
    win.set_size(1.3)
    win.set_sound_set("fx1")
    win.set_volume(0.5)
    check("size/sound/vol 状态更新", win.cfg["size"] == 1.3 and win.cfg["sound_set"] == "fx1" and abs(win.cfg["vol"] - 0.5) < 0.01)

    # 9. 记账文件已生成（config.json 落盘）
    from config import CONFIG_PATH, LEDGER_PATH
    check("config.json 已生成", os.path.exists(CONFIG_PATH))

    # 10. 退出保存
    win.quit_app()
    print()
    print("SMOKE RESULT:", "PASS" if not failures else "FAIL: " + ", ".join(failures))
    sys.exit(1 if failures else 0)


# 跑 1.5 秒 tick 后收尾
QTimer.singleShot(1500, finish)
sys.exit(app.exec())
