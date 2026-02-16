param(
  [string]$S3Bucket = "elasticbeanstalk-us-east-2-178773630934",
  [string]$Region = "us-east-2",
  [string]$AppName = "eki_produccion",
  [string]$EnvName = "produccion-maint-20260129032112",
  [string]$VersionLabel = $("deploy-fixed-clean-" + (Get-Date -Format yyyyMMdd_HHmmss))
)

Write-Output "Preparing clean ZIP with label: $VersionLabel"

# Files/paths to exclude
$excludes = @(
  ".venv",
  "*.pyc",
  "__pycache__",
  "db.sqlite3",
  ".git",
  ".git/*",
  ".vscode",
  "node_modules",
  ".platform/hooks/prebuild/*",
  ".platform/hooks/prebuild",
  "tmp_deploy_*"
)

# Build list of files to include
$cwd = Get-Location
$tmpDir = Join-Path $env:TEMP ("deploy_tmp_" + [System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $tmpDir | Out-Null

Write-Output "Copying files to temporary dir: $tmpDir"

Get-ChildItem -Path $cwd -Force | Where-Object {
  $path = $_.FullName.Replace($cwd.Path + '\\','')
  # Exclude patterns
  -not ($excludes | ForEach-Object { $pattern = $_; if ($pattern -like "*/*") { $false } ; ($_ -like $pattern -or $path -like $pattern -or $path -like ("*" + $pattern)) })
} | ForEach-Object {
  $dest = Join-Path $tmpDir $_.Name
  if ($_.PSIsContainer) { Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue } else { Copy-Item -Path $_.FullName -Destination $dest -Force -ErrorAction SilentlyContinue }
}

$zipName = "$PWD\deploy-clean-$VersionLabel.zip"
if (Test-Path $zipName) { Remove-Item $zipName -Force }

Write-Output "Creating ZIP: $zipName"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($tmpDir, $zipName)

# Upload to S3
Write-Output "Uploading $zipName to s3://$S3Bucket/"
aws s3 cp $zipName s3://$S3Bucket/$($VersionLabel + ".zip") --region $Region

# Create application version
Write-Output "Creating application version $VersionLabel"
aws elasticbeanstalk create-application-version --application-name $AppName --version-label $VersionLabel --source-bundle S3Bucket=$S3Bucket,S3Key=$($VersionLabel + ".zip") --region $Region

# Update maintenance environment to new version (optional)
Write-Output "Updating environment $EnvName to version $VersionLabel"
aws elasticbeanstalk update-environment --environment-name $EnvName --version-label $VersionLabel --region $Region

Write-Output "Cleaning up temp dir"
Remove-Item -Recurse -Force $tmpDir

Write-Output "Done. Version label: $VersionLabel"
