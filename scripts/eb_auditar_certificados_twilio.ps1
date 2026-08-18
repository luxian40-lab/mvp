param([int]$Horas = 72)
. "$PSScriptRoot\_eb_env_prod_bash.ps1"
$pyArgs = @('auditar_certificados_twilio', "--horas=$Horas")
$bash = @"
$(Get-EbEnvProdBash)
cd /var/app/current && source /var/app/venv/*/bin/activate && python manage.py $($pyArgs -join ' ')
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
