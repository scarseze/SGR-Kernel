<#
.SYNOPSIS
Runs the SGR Kernel Locust Load Tests in headless mode.

.DESCRIPTION
This script executes a load test against the locally running SGR Kernel API
using Locust. It overrides the default test behavior to run in headless mode
for a specific duration and saves a report.

.EXAMPLE
.\run_load_test.ps1 -Users 50 -SpawnRate 10 -Duration "30s"
#>

Param(
    [int]$Users = 50,
    [int]$SpawnRate = 10,
    [string]$Duration = "30s",
    [string]$HostUrl = "http://localhost:8000"
)

$LocustFile = "tests\load\locustfile.py"

Write-Host "🚀 Starting SGR Kernel Load Test..." -ForegroundColor Cyan
Write-Host "Users: $Users, Spawn Rate: $SpawnRate, Duration: $Duration, Target: $HostUrl" -ForegroundColor Yellow

# Ensure locust is installed
if (-not (Get-Command locust -ErrorAction SilentlyContinue)) {
    Write-Host "⚠️ Locust is not installed. Installing via pip..." -ForegroundColor DarkYellow
    pip install locust
}

# Run headless load test
locust -f $LocustFile --headless -u $Users -r $SpawnRate --run-time $Duration --host $HostUrl --print-stats

Write-Host "✅ Load Test Completed." -ForegroundColor Green
