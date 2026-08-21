# -*- coding: utf-8 -*-
"""sound.py —— 音效：按压/松手，小黄鸭/音效1 两套，音量控制。

用 QSoundEffect（低延迟，适合 UI 反馈音）。mp3 缺失时静默降级。
"""
import os

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

SOUND_FILES = {
    "duck": {"press": "Ya1.mp3", "release": "Ya2.mp3"},
    "fx1": {"press": "D1.mp3", "release": "D2.mp3"},
}


class SoundManager:
    def __init__(self, assets_dir: str):
        self.assets_dir = assets_dir
        self.sound_set = "duck"
        self.enabled = True
        self.volume = 0.9
        self._press = QSoundEffect()
        self._release = QSoundEffect()
        self._press.setLoopCount(1)
        self._release.setLoopCount(1)
        self.apply_set("duck")

    def _load(self, effect: QSoundEffect, filename: str) -> None:
        path = os.path.join(self.assets_dir, filename)
        if os.path.exists(path):
            effect.setSource(QUrl.fromLocalFile(path))
        else:
            effect.setSource(QUrl())

    def apply_set(self, name: str) -> None:
        """切换音效组：duck（小黄鸭）/ fx1（音效1）。"""
        files = SOUND_FILES.get(name, SOUND_FILES["duck"])
        self.sound_set = "duck" if name != "fx1" else "fx1"
        self._load(self._press, files["press"])
        self._load(self._release, files["release"])

    def set_volume(self, vol: float) -> None:
        self.volume = max(0.0, min(1.0, float(vol)))
        self.enabled = self.volume > 0
        self._press.setVolume(self.volume)
        self._release.setVolume(self.volume)

    def play_press(self) -> None:
        if not self.enabled or self._press.status() != QSoundEffect.Status.Ready:
            return
        self._release.stop()
        self._press.play()

    def play_release(self) -> None:
        if not self.enabled or self._release.status() != QSoundEffect.Status.Ready:
            return
        self._release.play()
