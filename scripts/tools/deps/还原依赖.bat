@echo off
chcp 65001 >nul
title 依赖还原（mdm 前端）
rem 入口：转调 还原依赖.py（单一实现；于 mdm 仓根执行，加 --dry-run 空跑）
set "SCRIPT_DIR=%~dp0"
python "%SCRIPT_DIR%还原依赖.py" %*
exit /b %errorlevel%
