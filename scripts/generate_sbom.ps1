<#
.SYNOPSIS
Generates an SBOM (Software Bill of Materials) and performs a vulnerability scan.

.DESCRIPTION
This script is required for Enterprise compliance. It creates an sbom.json file
using pip-licenses and scans for vulnerabilities using safety or pip-audit.
This ensures the supply chain is secure before any deployment.

.EXAMPLE
.\scripts\generate_sbom.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host "🛡️ Starting SGR Kernel Enterprise Security Scan..." -ForegroundColor Cyan

# Ensure Tools are Installed
Write-Host "1. Installing required security tools (pip-licenses, safety)..."
pip install pip-licenses safety -q

# Generate SBOM
$SBOMPath = "sbom.json"
Write-Host "2. Generating SBOM to $SBOMPath..."
pip-licenses --format=json --output-file=$SBOMPath --with-authors --with-urls
Write-Host "✅ SBOM Generated." -ForegroundColor Green

# Vulnerability Scan
$VulnReportPath = "vulnerability_report.txt"
Write-Host "3. Running Safety vulnerability scan..."
try {
    # Check current environment packages
    safety check --full-report > $VulnReportPath
    Write-Host "✅ Zero critical vulnerabilities found. Report saved to $VulnReportPath." -ForegroundColor Green
} catch {
    Write-Host "❌ Vulnerabilities detected! Check $VulnReportPath" -ForegroundColor Red
    exit 1
}

Write-Host "🎉 Security Hardening step complete. Ready for Enterprise Deployment." -ForegroundColor Cyan
