param(
    [string]$Environment = "eki-prod-final",
    [switch]$SkipPrecheck,
    [switch]$NoHealthCheck
)

$ErrorActionPreference = "Stop"

function Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

if (-not $SkipPrecheck) {
    Info "Running precheck..."
    & ".\scripts\eb_precheck_main.ps1"
    if ($LASTEXITCODE -ne 0) {
        Fail "Precheck failed. Abort deploy."
        exit 1
    }
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$label = "main-$timestamp"

Info "Environment: $Environment"
Info "Deploy label: $label"

# Snapshot current deployed version for rollback
$before = eb status $Environment | Select-String -Pattern "Deployed Version:\s*(.+)$"
$previousVersion = $null
if ($before) {
    $previousVersion = $before.Matches[0].Groups[1].Value.Trim()
    Ok "Current deployed version: $previousVersion"
}

Info "Starting eb deploy..."
eb deploy $Environment --label $label
if ($LASTEXITCODE -ne 0) {
    Fail "eb deploy failed"
    exit 1
}
Ok "Deploy command completed"

Info "Checking environment health..."
eb health $Environment
if ($LASTEXITCODE -ne 0) {
    Fail "eb health reported error"
    exit 1
}

if (-not $NoHealthCheck) {
    # Resolve CNAME from eb status output and hit /health/
    $statusText = eb status $Environment
    $cnameLine = $statusText | Select-String -Pattern "CNAME:\s*(.+)$"
    if ($cnameLine) {
        $cname = $cnameLine.Matches[0].Groups[1].Value.Trim()
        $healthUrl = "http://$cname/health/"
        Info "Smoke test: $healthUrl"
        try {
            $resp = Invoke-WebRequest -Uri $healthUrl -Method GET -TimeoutSec 20
            if ($resp.StatusCode -eq 200) {
                Ok "Health check OK (200)"
            } else {
                Fail "Health check returned $($resp.StatusCode)"
                exit 1
            }
        } catch {
            Fail "Health check failed: $($_.Exception.Message)"
            exit 1
        }
    } else {
        Fail "Could not resolve CNAME from eb status"
        exit 1
    }
}

Write-Host ""
Ok "Deployment completed"
Write-Host "Rollback command (if needed):" -ForegroundColor Yellow
if ($previousVersion) {
    Write-Host "eb deploy $Environment --version $previousVersion" -ForegroundColor White
} else {
    Write-Host "eb deploy $Environment --version <previous_version_label>" -ForegroundColor White
}
