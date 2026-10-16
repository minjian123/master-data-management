@echo off
chcp 65001 >nul
title 依赖重装（mdm 前后端）
rem 入口：转调 重装依赖.py（单一实现；于 mdm 仓根执行）
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%重装依赖.py" %*
exit /b %errorlevel%
