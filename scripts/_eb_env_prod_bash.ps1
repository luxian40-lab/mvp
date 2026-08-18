# Fragmento bash estándar para eb ssh: mismas vars que Gunicorn en prod (DB, Twilio, S3).
# Uso en scripts .ps1:
#   . "$PSScriptRoot\_eb_env_prod_bash.ps1"
#   $bash = @"
#   $(Get-EbEnvProdBash)
#   cd /var/app/current && source /var/app/venv/*/bin/activate
#   ...
#   "@

function Get-EbEnvProdBash {
    return @'
export ELASTIC_BEANSTALK=true
export USE_S3=True
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_WHATSAPP_NUMBER TWILIO_PHONE_NUMBER TWILIO_WHATSAPP_FROM AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME; do
  export "$key="$($GC environment -k $key 2>/dev/null)""
done
'@
}
