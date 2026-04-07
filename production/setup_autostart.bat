@echo off
chcp 65001 >nul
title 设置开机自启

echo ========================================
echo 向量记忆库API服务 - 设置开机自启
echo ========================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 需要管理员权限！
    echo [操作] 请右键此文件，选择"以管理员身份运行"
    pause
    exit /b 1
)

echo [信息] 正在创建计划任务...
echo.

:: 创建启动脚本（后台运行）
echo Set WshShell = WScript.CreateObject("WScript.Shell") > "C:\Users\Administrator\.openclaw\production\start_vector_api_hidden.vbs"
echo WshShell.Run "cmd /c cd /d C:\Users\Administrator\.openclaw\production\data\vector_store && pythonw api_server.py", 0, False >> "C:\Users\Administrator\.openclaw\production\start_vector_api_hidden.vbs"

:: 创建计划任务
schtasks /create /tn "VectorMemoryAPI" /tr "wscript.exe \"C:\Users\Administrator\.openclaw\production\start_vector_api_hidden.vbs\"" /sc onstart /rl highest /f

if %errorLevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ 开机自启设置成功！
    echo ========================================
    echo.
    echo 任务名称: VectorMemoryAPI
    echo 启动文件: start_vector_api_hidden.vbs
    echo.
    echo 管理方式:
    echo   - 查看: schtasks /query /tn VectorMemoryAPI
    echo   - 删除: schtasks /delete /tn VectorMemoryAPI /f
    echo.
) else (
    echo.
    echo [错误] 创建任务失败
    echo.
)

pause
