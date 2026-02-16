# Git initialization script for Windows
# Prepares repository for first commit

Write-Host "================================" -ForegroundColor Cyan
Write-Host "GIT INITIALIZATION" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check if git is installed
try {
    git --version | Out-Null
} catch {
    Write-Host "ERROR: Git is not installed" -ForegroundColor Red
    exit 1
}

# Check if already initialized
if (Test-Path ".git" -PathType Container) {
    Write-Host "Git repository already initialized" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Current status:" -ForegroundColor Cyan
    git status --short
    Write-Host ""
    $response = Read-Host "Do you want to commit current changes? (y/n)"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "Aborted" -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "Initializing git repository..." -ForegroundColor Cyan
    git init
    Write-Host "Git repository initialized" -ForegroundColor Green
}

# Verify .gitignore exists
if (-not (Test-Path ".gitignore")) {
    Write-Host "ERROR: .gitignore not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Checking .gitignore..." -ForegroundColor Cyan
$gitignoreContent = Get-Content ".gitignore" -Raw
if ($gitignoreContent -match "\.env|db\.sqlite3|__pycache__|\.pyc|media/|staticfiles/") {
    Write-Host "OK: .gitignore contains essential patterns" -ForegroundColor Green
} else {
    Write-Host "WARNING: .gitignore may be incomplete" -ForegroundColor Yellow
}

# Check for sensitive files
Write-Host ""
Write-Host "Checking for sensitive files..." -ForegroundColor Cyan
$sensitiveFiles = @()

if (Test-Path ".env") {
    $sensitiveFiles += ".env"
}

if (Test-Path ".env.production") {
    $sensitiveFiles += ".env.production"
}

if ($sensitiveFiles.Count -gt 0) {
    Write-Host "WARNING: Found sensitive files:" -ForegroundColor Yellow
    foreach ($file in $sensitiveFiles) {
        Write-Host "  - $file" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "These files should NOT be committed to git" -ForegroundColor Red
    Write-Host "Make sure they are in .gitignore" -ForegroundColor Yellow
    Write-Host ""
}

# Add all files
Write-Host ""
Write-Host "Staging files..." -ForegroundColor Cyan
git add .

# Show what will be committed
Write-Host ""
Write-Host "Files to be committed:" -ForegroundColor Cyan
git status --short

# Count files
$fileCount = (git diff --cached --numstat | Measure-Object).Count
Write-Host ""
Write-Host "Total files: $fileCount" -ForegroundColor White

# Ask for confirmation
Write-Host ""
$response = Read-Host "Proceed with commit? (y/n)"

if ($response -ne "y" -and $response -ne "Y") {
    Write-Host "Aborted. Files are staged but not committed." -ForegroundColor Yellow
    Write-Host "You can commit later with: git commit -m 'Your message'" -ForegroundColor Gray
    exit 0
}

# Commit
Write-Host ""
Write-Host "Creating commit..." -ForegroundColor Cyan

$commitMessage = @"
Initial commit: EKI MVP - cleaned and organized

- Removed all emojis from Python code
- Cleaned up 150+ temporary files
- Reorganized scripts into professional structure
- Created Docker deployment configuration
- Optimized dependencies for production
- Added comprehensive documentation
"@

git commit -m $commitMessage

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "GIT INITIALIZATION COMPLETE" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "1. Add remote: git remote add origin <your-repo-url>" -ForegroundColor White
Write-Host "2. Push to remote: git push -u origin main" -ForegroundColor White
Write-Host ""
Write-Host "To create a branch:" -ForegroundColor Green
Write-Host "  git checkout -b develop" -ForegroundColor White
Write-Host ""
Write-Host "To see commit history:" -ForegroundColor Green
Write-Host "  git log --oneline" -ForegroundColor White
