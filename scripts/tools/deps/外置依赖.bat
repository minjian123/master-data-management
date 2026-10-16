@echo off
chcp 65001 >nul
title 依赖外置（mdm 前端）
rem 入口：转调 外置依赖.py（单一实现；于 mdm 仓根执行，加 --dry-run 空跑）
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%外置依赖.py" %*
exit /b %errorlevel%
