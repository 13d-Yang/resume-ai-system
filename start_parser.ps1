# ============================================================
# 一键启动 HTTP 网关服务（端口 8501，对接 JeecgBoot 前端）
# 请先启动 start_mcp（8604），再启动本脚本。
# ============================================================
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:ZHIPU_API_KEY     = [Environment]::GetEnvironmentVariable("ZHIPU_API_KEY", "User")
$env:SILICONFLOW_API_KEY = [Environment]::GetEnvironmentVariable("SILICONFLOW_API_KEY", "User")

if (-not $env:ZHIPU_API_KEY) {
    Write-Host "[错误] 未设置永久环境变量 ZHIPU_API_KEY" -ForegroundColor Red
    Read-Host "按回车退出"; exit 1
}

Write-Host "密钥加载完成，正在启动网关服务 http://0.0.0.0:8501 ..." -ForegroundColor Cyan
.\venv310\Scripts\python.exe mcp_parser.py
