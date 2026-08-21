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

import balance as balance_mod

# 打桩：测试全程不碰真实网络，行为确定
balance_mod.fetch_balance = lambda key: {"ok": False, "code": "NO_KEY", "error": "test-no-network"}
balance_mod.fetch_usage = lambda token: {"error": "test-no-network"}

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

    # 3. 注入的成功载荷已处理：气泡 + 数字落位（须在后续 refresh 之前检查）
    check("首次载荷后气泡弹出", win.bubble_visible)
    check("余额数字落位 12.34", win.shown == 12.34 and win.status == "ok")
    check("今日已用已更新", win.today_usage == 0.56)

    # 4. 右键菜单可构建
    m = build_menu(win)
    check("菜单可构建，条目数 >= 10", len(m.actions()) >= 10)

    # 5. 托盘可创建
    tray = create_tray(win)
    check("托盘已创建", tray is not None)

    # 6. 无 Key 时 refresh 走错误分支不崩溃
    win.cfg["ds_api_key"] = ""
    win.refresh(True)
    check("无 Key 错误分支", win.status == "error")

    # 7. 有 Key 时（假 Key）网络分支不崩溃
    win.cfg["ds_api_key"] = "sk-fake-test-key"
    win.refresh(True)

    # 8. 随机台词可挑选 + 台词表加载
    lines, inner = win._pick_random_lines()
    check("随机台词非空", len(lines) >= 1 and lines[0][0])
    check("台词表加载 8 组", len(win._line_groups) == 8)
    check("拖拽台词 4 条", len(win._drag_lines) == 4)
    # 三连句组应为多行整组气泡
    multi = [g for g in win._line_groups if g[2]]
    check("三连句多行组", len(multi) == 1 and len(multi[0][3]) == 3)

    # 9. 大小/音效/音量切换
    win.set_size(1.3)
    win.set_sound_set("fx1")
    win.set_volume(0.5)
    check("size/sound/vol 状态更新", win.cfg["size"] == 1.3 and win.cfg["sound_set"] == "fx1" and abs(win.cfg["vol"] - 0.5) < 0.01)

    # 10. 中线镜像逻辑
    geo = win.screen().availableGeometry()
    win.move(geo.left() + 1, geo.top() + 1)
    win._update_mirror()
    check("左半区镜像", win.mirrored)
    win.move(geo.right() - win.width() - 1, geo.top() + 1)
    win._update_mirror()
    check("右半区不镜像", not win.mirrored)

    # 11. 记账文件已生成（config.json 落盘）
    from config import CONFIG_PATH, LEDGER_PATH
    check("config.json 已生成", os.path.exists(CONFIG_PATH))

    # 12. 退出保存
    win.quit_app()

    print()
    print("SMOKE RESULT:", "PASS" if not failures else "FAIL: " + ", ".join(failures))
    sys.exit(1 if failures else 0)


# 跑 1.5 秒 tick 后注入模拟成功载荷，再等 300ms 收尾
QTimer.singleShot(1500, lambda: inject_payload(win))
QTimer.singleShot(1800, finish)


def inject_payload(win):
    # 直接投递一个成功载荷，验证首次观测 → 弹气泡 + 数字落位
    with win.engine._lock:
        win.engine._results.append({
            "ok": True, "totalBalance": 12.34, "currency": "CNY",
            "todayUsage": 0.56, "isPeak": True, "usageMode": "ledger",
        })
    win.refresh_timer.stop()  # 避免 60s 定时器干扰退出


sys.exit(app.exec())
