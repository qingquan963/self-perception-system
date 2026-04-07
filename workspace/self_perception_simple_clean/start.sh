#!/bin/bash
# =============================================
# 自我感知 + 做梦模式 整合系统
# 启动脚本 (Linux / Mac)
# =============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "   记忆系统启动脚本 (Linux/Mac)"
echo "=============================================="
echo ""

# Docker 检查
docker_available() {
    command -v docker &> /dev/null
}

docker_ready() {
    docker info &> /dev/null
}

case "${1:-}" in
    --docker)
        MODE=docker
        ;;
    --python)
        MODE=python
        ;;
    "")
        if docker_available && docker_ready; then
            echo "[信息] 检测到 Docker"
            MODE=menu
        else
            MODE=python
        fi
        ;;
    *)
        echo "[错误] 未知参数: $1"
        echo "用法: $0 [--docker|--python]"
        exit 1
        ;;
esac

if [ "$MODE" = "menu" ]; then
    echo "[模式选择]"
    echo "  1) Docker 容器（推荐）"
    echo "  2) 直接运行 Python"
    echo ""
    read -p "请选择 [1/2]: " choice
    case "$choice" in
        1) MODE=docker ;;
        2) MODE=python ;;
        *) echo "[错误] 无效选项"; exit 1 ;;
    esac
fi

# ── Docker 模式 ──────────────────────────────────────────────────
if [ "$MODE" = "docker" ]; then
    if ! docker_available; then
        echo "[错误] 未安装 Docker"
        echo "  Linux:   sudo apt install docker.io docker-compose"
        echo "  Mac:     https://www.docker.com/products/docker-desktop/"
        exit 1
    fi

    if ! docker_ready; then
        echo "[错误] Docker 未运行，请先启动 Docker"
        exit 1
    fi

    echo "[1/2] 构建并启动容器..."
    docker compose up -d --build

    echo ""
    echo "[2/2] 等待服务就绪..."
    sleep 10

    echo ""
    echo "=============================================="
    echo "✅ 启动完成！"
    echo "=============================================="
    echo ""
    echo "  向量记忆服务:  http://localhost:8007"
    echo "  自我感知 API:   http://localhost:8011"
    echo "  做梦模式:       http://localhost:8001"
    echo "  Compaction:     http://localhost:8014"
    echo "  前端仪表板:     http://localhost:8090"
    echo ""
    echo "  停止: docker compose down"
    echo "  日志: docker compose logs -f"
    echo ""

# ── Python 模式 ─────────────────────────────────────────────────
else
    echo "[Python] 检查依赖..."
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt 2>/dev/null || true
    fi
    pip install httpx chromadb sentence-transformers psutil pyyaml structlog 2>/dev/null || true

    echo ""
    echo "启动看门狗（guardian）..."
    echo ""
    python3 watchdog.py
fi
