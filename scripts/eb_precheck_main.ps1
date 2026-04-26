param(
    [string]$PythonPath = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$errors = 0
$warnings = 0

function Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow; $script:warnings++ }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red; $script:errors++ }

Write-Host "Precheck main -> Elastic Beanstalk (eki-prod-final)" -ForegroundColor Cyan
Write-Host "----------------------------------------------------" -ForegroundColor Cyan

# 1) Basic files
$requiredFiles = @(
    "manage.py",
    "requirements.txt",
    "Procfile",
    ".elasticbeanstalk\config.yml",
    "mvp_project\settings.py",
    "mvp_project\urls.py"
)
foreach ($file in $requiredFiles) {
    if (Test-Path $file) { Ok "Found $file" } else { Fail "Missing $file" }
}

# 2) Validate git branch and cleanliness
$branch = (git branch --show-current).Trim()
if ($branch -ne "main") {
    Warn "Current branch is '$branch'. Recommended: main."
} else {
    Ok "Current branch is main"
}

$gitStatus = git status --porcelain
if ($gitStatus) {
    Warn "Working tree has local changes. Commit/stash before deploy."
} else {
    Ok "Working tree is clean"
}

# 3) Secrets safety
if (Test-Path ".gitignore") {
    $gitignore = Get-Content ".gitignore" -Raw
    if ($gitignore -match "(^|\n)\.env($|\n)" -or $gitignore -match "(^|\n)\.env\..*($|\n)") {
        Ok "Environment files appear ignored in .gitignore"
    } else {
        Warn "Could not confirm env ignores in .gitignore"
    }
} else {
    Fail ".gitignore not found"
}

# 4) Django checks
if (-not (Test-Path $PythonPath)) {
    Warn "Python path not found: $PythonPath (skipping manage.py check)"
} else {
    & $PythonPath manage.py check --deploy
    if ($LASTEXITCODE -eq 0) { Ok "manage.py check --deploy passed" } else { Fail "manage.py check --deploy failed" }
}

# 5) EB connectivity
$eb = Get-Command eb -ErrorAction SilentlyContinue
if ($eb) {
    Ok "EB CLI available"
    eb status eki-prod-final | Out-Null
    if ($LASTEXITCODE -eq 0) { Ok "EB status reachable for eki-prod-final" } else { Fail "Cannot reach EB environment" }
} else {
    Fail "EB CLI not available in PATH"
}

Write-Host ""
Write-Host "Result: $errors error(s), $warnings warning(s)" -ForegroundColor Cyan
if ($errors -gt 0) { exit 1 }
exit 0
