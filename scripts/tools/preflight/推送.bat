@echo off
rem 推送入口（Windows）：预检通过后自动推送
rem 档位按待推提交自动选（全文档→快速档 / 含代码→定向档）；工作树脏即拒
rem 用法: 推送.bat [--full] [--remote origin] [--branch <分支>] [--jobs auto|N|off]
rem
rem 启动解释器只用仓内 venv；engkit 本身由 `uv run --project backend` 在仓内环境执行。
rem 原写法用 PATH 上的 python，且文件为 LF 行尾，cmd 解析多行块会错乱（实测执行报错）。
setlocal
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\..\.." || exit /b 2
set "VENV_PY=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [推送] 未找到仓内解释器：%VENV_PY%
  echo   请先按《开发机部署使用说明》准备 backend\.venv（依赖外置时先还原依赖再同步）。
  exit /b 2
)

"%VENV_PY%" "scripts\tools\preflight\推送.py" %*
exit /b %errorlevel%
