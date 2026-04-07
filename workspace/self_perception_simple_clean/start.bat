@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 自我感知 + 做梦模式 整合系统

echo ==============================================
echo    记忆系统启动脚本 (Windows)
echo ==============================================
echo.

cd /d "%~dp0"

:: 检查 Docker
where docker >nul 2>&1
set DOCKER_FOUND=%ERRORLEVEL%

:: 检查参数
if "%~1"=="--docker" goto docker_mode
if "%~1"=="--python" goto python_mode

:: 菜单
echo [模式选择]
echo   1) Docker 容器（推荐，需要 Docker Desktop）
echo   2) 直接运行 Python
echo.
set /p choice="请选择 [1/2]: "

if "!choice!"=="1" goto docker_mode
if "!choice!"=="2" goto python_mode
echo [错误] 无效选项
exit /b 1

:docker_mode
if %DOCKER_FOUND% neq 0 (
    echo [错误] 未安装 Docker，请先安装 Docker Desktop
    echo   下载: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

echo [1/2] 构建并启动容器...
docker compose up -d --build

echo.
echo [2/2] 等待服务就绪...
timeout /t 10 /nobreak >nul

echo.
echo ==============================================
echo ✅ 启动完成！
echo ==============================================
echo.
echo   向量记忆服务:  http://localhost:8007
echo   自我感知 API:   http://localhost:8011
echo   做梦模式:       http://localhost:8001
echo   Compaction:     http://localhost:8014
echo   前端仪表板:     http://localhost:8090
echo.
echo   停止:   docker compose down
echo   日志:   docker compose logs -f
echo.
pause
exit /b 0

:python_mode
echo [Python] 检查依赖...
if exist requirements.txt (
    pip install -r requirements.txt >nul 2>&1
)
pip install httpx chromadb sentence-transformers psutil pyyaml structlog >nul 2>&1

echo.
echo 启动看门狗（guardian）...
python watchdog.py
exit /b 0
