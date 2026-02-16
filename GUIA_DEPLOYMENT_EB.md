# GUIA COMPLETA DE DEPLOYMENT - AWS ELASTIC BEANSTALK

## Decision Final: ELASTIC BEANSTALK

Ya tienes el 70% configurado, solo necesitas limpiar y actualizar.

## Lo que se hizo:

### 1. Limpieza de BOM
- [x] Removidos BOM de `.platform/nginx/conf.d/proxy.conf`
- [x] Removido BOM de `mvp_project/wsgi.py`
- [x] Verificador automatico creado: `scripts/verification/verificar_bom.py`

### 2. Configuracion Elastic Beanstalk
- [x] `.ebextensions/01_django.config` - Settings Django
- [x] `.ebextensions/02_migrate.config` - Migraciones automaticas
- [x] `.ebextensions/03_instance.config` - Configuracion instancia
- [x] `.platform/hooks/postdeploy/01_migrate.sh` - Post-deploy hooks

### 3. Scripts de Deployment
- [x] `deploy_eb.sh` - Deploy automatizado completo
- [x] `configure_eb_env.sh` - Configura variables de entorno

## Arquitectura

```
Internet
   |
   v
Application Load Balancer (HTTPS)
   |
   v
EC2 Instance(s) - t3.small
   |
   +-- Docker Container
   |    +-- Gunicorn
   |    +-- Django App
   |
   +-- RDS PostgreSQL
   +-- S3 para media
```

## PASO A PASO PARA DEPLOY

### Paso 1: Preparar .env.production

```bash
# Ya tienes .env.production.template
# Completar con tus valores reales

# Variables REQUERIDAS:
SECRET_KEY=tu_secret_key_generada
DATABASE_URL=postgresql://user:pass@host:5432/dbname
TWILIO_ACCOUNT_SID=tu_sid
TWILIO_AUTH_TOKEN=tu_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
OPENAI_API_KEY=sk-tu-key
AWS_ACCESS_KEY_ID=tu_access_key
AWS_SECRET_ACCESS_KEY=tu_secret_key
AWS_STORAGE_BUCKET_NAME=tu-bucket
```

### Paso 2: Verificar Pre-requisitos

```bash
# Instalar EB CLI
pip install awsebcli

# Configurar AWS credentials
aws configure
# Ingresa:
#   AWS Access Key ID
#   AWS Secret Access Key
#   Default region: us-east-2
#   Default output format: json

# Verificar credenciales
aws sts get-caller-identity
```

### Paso 3: Inicializar Elastic Beanstalk

```bash
# Ir a directorio del proyecto
cd c:\Users\luxia\OneDrive\Escritorio\eki_mvp

# Inicializar EB (si no lo has hecho)
eb init

# Selecciona:
#   Region: us-east-2 (o la que prefieras)
#   Application name: eki-mvp
#   Platform: Docker
#   Version: Docker running on 64bit Amazon Linux 2
#   CodeCommit: No
#   SSH: Yes (opcional pero recomendado)
```

### Paso 4: Crear RDS (Base de Datos)

Opcion A - Via Console AWS:
1. Ir a RDS Console
2. Create database
3. PostgreSQL 15
4. Free tier (db.t3.micro) o Production (db.t3.small)
5. Nombre: eki-mvp-db
6. Usuario: postgres
7. Password: [tu password seguro]
8. Guardar endpoint y credenciales

Opcion B - Via EB CLI:
```bash
# Crear environment con RDS incluido
eb create produccion --database \
  --database.engine postgres \
  --database.version 15 \
  --database.instance db.t3.micro \
  --database.username postgres \
  --database.password [tu_password]
```

### Paso 5: Crear S3 Bucket

```bash
# Crear bucket para media files
aws s3 mb s3://eki-mvp-media --region us-east-2

# Configurar CORS
aws s3api put-bucket-cors --bucket eki-mvp-media --cors-configuration file://s3-cors.json

# s3-cors.json:
{
  "CORSRules": [{
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3000
  }]
}
```

### Paso 6: Configurar Variables de Entorno

```bash
# Actualizar DATABASE_URL en .env.production con el endpoint de RDS
# Ejemplo:
# DATABASE_URL=postgresql://postgres:password@eki-mvp-db.xxxx.us-east-2.rds.amazonaws.com:5432/ebdb

# Configurar variables en EB
bash configure_eb_env.sh

# O manualmente:
eb setenv \
  SECRET_KEY=tu_key \
  DATABASE_URL=postgresql://... \
  TWILIO_ACCOUNT_SID=ACxxx \
  TWILIO_AUTH_TOKEN=xxx \
  OPENAI_API_KEY=sk-xxx \
  AWS_STORAGE_BUCKET_NAME=eki-mvp-media \
  USE_S3=True
```

### Paso 7: Build y Push Docker Image

```bash
# Login a ECR
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-2 | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-2.amazonaws.com

# Crear repositorio ECR (primera vez)
aws ecr create-repository --repository-name eki-mvp --region us-east-2

# Build image
docker build -f Dockerfile.production -t eki-mvp:latest .

# Tag
docker tag eki-mvp:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-2.amazonaws.com/eki-mvp:latest

# Push
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-2.amazonaws.com/eki-mvp:latest
```

### Paso 8: Deploy!

```bash
# Opcion A - Usando script automatizado (RECOMENDADO)
bash deploy_eb.sh

# Opcion B - Manual
eb deploy

# Ver logs en tiempo real
eb logs -f
```

### Paso 9: Verificar Deployment

```bash
# Ver status
eb status

# Ver health
eb health

# Abrir aplicacion en browser
eb open

# SSH a instancia (para debug)
eb ssh
```

### Paso 10: Configurar Dominio (Opcional)

```bash
# Via Route 53
# 1. Crear hosted zone para tu dominio
# 2. Crear CNAME apuntando a EB environment URL
# 3. Configurar SSL/TLS con Certificate Manager

# Via EB CLI
eb config

# Agregar:
# aws:elasticbeanstalk:environment:
#   LoadBalancerType: application
# aws:elbv2:listener:443:
#   Protocol: HTTPS
#   SSLCertificateArns: arn:aws:acm:...
```

## Variables de Entorno - Detalle

### Como se Manejan:

1. **Desarrollo Local**: `.env` (gitignored)
2. **Produccion AWS**: Configuradas via `eb setenv` o Console
3. **NO van en .ebextensions/**: Por seguridad

### Variables REQUERIDAS para AWS:

```bash
# Django
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=.elasticbeanstalk.com,tu-dominio.com
DJANGO_SETTINGS_MODULE=mvp_project.settings_production

# Database
DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/ebdb

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# OpenAI
OPENAI_API_KEY=sk-xxxxx

# AWS S3
AWS_ACCESS_KEY_ID=AKIAxxxxx
AWS_SECRET_ACCESS_KEY=xxxxx
AWS_STORAGE_BUCKET_NAME=eki-mvp-media
AWS_S3_REGION_NAME=us-east-2
USE_S3=True

# Optional
COHERE_API_KEY=xxxxx
GEMINI_API_KEY=xxxxx
```

### Verificar Variables:

```bash
# Ver todas las variables configuradas
eb printenv

# Ver variable especifica
eb printenv SECRET_KEY
```

## Comandos Utiles

```bash
# Ver logs
eb logs
eb logs -f  # follow mode

# SSH a instancia
eb ssh

# Ver status
eb status
eb health

# Reiniciar application
eb restart

# Rollback a version anterior
eb deploy --version <version-label>

# Escalar
eb scale 2  # 2 instancias

# Cambiar instance type
eb config
# Editar: aws:autoscaling:launchconfiguration:InstanceType

# Terminar environment (CUIDADO)
eb terminate produccion

# Ver configuracion actual
eb config

# Ver eventos
eb events -f
```

## Monitoreo

### Logs:
```bash
# Ver logs en tiempo real
eb logs -f

# Descargar todos los logs
eb logs --all

# Logs especificos
eb logs --instance i-xxxxx
```

### CloudWatch:
- EB automaticamente envia metricas a CloudWatch
- CPU, Memory, Network, Request count
- Crear alarmas para notificaciones

### Health Checks:
- EB hace health checks a `/health/`
- Configurado en `.ebextensions/01_django.config`
- Si falla 5 veces consecutivas, reinicia instancia

## Troubleshooting

### Error: "Environment health has transitioned from Ok to Severe"

```bash
# Ver logs detallados
eb logs

# Causas comunes:
# 1. Error en migraciones
# 2. Variable de entorno faltante
# 3. Error en codigo Python
# 4. Health check fallando

# SSH y debug
eb ssh
cd /var/app/current
docker logs $(docker ps -q)
```

### Error: "Failed to pull Docker image"

```bash
# Verificar image en ECR
aws ecr describe-images --repository-name eki-mvp

# Verificar Dockerrun.aws.json tiene la image correcta
cat Dockerrun.aws.json

# Rebuild y push
bash deploy_eb.sh
```

### Error: "Database connection failed"

```bash
# Verificar DATABASE_URL
eb printenv DATABASE_URL

# Verificar security groups de RDS
# RDS debe permitir conexiones desde EB security group

# Test conexion desde instancia
eb ssh
ping <rds-endpoint>
```

### Error: "Static files not loading"

```bash
# Verificar collectstatic se ejecuto
eb ssh
cd /var/app/current
ls -la staticfiles/

# Re-ejecutar collectstatic
docker exec -it <container-id> python manage.py collectstatic --noinput
```

## Costos Estimados (us-east-2)

```
EC2 t3.medium (1 instancia):    ~$60/mes
RDS db.t3.micro:                ~$15/mes
Application Load Balancer:      ~$16/mes
Data transfer out:              ~$5-10/mes
S3 storage (10GB):              ~$0.23/mes
----------------------------------------------
TOTAL:                          ~$96-101/mes
```

### Reducir Costos:
- Usar Reserved Instances (40% descuento) → ~$36/mes EC2
- Usar Savings Plans
- Apagar staging environment cuando no se usa
- Usar CloudFront para reducir data transfer

**Nota:** Se usa t3.medium porque t3.small se traba con la carga de la aplicacion.

## Checklist Final

Antes de deploy:
- [ ] .env.production completado (sin XXX)
- [ ] AWS credentials configuradas
- [ ] EB CLI instalado
- [ ] RDS creado y accesible
- [ ] S3 bucket creado
- [ ] ECR repository creado
- [ ] Variables configuradas en EB
- [ ] BOM removidos
- [ ] Docker image builded

Despues de deploy:
- [ ] Health check pasa
- [ ] Aplicacion accesible via URL
- [ ] Admin funciona
- [ ] Base de datos conectada
- [ ] Static files cargan
- [ ] WhatsApp funciona (si esta configurado)
- [ ] Logs no muestran errores criticos

## Soporte

Si encuentras problemas:
1. Ver logs: `eb logs -f`
2. SSH y ver container logs: `eb ssh` + `docker logs`
3. Verificar health: `eb health`
4. Verificar events: `eb events -f`
5. Verificar variables: `eb printenv`

## Proximos Pasos

Despues del primer deploy:
1. Configurar dominio custom
2. Configurar SSL/TLS
3. Configurar auto-scaling
4. Setup CI/CD con GitHub Actions
5. Configurar backups automaticos de RDS
6. Setup monitoring con CloudWatch Alarms
7. Configurar staging environment
