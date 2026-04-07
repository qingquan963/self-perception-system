@echo off
REM install_services.bat - Windows 服务注册脚本 (使用 nssm)
REM 需要先安装 nssm: https://nssm.cc/download
REM
REM 使用方法:
REM   1. 下载 nssm.exe 到项目目录
REM   2. 双击运行此脚本（需要管理员权限）

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
set "PYTHON=%PYTHON_EXE%"
set "NSSM=nssm.exe"

echo ============================================================
echo  Self-Perception System - Windows 服务注册
echo ============================================================
echo.

REM 检查 nssm 是否存在
if not exist "%PROJECT_DIR%%NSSM%" (
    echo [错误] nssm.exe 未找到，请先下载并放置到项目目录
    echo 下载地址: https://nssm.cc/release/nssm-2.24.zip
    pause
    exit /b 1
)

REM 检查 Python
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 未找到，请确保已安装 Python
    pause
    exit /b 1
)

echo [1/4] 注册 supervisor 服务...
"%NSSM%" install SelfPerceptionSupervisor "%PYTHON%" "supervisor.py"
"%NSSM%" set SelfPerceptionSupervisor AppDirectory "%PROJECT_DIR%"
"%NSSM%" set SelfPerceptionSupervisor AppStdout "%PROJECT_DIR%data\logs\supervisor_stdout.log"
"%NSSM%" set SelfPerceptionSupervisor AppStderr "%PROJECT_DIR%data\logs\supervisor_stderr.log"
"%NSSM%" set SelfPerceptionSupervisor Description "Self-Perception System Supervisor"
"%NSSM%" set SelfPerceptionSupervisor Start SERVICE_AUTO_START
"%NSSM%" set SelfPerceptionSupervisor ObjectName LocalSystem
echo.

echo [2/4] 注册 watchdog 服务...
"%NSSM%" install SelfPerceptionWatchdog "%PYTHON%" "watchdog.py"
"%NSSM%" set SelfPerceptionWatchdog AppDirectory "%PROJECT_DIR%"
"%NSSM%" set SelfPerceptionWatchdog AppStdout "%PROJECT_DIR%data\logs\watchdog_stdout.log"
"%NSSM%" set SelfPerceptionWatchdog AppStderr "%PROJECT_DIR%data\logs\watchdog_stderr.log"
"%NSSM%" set SelfPerceptionWatchdog Description "Self-Perception System Watchdog"
"%NSSM%" set SelfPerceptionWatchdog Start SERVICE_AUTO_START
"%NSSM%" set SelfPerceptionWatchdog ObjectName LocalSystem
REM watchdog 依赖 supervisor
"%NSSM%" set SelfPerceptionWatchdog DependOnService SelfPerceptionSupervisor
echo.

echo [3/4] 启动服务...
net start SelfPerceptionSupervisor
net start SelfPerceptionWatchdog
echo.

echo [4/4] 服务状态:
echo.
"%NSSM%" status SelfPerceptionSupervisor
"%NSSM%" status SelfPerceptionWatchdog
echo.

echo ============================================================
echo  安装完成！
echo ============================================================
echo.
echo  常用命令:
echo    net start SelfPerceptionSupervisor  - 启动 supervisor
echo    net stop SelfPerceptionSupervisor   - 停止 supervisor
echo    nssm restart SelfPerceptionSupervisor - 重启 supervisor
echo.
echo  卸载命令:
echo    nssm remove SelfPerceptionSupervisor confirm
echo    nssm remove SelfPerceptionWatchdog confirm
echo.
pause
