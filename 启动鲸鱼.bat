@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "鲸鱼.py"
) else (
    start "" pythonw "鲸鱼.py"
)
