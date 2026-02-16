# Espera a que el entorno EB esté Ready, aplica OptionSettings y despliega la versión corregida
$envId = 'e-53phuffetn'
$region = 'us-east-2'
$optionFile = 'eb_option_settings_produccion.json'
$rollbackVersion = 'deploy-20260129012639'  # versión estable para rollback
$correctedVersion = 'deploy-20260129014933' # versión corregida con requirements fix

Write-Output "Starting watcher: wait for environment $envId to be Ready..."
while ($true) {
    $status = aws elasticbeanstalk describe-environments --environment-ids $envId --region $region --query "Environments[0].Status" --output text 2>$null
    Write-Output "$(Get-Date -Format o) Status: $status"
    if ($status -eq 'Ready') { break }
    if ($status -eq 'Terminated') { Write-Output 'Environment terminated, abort.'; exit 1 }
    Start-Sleep -Seconds 15
}

Write-Output "Environment Ready. Applying OptionSettings from $optionFile..."
aws elasticbeanstalk update-environment --environment-id $envId --region $region --option-settings file://$optionFile
if ($LASTEXITCODE -ne 0) { Write-Output 'Failed to apply OptionSettings. Will continue and attempt deploy.' }

Write-Output "Rolling back to stable version $rollbackVersion to ensure availability..."
aws elasticbeanstalk update-environment --environment-id $envId --version-label $rollbackVersion --region $region

# Esperar a Ready otra vez
while ($true) {
    $status2 = aws elasticbeanstalk describe-environments --environment-ids $envId --region $region --query "Environments[0].Status" --output text 2>$null
    Write-Output "$(Get-Date -Format o) Post-rollback Status: $status2"
    if ($status2 -eq 'Ready') { break }
    Start-Sleep -Seconds 15
}

Write-Output "Deploying corrected version $correctedVersion..."
aws elasticbeanstalk update-environment --environment-id $envId --version-label $correctedVersion --region $region
Write-Output 'Done.'
