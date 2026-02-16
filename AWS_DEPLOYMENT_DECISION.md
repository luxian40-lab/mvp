# COMPARACION: AWS Elastic Beanstalk vs App Runner

## Tu Situacion Actual

Ya tienes configuracion de Elastic Beanstalk:
- .ebextensions/ con configs
- .platform/hooks/ con scripts
- Dockerrun.aws.json configurado
- ECR image ya existe

## Mi Recomendacion: ELASTIC BEANSTALK

### Por que Elastic Beanstalk es mejor para tu caso:

#### 1. YA LO TIENES CONFIGURADO
- Tienes .ebextensions/ funcionando
- Scripts de post-deploy listos
- ECR image configurado
- Solo necesitas actualizar y limpiar

#### 2. CONTROL TOTAL
- PostgreSQL RDS directamente
- Redis ElastiCache si necesitas
- Load balancer configurado
- Auto-scaling cuando crezcas
- SSH a las instancias si necesitas debug

#### 3. VARIABLES DE ENTORNO
- Se manejan via AWS Console o CLI
- Se pueden configurar por ambiente (staging, prod)
- Se cargan automaticamente en el container
- NO necesitas archivo .env en el repo

#### 4. COSTOS
- $0 por Elastic Beanstalk (solo pagas EC2)
- t3.small ~$15/mes
- RDS db.t3.micro ~$15/mes
- Total: ~$30-40/mes

#### 5. FEATURES
- Health monitoring incluido
- Logs centralizados
- Rollback automatico si deploy falla
- Multiple ambientes (dev, staging, prod)

## Por que NO App Runner (para tu caso):

#### 1. MENOS CONTROL
- No puedes SSH a containers
- Dificil debug de problemas
- Limitado para customizacion

#### 2. BASE DE DATOS
- Necesitas RDS separado igual
- Mas configuracion de networking
- VPC connector para conectar a RDS

#### 3. MIGRACION
- Tienes que rehacer toda la config
- Perder todo el trabajo de .ebextensions/
- Mas riesgo, mas tiempo

#### 4. COSTOS SIMILARES
- App Runner: ~$25-30/mes
- Elastic Beanstalk: ~$30-40/mes
- Diferencia minima

## Decision Final: ELASTIC BEANSTALK

### Ventajas para ti:
1. Ya tienes el 70% configurado
2. Solo necesitas limpiar y actualizar
3. Mas control y flexibilidad
4. Mejor para cuando crezcas
5. Mas facil debug y mantenimiento

### Plan de Accion:
1. Limpiar configs existentes de Elastic Beanstalk
2. Verificar archivos sin BOM
3. Actualizar Dockerrun.aws.json
4. Configurar variables de entorno en AWS
5. Deploy y probar

## Variables de Entorno en Elastic Beanstalk

### Como se manejan:

#### Via AWS Console:
```
1. Ir a Environment > Configuration
2. Software > Edit
3. Environment properties
4. Agregar cada variable
```

#### Via CLI:
```bash
eb setenv SECRET_KEY=tu_secret_key \
         DATABASE_URL=tu_database_url \
         TWILIO_ACCOUNT_SID=tu_sid \
         OPENAI_API_KEY=tu_key
```

#### Via .ebextensions/env.config (RECOMENDADO):
```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    DJANGO_SETTINGS_MODULE: mvp_project.settings_production
    DEBUG: False
    # Valores sensibles van en AWS Console/CLI
```

### Variables que NUNCA van en .ebextensions/:
- SECRET_KEY
- DATABASE_URL (con password)
- TWILIO_AUTH_TOKEN
- OPENAI_API_KEY
- AWS credentials

### Estas van en AWS Console

## Arquitectura Recomendada

```
Internet
   |
   v
Application Load Balancer (HTTP/HTTPS)
   |
   v
Elastic Beanstalk Environment
   |
   +-- EC2 Instance(s) con Docker
   |    +-- Django Container (Gunicorn)
   |
   +-- RDS PostgreSQL (privada)
   +-- ElastiCache Redis (opcional)
   +-- S3 para media files
```

## Proximos Pasos

1. Limpiar configs de BOM
2. Actualizar .ebextensions/
3. Crear script de deploy EB
4. Configurar variables en AWS
5. Deploy!

## Comandos Utiles

```bash
# Inicializar EB (si no esta)
eb init

# Crear environment
eb create produccion --database

# Deploy
eb deploy

# Ver logs
eb logs

# SSH a instancia
eb ssh

# Configurar env vars
eb setenv VAR=value

# Ver status
eb status

# Abrir app en browser
eb open
```

## Resumen

**USA ELASTIC BEANSTALK** porque:
- Ya lo tienes 70% configurado
- Mas control y flexibilidad
- Mejor para escalar
- Facil manejo de env vars
- Mejor debugging

**NO uses App Runner** porque:
- Tendrias que empezar de cero
- Menos control
- Mismos costos
- Mas complicado con RDS
