@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo 未找到 uv。请先按 README.md 安装 uv，然后重新打开终端或本启动脚本。
  pause
  exit /b 1
)
set "PYTHONUTF8=1"
uv run --locked meowcannery gui
if errorlevel 1 (
  echo 启动失败。请检查以上错误，并按 README.md 配置环境。
  pause
  exit /b 1
)
