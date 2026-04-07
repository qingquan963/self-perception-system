# 精简自我感知系统 - 服务启动脚本
# 服务：api_service (8011)、vector_service (8007)、frontend (8090)
# 此脚本由注册表 Run 键在开机时调用
# 使用 WScript.Shell 启动独立进程，确保子进程在脚本退出后继续存活

$PROJECT = "c:\Users\Administrator\.openclaw\workspace\self_perception_simple_clean"
$PYTHON  = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$LOG_DIR = "$PROJECT\logs"

if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR | Out-Null }

# 使用 WScript.Shell 启动完全独立的后台进程（不依附父进程生命周期）
$wsh = New-Object -ComObject WScript.Shell

function Start-DetachedService {
    param($Name, $Port, $CmdLine, $WorkDir)

    $listening = netstat -ano | Select-String "127\.0\.0\.1:$Port\s.*LISTENING"
    if ($listening) {
        Write-Host "[$Name] Port $Port already in use, skipping."
        return
    }

    $logFile  = "$LOG_DIR\${Name}.log"
    $errFile  = "$LOG_DIR\${Name}_err.log"

    # cmd /c 启动后台进程，重定向日志，0=隐藏窗口，false=不等待
    $fullCmd = "cmd /c `"cd /d `"$WorkDir`" && $CmdLine >> `"$logFile`" 2>> `"$errFile`"`""
    $wsh.Run($fullCmd, 0, $false)
    Write-Host "[$Name] Started on port $Port"
}

# 1. API Service (port 8011)
Start-DetachedService `
    -Name "api_service" `
    -Port 8011 `
    -CmdLine "`"$PYTHON`" -m uvicorn api_service:app --host 127.0.0.1 --port 8011 --log-level warning" `
    -WorkDir $PROJECT

Start-Sleep -Seconds 3

# 2. Vector Service (port 8007)
Start-DetachedService `
    -Name "vector_service" `
    -Port 8007 `
    -CmdLine "`"$PYTHON`" -m uvicorn vector_service:app --host 127.0.0.1 --port 8007 --log-level warning" `
    -WorkDir $PROJECT

Start-Sleep -Seconds 3

# 3. Frontend Dashboard (port 8090)
Start-DetachedService `
    -Name "frontend" `
    -Port 8090 `
    -CmdLine "`"$PYTHON`" -m http.server 8090 --bind 127.0.0.1" `
    -WorkDir "$PROJECT\frontend"

Write-Host "All services started."
