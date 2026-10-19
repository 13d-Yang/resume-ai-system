# ============================================================
# 一键启动 MCP 服务（端口 8604）
# 作用：自动从 Windows 永久环境变量读取两个 API Key 注入本窗口，
#       再用 venv310 启动服务。无论终端是何时打开的都能拿到最新 Key。
# 用法：双击同目录的 start_mcp.bat，或在本目录执行 ./start_mcp.ps1
# ============================================================
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:ZHIPU_API_KEY     = [Environment]::GetEnvironmentVariable("ZHIPU_API_KEY", "User")
$env:SILICONFLOW_API_KEY = [Environment]::GetEnvironmentVariable("SILICONFLOW_API_KEY", "User")

if (-not $env:ZHIPU_API_KEY) {
    Write-Host "[错误] 未设置永久环境变量 ZHIPU_API_KEY" -ForegroundColor Red
    Read-Host "按回车退出"; exit 1
}
if (-not $env:SILICONFLOW_API_KEY) {
    Write-Host "[错误] 未设置永久环境变量 SILICONFLOW_API_KEY" -ForegroundColor Red
    Read-Host "按回车退出"; exit 1
}

Write-Host "密钥加载完成（智谱长度 $($env:ZHIPU_API_KEY.Length)，硅基流动长度 $($env:SILICONFLOW_API_KEY.Length)）" -ForegroundColor Green
Write-Host "正在启动 MCP 服务 http://127.0.0.1:8604/sse ..." -ForegroundColor Cyan
.\venv310\Scripts\python.exe -m app.server_mcp
