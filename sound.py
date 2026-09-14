# -*- coding: utf-8 -*-
"""sound.py —— 音效：按压/松手，小黄鸭/音效1 两套，音量控制。

两段式后端（修复"音效完全不出声"）：
  1) **QSoundEffect**（低延迟，适合 UI 反馈音）——Qt 官方仅支持**未压缩音频**（典型是 WAV），
     所以每个音效的首选源是 `assets/*.wav`；
  2) 若 QSoundEffect 加载失败（`Status.Error`，例如只找到 mp3），**自动回落 QMediaPlayer**
     （支持 mp3 等压缩格式），保证"按压有声"这个基本体验不丢。

源按优先级尝试：`.wav` → `.mp3`；都缺失时静默降级（不发声）并写日志。
"""
import os

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect

from log import get_logger

# 每个音效给出候选源（按优先级）
SOUND_FILES = {
    "duck": {"press": ("Ya1.wav", "Ya1.mp3"), "release": ("Ya2.wav", "Ya2.mp3")},
    "fx1": {"press": ("D1.wav", "D1.mp3"), "release": ("D2.wav", "D2.mp3")},
}


class _Clip:
    """单个音效片段：QSoundEffect 优先，加载失败自动回落 QMediaPlayer。"""

    def __init__(self, assets_dir: str, candidates, label: str):
        self.assets_dir = assets_dir
        self.label = label
        self.filename = None
        self.backend = "none"          # none / effect / media
        self.volume = 0.9
        self._effect = QSoundEffect()
        self._effect.setLoopCount(1)
        self._effect.statusChanged.connect(self._on_status_changed)
        self._player = None
        self._out = None
        self.set_source(candidates)

    # ---------- 源 ----------
    def set_source(self, candidates) -> None:
        """按优先级挑选存在的源文件；都缺失则 backend='none'。"""
        self._teardown_player()
        self._effect.setSource(QUrl())
        self.backend = "none"
        self.filename = None
        for filename in candidates:
            path = os.path.join(self.assets_dir, filename)
            if os.path.exists(path):
                self.filename = filename
                self._effect.setVolume(self.volume)
                self._effect.setSource(QUrl.fromLocalFile(path))
                self.backend = "effect"
                return
        get_logger().warning("音效资源缺失: %s 候选=%s", self.label, list(candidates))

    def _teardown_player(self) -> None:
        if self._player is not None:
            self._player.stop()
            self._player = None
        self._out = None

    def _on_status_changed(self) -> None:
        """QSoundEffect 只支持未压缩音频：一旦 Error 就换 QMediaPlayer 后端。"""
        if self.backend != "effect" or not self.filename:
            return
        if self._effect.status() != QSoundEffect.Status.Error:
            return
        path = os.path.join(self.assets_dir, self.filename)
        get_logger().info("QSoundEffect 加载失败(Error)，回落 QMediaPlayer: %s (%s)", self.filename, self.label)
        self._effect.setSource(QUrl())
        self._player = QMediaPlayer()
        self._out = QAudioOutput()
        self._player.setAudioOutput(self._out)
        self._out.setVolume(self.volume)
        self._player.setSource(QUrl.fromLocalFile(path))
        self.backend = "media"

    # ---------- 控制 ----------
    def set_volume(self, vol: float) -> None:
        self.volume = max(0.0, min(1.0, float(vol)))
        self._effect.setVolume(self.volume)
        if self._out is not None:
            self._out.setVolume(self.volume)

    def play(self) -> bool:
        if self.backend == "effect":
            if self._effect.status() == QSoundEffect.Status.Ready:
                self._effect.play()
                return True
            return False
        if self.backend == "media" and self._player is not None:
            self._player.setPosition(0)
            self._player.play()
            return True
        return False

    def stop(self) -> None:
        self._effect.stop()
        if self._player is not None:
            self._player.stop()

    def status_text(self) -> str:
        if self.backend == "media":
            return "media:" + str(self._player.mediaStatus())
        return "effect:" + str(self._effect.status())


class SoundManager:
    """音效管理：两套音效组 + 音量 + 开关。"""

    def __init__(self, assets_dir: str):
        self.assets_dir = assets_dir
        self.sound_set = "duck"
        self.sound_on = True
        self.enabled = True
        self.volume = 0.9
        self._clips = {}
        self.apply_set("duck")

    def apply_set(self, name: str) -> None:
        """切换音效组：duck（小黄鸭）/ fx1（音效1）。"""
        files = SOUND_FILES.get(name, SOUND_FILES["duck"])
        self.sound_set = "duck" if name != "fx1" else "fx1"
        self._clips = {
            role: _Clip(self.assets_dir, candidates, "%s/%s" % (self.sound_set, role))
            for role, candidates in files.items()
        }
        for clip in self._clips.values():
            clip.set_volume(self.volume)

    def set_volume(self, vol: float) -> None:
        self.volume = max(0.0, min(1.0, float(vol)))
        self._refresh_enabled()
        for clip in self._clips.values():
            clip.set_volume(self.volume)

    def set_enabled(self, on: bool) -> None:
        """独立音效开关（config 的 sound_on），与音量解耦。"""
        self.sound_on = bool(on)
        self._refresh_enabled()

    def _refresh_enabled(self) -> None:
        self.enabled = bool(self.sound_on) and self.volume > 0

    def play_press(self) -> bool:
        if not self.enabled:
            return False
        self._clips["release"].stop()
        return self._clips["press"].play()

    def play_release(self) -> bool:
        if not self.enabled:
            return False
        return self._clips["release"].play()
