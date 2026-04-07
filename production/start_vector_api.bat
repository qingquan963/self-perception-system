@echo off
chcp 65001 >nul
title 向量记忆库API服务

echo ========================================
echo 向量记忆库API服务器启动脚本
echo ========================================
echo.

cd /d "C:\Users\Administrator\.openclaw\production\data\vector_store"

echo [启动] 正在启动API服务器...
echo [端口] 8000
echo.

start /min pythonw api_server.py

echo [完成] 服务已在后台启动
echo [验证] 访问 http://localhost:8000/api/v1/health
echo.
timeout /t 3 >nul
