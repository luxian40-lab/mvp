param([int]$Horas = 72)
$pyArgs = @('auditar_certificados_twilio', "--horas=$Horas")
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate && python manage.py $($pyArgs -join ' ')
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
