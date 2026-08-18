#!/bin/bash
# Carga env de prod en instancia EB (eb ssh / smoke). Igual que Gunicorn: DB + Twilio + S3.
# Uso: source scripts/eb_env_prod.sh   (dentro de la instancia, tras cd /var/app/current)
export ELASTIC_BEANSTALK=true
export USE_S3=True
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT \
  TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_WHATSAPP_NUMBER TWILIO_PHONE_NUMBER TWILIO_WHATSAPP_FROM \
  AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME; do
  export "$key=$($GC environment -k "$key" 2>/dev/null)"
done
