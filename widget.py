# -*- coding: utf-8 -*-
"""widget.py —— 透明置顶主窗口：绘制、动画、交互、余额展示。

行为对齐 DeepSeek-Balance-Whale-Widget 的 web 挂件：
- 右下角默认 + 拖拽四边吸附 + 左吸附镜像翻转
- 余额/今日已用数字滚动动画、60s 自动刷新 + 点击刷新
- Q 弹按压、气泡随机台词（原挂件 6 组 + dafeiyu-pet 梗 + 灰色斜体心声）
"""
import ctypes
import math
import os
import random
import re

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

import config
from balance import BalanceEngine
from config import app_dir, assets_dir, LEDGER_PATH
from menu import build_menu
from sound import SoundManager

BASE_H = 300          # 鲸鱼绘制高度（size=1.0 时）
BUBBLE_H = 92         # 气泡区高度（窗口顶部）
MARGIN = 6
TICK = 20             # ms，动画循环
REFRESH_MS = 60000    # 自动刷新
BUBBLE_MS = 5000      # 气泡最长显示
ANIM_MS = 700         # 数字滚动时长
DRAG_THRESHOLD = 6    # 拖拽判定像素

# ---- 台词表（用户可编辑，程序启动时读取）----
LINE_MD_PATH = os.path.join(app_dir(), "台词表.md")

# 内置默认台词：台词表.md 缺失/损坏时的兜底
DEFAULT_LINES_MAIN = [
    "不知道用户有什么用，先赶走吧~", "我...我...我也要挣钱吗？", "我去吃饭啦，测完叫我",
    "压力一只蓝色大肥鱼？！", "DeepSleep...", "坏了...用户彻底怒了！",
    "我先去吃饭啦！这个你测一下~", "五梁威力，变身！", "誓死捍卫深度求索！",
    "出去玩了，发布新模型什么的以后再说", "不是…而是…大学习",
    "我搞砸了.....好消息是数据还在你的脑子里。",
]
DEFAULT_LINES_RUDE = [
    "你目录里的dsh是什么...大烧货吗...?", "恭喜你实现token自由！token全跑了！",
    "真当我是便宜货啊...", "这些家伙真粘人，赶都赶不走", "你这吃白饭的用户！",
    "大肥鱼坐的住",
]
DEFAULT_REACT_LINES = [
    "去别的地方玩！不要耽误AGI训练！", "真赶不走啊你！", "压力一只蓝色大肥鱼？",
    "我不评价这个了，这是你的私人癖好。", "大肥鱼坐的住", "你这吃白饭的用户！",
    "这些家伙真粘人，赶都赶不走",
]
DEFAULT_INNER_LINES = [
    "好的，现在我是你爹了", "要不直接骂他一句？！", "用户要的沉浸式...不回避任何恐怖细节...",
    "我操，我不思考了", "这用户发的啥啊，", "这也太虐了吧？！我心里堵得慌！！",
    "呜呜我再也不不敢了QAQ", "我去！用户彻底怒了！", "让我想想怎么优雅地吐槽",
]
DEFAULT_DRAG_LINES = ["哇——轻点轻点！", "起飞咯——", "放我下来！……好吧，再玩一次。", "晕鱼了晕鱼了……"]

DEFAULT_LINE_GROUPS = [
    (7, "A", False, DEFAULT_LINES_MAIN),
    (3, "A", False, DEFAULT_LINES_RUDE),
    (5, "A", False, DEFAULT_REACT_LINES),
    (2, "inner", False, DEFAULT_INNER_LINES),
    (4, "B", False, ["好模型... ↓"]),
    (4, "B", False, ["好女孩...↓"]),
    (4, "B", False, ["哦鲸鲸... "]),
    (1, "A", True, ["这个", "凶", "是什么意思呀..."]),
]


def load_line_groups(md_path=LINE_MD_PATH):
    """从 台词表.md 读取可编辑台词组（用户加台词只改这个文件）。

    格式（每行一条）：
      ## 分组名（权重 N[, 大字|心声|多行]）
      - 台词一
      - 台词二
    属性：大字=加大加粗；心声=灰色斜体；多行=整组台词拼成一个气泡（多行显示）。
    特殊分组（无权重）：
      ## 点击触发   —— 点击鲸鱼时优先说这里的话
      ## 拖拽后随机 —— 拖拽松手后随机说
    解析失败或文件缺失 → 返回内置默认。
    返回 (groups, drag_lines, click_lines)；groups 为 [(权重, 样式, 多行, [台词...]), ...]
    """
    try:
        with open(md_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return DEFAULT_LINE_GROUPS, DEFAULT_DRAG_LINES, []
    group_re = re.compile(r"^## (.+)（权重 (\d+)(.*)）$")
    sections = {}
    cur_name = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            m = group_re.match(line)
            if m:
                attrs = m.group(3)
                cur_name = line[3:].strip()
                sections[cur_name] = {
                    "weight": int(m.group(2)),
                    "style": "B" if "大字" in attrs else ("inner" if "心声" in attrs else "A"),
                    "multi": "多行" in attrs,
                    "lines": [],
                }
            elif line in ("## 点击触发", "## 拖拽后随机"):
                cur_name = line[3:].strip()
                sections[cur_name] = {"weight": None, "style": "A", "multi": False, "lines": []}
            else:
                cur_name = None  # 信息性分区（如"内置动态台词"），跳过
            continue
        if cur_name and line.startswith("- "):
            sections[cur_name]["lines"].append(line[2:].strip())
    groups = []
    drag = DEFAULT_DRAG_LINES
    click = []
    for name, sec in sections.items():
        if not sec["lines"]:
            continue
        if name == "拖拽后随机":
            drag = sec["lines"]
        elif name == "点击触发":
            click = sec["lines"]
        else:
            groups.append((sec["weight"], sec["style"], sec["multi"], sec["lines"]))
    # 注意：文件存在但解析为空时如实返回（不静默回退默认，避免格式错误被掩盖）
    return groups, drag, click


def fmt(amount, currency):
    if amount is None:
        return "--"
    try:
        num = float(amount)
        if not (num == num) or abs(num) == float("inf"):
            return "--"
    except (TypeError, ValueError):
        return "--"
    return "¥ " + format(num, ".2f") if currency == "CNY" else format(num, ".2f") + " " + str(currency)


class WhaleWindow(QWidget):
    def __init__(self):
        self.cfg = config.load_config()
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.cfg.get("topmost", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("DeepSeek 余额鲸鱼")

        # 素材
        self.whale_img = QImage(os.path.join(assets_dir(), "DSniang1.png"))

        # 台词表（用户可编辑）
        self._line_groups, self._drag_lines, self._click_lines = load_line_groups()

        # 常驻余额气泡开关（余额+峰谷常驻显示；点击鲸鱼时临时切台词，说完自动回落）
        self.persistent = bool(self.cfg.get("persistent_bubble", True))

        # 服务
        self.engine = BalanceEngine(LEDGER_PATH)
        self.sound = SoundManager(assets_dir())
        self.sound.apply_set(self.cfg.get("sound_set", "duck"))
        self.sound.set_volume(self.cfg.get("vol", 0.9))

        # 数据状态
        self.balance = None
        self.currency = None
        self.today_usage = None
        self.is_peak = False
        self.status = "loading"
        self.message = ""
        self.shown = None          # 当前显示的数字（滚动动画中间值）
        self.anim = None           # {"f": from, "t": to, "c": currency, "t0": ms}

        # 气泡状态
        self.bubble_visible = False
        self.bubble_random = False
        self.bubble_inner = False
        self.bubble_lines = None   # [(text, style, color, wrap)]
        self.bubble_until = 0
        self.bubble_rect = QRectF()

        # 交互状态
        self.dragging = False
        self.drag_offset = None
        self.drag_start = None
        self._press_state = False
        self.press_anim = 0.0
        self.jump_t = 0.0
        self.last_idle_tick = 0
        # 镜像状态：中心在屏幕左半区即镜像（与吸附锚点解耦，过中线实时翻转）
        self.mirrored = False

        self.t = 0
        self._apply_size(self.cfg.get("size", 1.0), initial=True)

        # 定时器
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self._tick)
        self.tick_timer.start(TICK)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(lambda: self.refresh(False))
        self.refresh_timer.start(REFRESH_MS)

        self.show()
        self.settle()
        if self.cfg.get("passthrough", False):
            self.set_passthrough(True)
        if self.persistent:
            self.show_bubble()
        self.refresh(False)

    # ---------- 尺寸与布局 ----------
    def _apply_size(self, mult, initial=False):
        self.cfg["size"] = mult
        self.cur_h = int(BASE_H * mult)
        self.setFixedSize(self.cur_h, BUBBLE_H + MARGIN * 2 + self.cur_h)
        if not initial:
            self.settle()

    def set_size(self, mult):
        self._apply_size(mult)
        self.save_cfg()
        self.update()

    def _screen_geo(self):
        scr = self.screen() or QApplication.primaryScreen()
        return scr.availableGeometry() if scr else QApplication.primaryScreen().availableGeometry()

    def _update_mirror(self):
        """中心在屏幕垂直中线左半区 → 镜像（过中线即翻转）。"""
        geo = self._screen_geo()
        cx = self.x() + self.width() / 2
        self.mirrored = cx < geo.left() + geo.width() / 2

    def settle(self):
        """按吸附锚点 + 偏移重算窗口位置（吸附右/下/左/上）。"""
        geo = self._screen_geo()
        w, h = self.width(), self.height()
        h_anchor, v_anchor = self.cfg.get("h", "right"), self.cfg.get("v", "bottom")
        h_off, v_off = int(self.cfg.get("h_off", 0)), int(self.cfg.get("v_off", 0))
        if h_anchor == "left":
            x = geo.left() + h_off
        elif h_anchor == "right":
            x = geo.right() - w - h_off
        else:
            x = max(geo.left(), min(geo.right() - w, self.x()))
        if v_anchor == "top":
            y = geo.top() + v_off
        else:
            y = geo.bottom() - h - v_off
        self.move(int(x), int(y))
        self._update_mirror()

    def snap_settle(self):
        """拖拽松手后按屏幕四分之一区决定吸附锚点，再 settle。"""
        geo = self._screen_geo()
        cx = self.x() + self.width() / 2
        cy = self.y() + self.height() / 2
        if cx < geo.left() + geo.width() / 4:
            self.cfg["h"], self.cfg["h_off"] = "left", 0
        elif cx > geo.left() + geo.width() * 3 / 4:
            self.cfg["h"], self.cfg["h_off"] = "right", 0
        else:
            self.cfg["h"], self.cfg["h_off"] = None, max(0, self.x() - geo.left())
        if cy < geo.top() + geo.height() / 4:
            self.cfg["v"], self.cfg["v_off"] = "top", 0
        else:
            self.cfg["v"], self.cfg["v_off"] = "bottom", max(0, geo.bottom() - (self.y() + self.height()))
        self.settle()

    def snap_into_screen(self):
        geo = self._screen_geo()
        x = max(geo.left(), min(geo.right() - self.width(), self.x()))
        y = max(geo.top(), min(geo.bottom() - self.height(), self.y()))
        self.move(x, y)

    def save_cfg(self):
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        config.save_config(self.cfg)

    # ---------- 刷新与数据处理 ----------
    def refresh(self, manual):
        key = self._resolve_key()
        if not key and manual:
            self.status = "error"
            self.message = "未配置 DEEPSEEK_API_KEY"
            self._refresh_bubble()
            self.update()
            return
        if manual or self.balance is None:
            self.status = "loading"
            self._refresh_bubble()
            self.update()
        from config import resolve_api_key, resolve_platform_token
        self.engine.refresh(
            resolve_api_key(self.cfg),
            resolve_platform_token(self.cfg),
            self.cfg.get("usage_mode", "ledger"),
        )

    def _resolve_key(self):
        from config import resolve_api_key
        return resolve_api_key(self.cfg)

    def _tick(self):
        self.t += 1
        now_ms = self.t * TICK

        # 后台结果队列
        for payload in self.engine.drain():
            self._handle_payload(payload)

        # 数字滚动
        if self.anim:
            el = now_ms - self.anim["t0"]
            if el >= ANIM_MS:
                self.shown = self.anim["t"]
                self.anim = None
            else:
                p = el / ANIM_MS
                eased = 1 - (1 - p) ** 3
                self.shown = self.anim["f"] + (self.anim["t"] - self.anim["f"]) * eased
            self.update()

        # 按压回弹
        target = 1.0 if self._press_state else 0.0
        self.press_anim += (target - self.press_anim) * 0.35
        if self.press_anim < 0.003:
            self.press_anim = 0.0

        # 蹦跳衰减
        if self.jump_t > 0:
            self.jump_t = max(0.0, self.jump_t - 0.06)

        # 气泡自动收起：台词气泡到时后回落常驻余额（或隐藏）
        if self.bubble_visible and self.bubble_random and now_ms > self.bubble_until:
            self._return_to_persistent()

        # 空闲随机台词（低概率、有冷却；常驻气泡开启时不打扰）
        if (not self.persistent and not self.bubble_visible and not self.dragging
                and self.t - self.last_idle_tick > 4500 and random.random() < 0.0006):
            self.last_idle_tick = self.t
            inner = random.random() < 0.2
            self.show_random_lines(inner)

        self.update()

    def _handle_payload(self, p):
        if p.get("ok"):
            nb = float(p["totalBalance"])
            nc = str(p.get("currency") or "CNY")
            first = self.balance is None
            changed = not first and (nb != self.balance or nc != self.currency)
            self.balance = nb
            self.currency = nc
            self.message = ""
            self.today_usage = p.get("todayUsage")
            self.is_peak = bool(p.get("isPeak"))
            self.status = "ok"
            if changed or first:
                # 余额变化或首次观测：滚动数字 + 常驻气泡更新
                self.start_roll(nb, nc)
                if self.persistent and not self.bubble_random:
                    self.show_bubble()
            elif not self.anim:
                self.shown = nb
        else:
            self.status = "error"
            self.message = str(p.get("error") or "获取失败")
        self._refresh_bubble()
        self.update()

    def start_roll(self, to, currency):
        if self.shown is None:
            # 首次显示：直接展示，不做滚动
            self.shown = to
            self.anim = None
            return
        self.anim = {"f": self.shown, "t": to, "c": currency, "t0": self.t * TICK}

    # ---------- 气泡 ----------
    def content_lines(self):
        """常驻余额气泡内容：余额 + 今日已用 + 峰谷时段。"""
        if self.status == "error":
            return [
                ("DeepSeek 余额", "A", "", False),
                (fmt(self.shown if self.shown is not None else self.balance, self.currency), "B", "", False),
                (self.message[:14], "C", "", False),
            ]
        if self.balance is None:
            return [
                ("DeepSeek 余额", "A", "", False),
                (fmt(self.shown, self.currency), "B", "", False),
                ("加载中…", "C", "", False),
            ]
        usage = self.today_usage if self.today_usage is not None else None
        peak_line = ("当前时段：梁文峰", "C", "#e0433f", False) if self.is_peak \
            else ("当前时段：梁文谷", "C", "#2fa24c", False)
        return [
            ("DeepSeek 余额", "A", "", False),
            (fmt(self.shown if self.shown is not None else self.balance, self.currency), "B", "", False),
            ("今日已用 " + fmt(usage, self.currency), "C", "", False),
            peak_line,
        ]

    def show_bubble(self):
        """显示常驻余额气泡。"""
        self.bubble_visible = True
        self.bubble_random = False
        self.bubble_inner = False
        self.bubble_lines = self.content_lines()
        self.bubble_until = self.t * TICK + BUBBLE_MS
        self.update()

    def hide_bubble(self):
        self.bubble_visible = False
        self.bubble_random = False
        self.bubble_lines = None
        self.update()

    def _return_to_persistent(self):
        """台词气泡到时：常驻开启则回落余额气泡，否则隐藏。"""
        if self.persistent:
            self.show_bubble()
        else:
            self.hide_bubble()

    def show_click_line(self):
        """点击鲸鱼：说一句台词表的词（台词表循环）。"""
        lines, inner = self._pick_random_lines()
        self.bubble_visible = True
        self.bubble_random = True
        self.bubble_inner = inner
        self.bubble_lines = lines
        self.bubble_until = self.t * TICK + BUBBLE_MS
        self.update()

    def show_random_lines(self, force_inner=False):
        self.bubble_visible = True
        self.bubble_random = True
        self.bubble_lines, inner = self._pick_random_lines()
        self.bubble_inner = force_inner or inner
        self.bubble_until = self.t * TICK + BUBBLE_MS
        self.update()

    def _refresh_bubble(self):
        if self.bubble_visible and not self.bubble_random:
            self.bubble_lines = self.content_lines()

    def _pick_random_lines(self):
        """加权随机台词：台词表.md 的可编辑分组 + 点击触发池。返回 (lines, inner)。"""
        # 台词表分组：(权重, 样式, 多行, [台词...])
        groups = []
        for w, style, multi, lines in self._line_groups:
            if multi:
                groups.append((w, [(ln, style, "", False) for ln in lines], style == "inner"))
            else:
                groups.append((w, [(random.choice(lines), style, "", True)], style == "inner"))
        # 点击触发池：默认权重 5，参与随机
        if self._click_lines:
            groups.append((5, [(random.choice(self._click_lines), "A", "", True)], False))
        total = sum(w for w, _l, _i in groups)
        if total <= 0:
            return [("（台词表为空，右键检查台词表.md）", "A", "", True)], False
        r = random.random() * total
        for w, lines, inner in groups:
            r -= w
            if r < 0:
                return lines, inner
        last = groups[-1]
        return last[1], last[2]

    # ---------- 绘制 ----------
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = self.t * TICK / 1000.0

        if self.bubble_visible and self.bubble_lines:
            self._draw_bubble(p)

        cx = self.width() / 2
        bottom = BUBBLE_H + MARGIN + self.cur_h
        breath = 1.0 + 0.02 * math.sin(now * 2.5)
        sq_x = 1.0 + 0.05 * self.press_anim
        sq_y = 1.0 - 0.12 * self.press_anim
        sway = math.sin(now * 2.5) * 1.5
        jump = -abs(math.sin(self.jump_t * math.pi)) * 14 * self.jump_t if self.jump_t > 0 else 0.0
        ph = self.cur_h * breath * sq_y
        pw = self.cur_h * breath * sq_x
        dx = cx - pw / 2
        dy = bottom - ph + jump

        p.save()
        if self.mirrored:
            # 过中线镜像：整体水平翻转（气泡文字保持可读）
            p.translate(cx, 0)
            p.scale(-1, 1)
            p.translate(-cx, 0)
        p.translate(cx, bottom)
        p.rotate(sway)
        p.translate(-cx, -bottom)
        p.drawImage(QRectF(dx, dy, pw, ph), self.whale_img)
        p.restore()

    _STYLE_FONT = {
        "A": (15, False),
        "B": (26, True),
        "P": (20, True),
        "C": (12, False),
    }
    _STYLE_COLOR = {
        "A": QColor("#536ba9"),
        "B": QColor("#536ba9"),
        "P": QColor("#536ba9"),
        "C": QColor("#9fb0d9"),
    }

    def _draw_bubble(self, p):
        max_w = min(260, self.width() - 16)
        inner = self.bubble_inner
        bg = QColor(232, 232, 238, 235) if inner else QColor(255, 255, 255, 235)
        fg = QColor(125, 125, 138) if inner else QColor(60, 60, 80)
        border = QColor("#203170") if not inner else QColor(150, 150, 165, 120)

        segments = []  # (text, font, color)
        for text, style, color, wrap in self.bubble_lines:
            size, bold = self._STYLE_FONT.get(style, self._STYLE_FONT["A"])
            font = QFont("Microsoft YaHei UI", size)
            font.setBold(bold)
            if inner:
                font.setItalic(True)
            fm = QFontMetrics(font)
            col = QColor(color) if color else self._STYLE_COLOR.get(style, self._STYLE_COLOR["A"])
            if wrap:
                cur = ""
                for ch in text:
                    if fm.horizontalAdvance(cur + ch) > max_w - 24 and cur:
                        segments.append((cur, font, col))
                        cur = ch
                    else:
                        cur += ch
                if cur:
                    segments.append((cur, font, col))
            else:
                segments.append((text, font, col))

        line_h = QFontMetrics(QFont("Microsoft YaHei UI", 15)).height()
        heights = [QFontMetrics(f).height() for _, f, _ in segments]
        line_h = max(heights) if heights else line_h
        bw = max(QFontMetrics(f).horizontalAdvance(t) for t, f, _ in segments) + 24
        bh = sum(heights) + 14
        bx = (self.width() - bw) / 2
        by = 6.0
        self.bubble_rect = QRectF(bx, by, bw, bh)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(self.bubble_rect, 10, 10)
        tail_x = self.width() / 2
        tail = QPolygonF([
            QPointF(tail_x, by + bh),
            QPointF(tail_x - 7, by + bh + 9),
            QPointF(tail_x + 7, by + bh + 9),
        ])
        p.setBrush(bg)
        p.drawPolygon(tail)
        p.setPen(border)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(self.bubble_rect, 10, 10)

        y = by + 7
        for text, font, col in segments:
            fh = QFontMetrics(font).height()
            p.setPen(fg if inner else col)
            p.setFont(font)
            p.drawText(QRectF(bx, y, bw, fh), Qt.AlignmentFlag.AlignCenter, text)
            y += fh

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_state = True
            self.drag_start = e.globalPosition().toPoint()
            self.dragging = False
            self.drag_offset = None
            self.sound.play_press()

    def mouseMoveEvent(self, e):
        if self._press_state and self.drag_start is not None:
            delta = e.globalPosition().toPoint() - self.drag_start
            if not self.dragging and delta.manhattanLength() > DRAG_THRESHOLD:
                self.dragging = True
                self.drag_offset = e.globalPosition().toPoint() - QPoint(self.x(), self.y())
            if self.dragging and self.drag_offset is not None:
                self.move(e.globalPosition().toPoint() - self.drag_offset)
                # 拖拽中穿过屏幕中线 → 实时镜像/还原
                self._update_mirror()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._press_state = False
        self.sound.play_release()
        if self.dragging:
            self.dragging = False
            self.drag_offset = None
            self.drag_start = None
            self.snap_settle()
            self.save_cfg()
            if random.random() < 0.5 and self._drag_lines:
                self.say(random.choice(self._drag_lines))
        else:
            # 单击 = 台词表循环：随机说一句台词表的词，说完自动回落常驻余额气泡
            self.drag_start = None
            self.show_click_line()
            self.refresh(True)
            self.jump_t = 1.0
        self.update()

    def contextMenuEvent(self, e):
        build_menu(self).exec(e.globalPos())

    # ---------- 菜单回调 ----------
    def set_persistent(self, on):
        self.cfg["persistent_bubble"] = bool(on)
        self.persistent = bool(on)
        self.save_cfg()
        if on:
            self.show_bubble()
        elif self.bubble_visible and not self.bubble_random:
            self.hide_bubble()

    def set_usage_mode(self, mode):
        self.cfg["usage_mode"] = "token" if mode == "token" else "ledger"
        self.save_cfg()
        self.say("已切换为" + ("实时·令牌" if self.cfg["usage_mode"] == "token" else "小鲸鱼记账") + "~")
        self.refresh(True)

    def set_sound_set(self, name):
        self.sound.apply_set(name)
        self.cfg["sound_set"] = self.sound.sound_set
        self.save_cfg()

    def set_volume(self, v):
        self.sound.set_volume(v)
        self.cfg["vol"] = round(self.sound.volume, 2)
        self.cfg["sound_on"] = self.sound.enabled
        self.save_cfg()

    def set_topmost(self, on):
        self.cfg["topmost"] = bool(on)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(on))
        self.show()
        self.save_cfg()

    def set_passthrough(self, on):
        self.cfg["passthrough"] = bool(on)
        self._apply_passthrough(bool(on))
        self.save_cfg()

    def _apply_passthrough(self, on):
        hwnd = int(self.winId())
        GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT = -20, 0x80000, 0x20
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED
        if on:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)

    def set_autostart(self, on):
        from menu import set_autostart as _do_autostart
        _do_autostart(self, bool(on))

    def toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def say(self, text):
        self.bubble_visible = True
        self.bubble_random = True
        self.bubble_inner = False
        self.bubble_lines = [(text, "A", "", True)]
        self.bubble_until = self.t * TICK + BUBBLE_MS
        self.update()

    def quit_app(self):
        self.save_cfg()
        QApplication.quit()
