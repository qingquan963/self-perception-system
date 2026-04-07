@echo off
REM uninstall_services.bat - Windows 服务卸载脚本
REM
REM 使用方法:
REM   双击运行此脚本（需要管理员权限）

setlocal enabledelayedexpansion

echo ============================================================
echo  Self-Perception System - Windows 服务卸载
echo ============================================================
echo.

REM 停止并卸载服务
echo 停止并卸载 supervisor 服务...
net stop SelfPerceptionSupervisor >nul 2>&1
nssm remove SelfPerceptionSupervisor confirm

echo.
echo 停止并卸载 watchdog 服务...
net stop SelfPerceptionWatchdog >nul 2>&1
nssm remove SelfPerceptionWatchdog confirm

echo.
echo ============================================================
echo  卸载完成
echo ============================================================
pause
