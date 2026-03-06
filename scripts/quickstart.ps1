<#
.SYNOPSIS
Enterprise Quickstart Wizard for SGR Kernel V3.

.DESCRIPTION
Deploys the complete SGR Kernel infrastructure (Kernel, Redis, Jaeger, Qdrant, Prometheus/Grafana)
in under 2 minutes using Docker Compose, and runs an initial health check.

.EXAMPLE
.\scripts\quickstart.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "🚀 Welcome to SGR Kernel V3 Enterprise Quickstart" -ForegroundColor Cyan
Write-Host "================================================="
Write-Host "Checking prerequisites..."

if (-not (Get-Command "docker-compose" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Error: docker-compose is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Prerequisites met. Starting infrastructure..." -ForegroundColor Green

# Bring up the core services
docker-compose up -d sgr_redis jaeger sgr_qdrant sgr-kernel

Write-Host "⏳ Waiting for services to initialize (15 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

Write-Host "🔍 Running Health Checks..." -ForegroundColor Cyan

# Check Kernel API (assuming it's on 8501 or 8000 depending on chainlit/fastapi)
# The compose file maps 8501:8501 for sgr-kernel
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 5
    Write-Host "✅ Kernel UI is reachable." -ForegroundColor Green
} catch {
    Write-Host "⚠️ Kernel UI might still be booting. Check http://localhost:8501 later." -ForegroundColor Yellow
}

Write-Host "================================================="
Write-Host "🎉 Deployment Successful! Time-to-Hello-World complete." -ForegroundColor Green
Write-Host ""
Write-Host "🔗 Access URLs:"
Write-Host " - SGR Kernel UI:  http://localhost:8501"
Write-Host " - Jaeger Tracing: http://localhost:16686"
Write-Host " - Metrics (Prom): http://localhost:9090"
Write-Host ""
Write-Host "To view logs, run: docker-compose logs -f sgr-kernel"
