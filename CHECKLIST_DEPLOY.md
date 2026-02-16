# CHECKLIST FINAL PARA DEPLOY - EKI MVP

## Pre-Requisitos

### Instalaciones
- [ ] Docker Desktop instalado y corriendo
- [ ] Git instalado
- [ ] Python 3.11+ instalado (para desarrollo local)
- [ ] Editor de texto/IDE configurado

### Cuentas y Servicios
- [ ] Cuenta Twilio con WhatsApp configurado
- [ ] Cuenta OpenAI con API key
- [ ] Cuenta AWS (si usas S3)
- [ ] Base de datos PostgreSQL (local o en cloud)

## Paso 1: Configuracion de Entorno

### Crear .env.production
- [ ] Copiar: `cp .env.production.template .env.production`
- [ ] Generar SECRET_KEY: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- [ ] Completar SECRET_KEY
- [ ] Completar DATABASE_URL (PostgreSQL)
- [ ] Completar TWILIO_ACCOUNT_SID
- [ ] Completar TWILIO_AUTH_TOKEN
- [ ] Completar TWILIO_WHATSAPP_FROM
- [ ] Completar OPENAI_API_KEY
- [ ] Completar AWS credentials (si usas S3)
- [ ] Completar EMAIL_HOST_USER
- [ ] Completar EMAIL_HOST_PASSWORD
- [ ] Verificar ALLOWED_HOSTS tiene tu dominio
- [ ] Verificar DEBUG=False

### Verificar .env.production
- [ ] No tiene valores XXX
- [ ] No tiene espacios al inicio/fin de valores
- [ ] No tiene comillas en valores (a menos que sean necesarias)
- [ ] Todas las variables requeridas estan presentes

## Paso 2: Verificacion de Codigo

### Archivos Limpios
- [ ] Ejecutar: `python scripts/verification/verificar_dependencias.py`
- [ ] No hay errores de dependencias
- [ ] No hay warnings criticos
- [ ] Sin emojis en codigo Python
- [ ] Sin print statements en produccion

### Pre-Deploy Check
- [ ] Ejecutar: `bash pre_deploy_check.sh` (Linux/Mac)
- [ ] Ejecutar: `.\pre_deploy_check.ps1` (Windows)
- [ ] Todos los checks pasan (0 errores)
- [ ] Warnings revisados y entendidos

## Paso 3: Prueba Local

### Docker Build Desarrollo
- [ ] Ejecutar: `docker-compose build`
- [ ] Build completo sin errores
- [ ] No hay conflictos de dependencias
- [ ] Imagen creada exitosamente

### Docker Run Desarrollo
- [ ] Ejecutar: `docker-compose up`
- [ ] PostgreSQL inicia correctamente
- [ ] Redis inicia correctamente
- [ ] Django inicia correctamente
- [ ] Ver logs: No hay errores criticos
- [ ] Abrir: http://localhost:8000
- [ ] Pagina carga correctamente
- [ ] Admin accesible: http://localhost:8000/admin

### Migraciones
- [ ] Ejecutar: `docker-compose exec web python manage.py migrate`
- [ ] Todas las migraciones se aplican sin errores
- [ ] No hay warnings de migraciones

### Static Files
- [ ] Ejecutar: `docker-compose exec web python manage.py collectstatic --noinput`
- [ ] Static files copiados exitosamente
- [ ] CSS/JS carga en admin

### Crear Superusuario
- [ ] Ejecutar: `docker-compose exec web python manage.py createsuperuser`
- [ ] Usuario creado exitosamente
- [ ] Login funciona en admin

### Pruebas Funcionales
- [ ] Login admin funciona
- [ ] Crear un estudiante
- [ ] Crear un curso
- [ ] Enviar mensaje WhatsApp (si esta configurado)
- [ ] Ver logs: `docker-compose logs -f web`
- [ ] No hay errores en runtime

### Parar Desarrollo
- [ ] Ejecutar: `docker-compose down`
- [ ] Todos los containers parados
- [ ] Volumenes preservados (si quieres mantener data)

## Paso 4: Build Produccion

### Docker Build Produccion
- [ ] Ejecutar: `docker-compose -f docker-compose.production.yml build`
- [ ] Build completo sin errores
- [ ] requirements.production.txt usado
- [ ] Imagen optimizada creada

### Docker Run Produccion
- [ ] Ejecutar: `docker-compose -f docker-compose.production.yml up -d`
- [ ] Todos los servicios inician
- [ ] Nginx inicia correctamente
- [ ] Django inicia con Gunicorn
- [ ] Verificar: `docker-compose ps`
- [ ] Todos los servicios "healthy"

### Health Checks
- [ ] Abrir: http://localhost/health/
- [ ] Respuesta 200 OK
- [ ] Django responde correctamente
- [ ] Nginx proxy funciona

### Verificacion de Servicios
- [ ] PostgreSQL corriendo: `docker-compose exec db psql -U usuario -d eki_mvp -c "\dt"`
- [ ] Redis corriendo: `docker-compose exec redis redis-cli ping`
- [ ] Django corriendo: `docker-compose logs web`
- [ ] Nginx corriendo: `docker-compose logs nginx`

### Static Files en Produccion
- [ ] Abrir: http://localhost/static/admin/css/base.css
- [ ] CSS carga correctamente via nginx
- [ ] Cache headers presentes

### Logs en Produccion
- [ ] Ver: `docker-compose logs -f`
- [ ] No hay errores criticos
- [ ] Gunicorn workers iniciados
- [ ] Conexiones a DB exitosas

## Paso 5: Git Repository

### Inicializar Git
- [ ] Ejecutar: `bash git_init.sh` o `.\git_init.ps1`
- [ ] Repository inicializado
- [ ] .gitignore verificado
- [ ] No hay archivos sensibles (.env) staged

### Verificar Archivos Staged
- [ ] Ejecutar: `git status`
- [ ] Archivos correctos incluidos
- [ ] .env NO esta incluido
- [ ] .env.production NO esta incluido
- [ ] db.sqlite3 NO esta incluido
- [ ] __pycache__ NO esta incluido

### Commit Inicial
- [ ] Ejecutar commit (via script o manual)
- [ ] Commit creado exitosamente
- [ ] Ver: `git log`

### Remote Repository
- [ ] Crear repo en GitHub/GitLab/BitBucket
- [ ] Ejecutar: `git remote add origin <url>`
- [ ] Ejecutar: `git push -u origin main`
- [ ] Push exitoso
- [ ] Verificar en web que archivos estan correctos

## Paso 6: Deploy a Servidor

### Preparar Servidor
- [ ] Servidor Linux con Docker instalado
- [ ] SSH access configurado
- [ ] Puertos 80 y 443 abiertos
- [ ] Dominio apuntando al servidor
- [ ] SSL/TLS certificado (Let's Encrypt)

### Transferir Archivos
- [ ] Clone repo: `git clone <url>`
- [ ] Copiar .env.production al servidor
- [ ] Verificar permisos: `chmod 600 .env.production`
- [ ] Verificar Docker esta corriendo

### Build en Servidor
- [ ] SSH al servidor
- [ ] cd al directorio del proyecto
- [ ] Ejecutar: `bash deploy.sh prod`
- [ ] Build completo
- [ ] Servicios iniciados

### SSL/HTTPS (si no esta configurado)
- [ ] Instalar certbot
- [ ] Obtener certificado: `certbot --nginx -d tu-dominio.com`
- [ ] Actualizar nginx.conf con SSL
- [ ] Reiniciar nginx

### Verificacion Final
- [ ] Abrir: https://tu-dominio.com
- [ ] Sitio carga correctamente
- [ ] HTTPS funciona
- [ ] Admin accesible
- [ ] WhatsApp funciona
- [ ] Base de datos funciona

## Paso 7: Post-Deploy

### Monitoring
- [ ] Configurar logs persistentes
- [ ] Configurar alertas (Sentry, CloudWatch)
- [ ] Configurar backups automaticos
- [ ] Configurar monitoring de recursos

### Seguridad
- [ ] Firewall configurado
- [ ] Solo puertos necesarios abiertos
- [ ] SSH con key-based auth
- [ ] Fail2ban configurado
- [ ] Updates automaticos configurados

### Backups
- [ ] Backup de base de datos configurado
- [ ] Backup de media files configurado
- [ ] Backup de .env.production (en lugar seguro)
- [ ] Procedimiento de restore probado

### Documentacion
- [ ] README actualizado con URL de produccion
- [ ] Credenciales guardadas en lugar seguro
- [ ] Procedimientos de deploy documentados
- [ ] Contactos de emergencia documentados

## Comandos Rapidos de Referencia

### Ver logs
```bash
docker-compose logs -f web
docker-compose logs --tail=100 web
```

### Reiniciar servicio
```bash
docker-compose restart web
docker-compose restart nginx
```

### Ejecutar comando en container
```bash
docker-compose exec web python manage.py shell
docker-compose exec web python manage.py dbshell
```

### Backup database
```bash
docker-compose exec db pg_dump -U usuario eki_mvp > backup.sql
```

### Restore database
```bash
cat backup.sql | docker-compose exec -T db psql -U usuario eki_mvp
```

### Ver recursos
```bash
docker stats
docker-compose ps
```

### Parar todo
```bash
docker-compose down
docker-compose down -v  # incluye volumenes
```

## Troubleshooting

### Container no inicia
- [ ] Ver logs: `docker-compose logs <servicio>`
- [ ] Verificar .env.production
- [ ] Verificar puertos no estan ocupados
- [ ] Verificar recursos disponibles

### Error de dependencias
- [ ] Verificar requirements.production.txt
- [ ] Rebuild: `docker-compose build --no-cache`
- [ ] Verificar no hay paquetes de Windows

### Error de base de datos
- [ ] Verificar DATABASE_URL
- [ ] Verificar PostgreSQL esta corriendo
- [ ] Verificar credenciales
- [ ] Verificar red Docker

### Error 502 Bad Gateway
- [ ] Verificar Django esta corriendo
- [ ] Verificar Gunicorn esta corriendo
- [ ] Verificar nginx.conf correcto
- [ ] Ver logs de web y nginx

## Firma y Fecha

- [ ] Deploy completado exitosamente
- [ ] Fecha: _______________
- [ ] Deployado por: _______________
- [ ] Ambiente: Produccion
- [ ] URL: _______________

## Notas Adicionales

```
Espacio para notas sobre el deploy:
- Issues encontrados
- Soluciones aplicadas
- Cambios de ultimo minuto
- Pendientes para siguiente iteracion
```
