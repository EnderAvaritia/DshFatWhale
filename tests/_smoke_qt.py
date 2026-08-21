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

# 台词表解析器单测（无需 Qt）
import tempfile
from widget import load_line_groups

with tempfile.TemporaryDirectory() as td:
    md = os.path.join(td, "t.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(
            "## 我的台词（权重 100）\n- 我的梗\n"
            "## 日常（权重 5）\n- 甲\n- 乙\n"
            "## 心声（权重 2，心声）\n- 内心\n"
            "## 多行（权重 1，多行）\n- 一\n- 二\n"
            "## 点击触发\n- 点我\n- 再点我\n"
            "## 拖拽后随机\n- 拖我\n"
            "## 内置动态（跳过）\n- 不会被读取\n"
        )
    g, d, c = load_line_groups(md)
    assert len(g) == 4, g
    assert g[0] == (100, "A", False, ["我的梗"]), "我的台词组应为最高权重 100 且在首位"
    assert g[2][1] == "inner" and g[3][2] is True, g
    assert c == ["点我", "再点我"], c
    assert d == ["拖我"], d
print("  ok: 台词表解析器（含点击触发/拖拽/心声/多行/跳过）")

from menu import build_menu, create_tray
from widget import WhaleWindow

app = QApplication(sys.argv)
win = WhaleWindow()
win.set_persistent(True)  # 确定性：不依赖用户 config.json 里 persistent_bubble 的保存值

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
    # 防回归：台词表.md 必须是机器可读格式（含"权重"头与点击触发分组）
    md_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "台词表.md")
    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()
    check("台词表.md 为可解析格式", "（权重" in md_text and "## 点击触发" in md_text and "## 我的台词（权重 100）" in md_text)

    # 8b. 点击 = 台词表循环 + 常驻余额气泡
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win.set_persistent(True)
    check("常驻开启: 余额气泡显示", win.bubble_visible and not win.bubble_random)
    QTest.mouseClick(win, Qt.MouseButton.LeftButton)
    check("点击→台词", win.bubble_visible and win.bubble_random)
    QTest.mouseClick(win, Qt.MouseButton.LeftButton)
    check("再点→另一句台词", win.bubble_random)
    win._return_to_persistent()
    check("台词回落常驻余额", win.bubble_visible and not win.bubble_random)
    win.set_persistent(False)
    check("常驻关闭: 气泡隐藏", not win.bubble_visible)
    QTest.mouseClick(win, Qt.MouseButton.LeftButton)
    check("常驻关闭: 点击→台词", win.bubble_visible and win.bubble_random)
    win._return_to_persistent()
    check("常驻关闭: 回落后隐藏", not win.bubble_visible)
    win.set_persistent(True)

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
