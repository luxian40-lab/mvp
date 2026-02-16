# 🔐 INSTRUCCIONES: Configurar Credenciales AWS S3 en Elastic Beanstalk

## Problema Actual
El servidor NO puede subir archivos a S3 porque faltan las credenciales AWS.

## Solución: Agregar Variables de Entorno

### Opción A: Consola Web AWS (MÁS FÁCIL)

1. Ve a: https://console.aws.amazon.com/elasticbeanstalk
2. Click en "eki-prod-final"
3. Click "Configuration" (lado izquierdo)
4. Scroll hasta "Software" → Click "Edit"
5. En "Environment properties" agregar:

```
AWS_ACCESS_KEY_ID     = AKIA... (tu access key)
AWS_SECRET_ACCESS_KEY = wJalr... (tu secret key)
AWS_S3_REGION_NAME    = us-east-2
```

6. Click "Apply"
7. Esperar 2-3 minutos que reinicie

### Opción B: AWS CLI (RÁPIDO)

```powershell
# Reemplaza AKIA... y wJalr... con tus credenciales reales
aws elasticbeanstalk update-environment `
  --environment-name eki-prod-final `
  --option-settings `
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=AWS_ACCESS_KEY_ID,Value=AKIA... `
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=AWS_SECRET_ACCESS_KEY,Value=wJalr... `
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=AWS_S3_REGION_NAME,Value=us-east-2 `
  --region us-east-2
```

## Verificar que Funcionó

Después de configurar:

1. Espera 2-3 minutos
2. Ve al Admin Django
3. Sube un video nuevamente en ArchivoModulo
4. Verifica en S3:
   ```bash
   aws s3 ls s3://eki-produccion/media/modulos/ --recursive --region us-east-2
   ```
5. Deberías ver: `2026-02-04 ... VIDEO_MODULO_0.mp4`

## ¿Dónde Obtener las Credenciales?

### Si NO tienes Access Keys:
```bash
aws iam create-access-key --user-name eki-S3-produccion
```

### Si YA tienes pero las olvidaste:
- NO puedes recuperar el SecretAccessKey
- Debes crear nuevas:
  ```bash
  # Eliminar viejas
  aws iam delete-access-key --user-name eki-S3-produccion --access-key-id AKIA_VIEJA
  
  # Crear nuevas
  aws iam create-access-key --user-name eki-S3-produccion
  ```

## Seguridad

⚠️ **NUNCA** compartas estas credenciales en Git o código.
✅ Solo configurarlas en variables de entorno de Elastic Beanstalk.
