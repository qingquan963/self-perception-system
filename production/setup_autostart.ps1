# 向量记忆库API服务 - 开机自启脚本
# 创建时间：2026-03-24

$TaskName = "VectorMemoryAPI"
$ScriptPath = "C:\Users\Administrator\.openclaw\production\start_vector_api_background.ps1"

# 创建后台启动脚本
$BackgroundScript = @'
Start-Process python -ArgumentList "C:\Users\Administrator\.openclaw\production\data\vector_store\api_server.py" -WindowStyle Hidden -RedirectStandardOutput "C:\Users\Administrator\.openclaw\production\logs\api_stdout.log" -RedirectStandardError "C:\Users\Administrator\.openclaw\production\logs\api_stderr.log"
'@

Set-Content -Path $ScriptPath -Value $BackgroundScript -Encoding UTF8

# 创建计划任务
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 注册任务
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -User "Administrator" -RunLevel Highest -Force

Write-Host "✅ 开机自启任务已创建: $TaskName"
Write-Host "📝 后台启动脚本: $ScriptPath"
Write-Host ""
Write-Host "手动启动服务命令:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$ScriptPath`""
