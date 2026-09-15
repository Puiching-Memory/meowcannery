@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 未找到 Python 环境。请先按 README.md 完成安装。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 -m meowcannery gui
if errorlevel 1 pause
