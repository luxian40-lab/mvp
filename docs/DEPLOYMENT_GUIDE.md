# Deployment Best Practices - EKI MVP

## Overview

This document outlines professional deployment practices to ensure reliable and error-free production deployments.

## Pre-Deployment Checklist

### 1. Code Quality

```bash
# Run linting
flake8 core/ mvp_project/

# Run type checking (if using)
mypy core/

# Run security checks
bandit -r core/ mvp_project/
```

### 2. Database

```bash
# Check for pending migrations
python manage.py makemigrations --check --dry-run

# Apply migrations (test environment first)
python manage.py migrate --plan

# Backup database before applying
python manage.py dumpdata > backup_$(date +%Y%m%d_%H%M%S).json
```

### 3. Dependencies

```bash
# Verify all dependencies install cleanly
pip install -r requirements.txt --dry-run

# Check for security vulnerabilities
pip-audit

# Update outdated packages (test environment first)
pip list --outdated
```

### 4. Environment Configuration

Required environment variables:

```bash
# Core Django
SECRET_KEY=<50+ character random string>
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# AWS S3 (for media files)
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_STORAGE_BUCKET_NAME=<bucket-name>
AWS_S3_REGION_NAME=us-east-1

# Email
EMAIL_HOST_USER=<gmail-or-smtp-user>
EMAIL_HOST_PASSWORD=<app-password>

# Twilio
TWILIO_ACCOUNT_SID=<account-sid>
TWILIO_AUTH_TOKEN=<auth-token>
TWILIO_WHATSAPP_NUMBER=<whatsapp-number>

# OpenAI
OPENAI_API_KEY=<api-key>
```

### 5. Static Files

```bash
# Collect all static files
python manage.py collectstatic --noinput

# Verify static files
ls -lh staticfiles/

# Test static file serving
python manage.py runserver --insecure  # Only for testing!
```

## Deployment Process

### Step 1: Version Control

```bash
# Ensure clean working directory
git status

# Create release branch
git checkout -b release/v1.0.0

# Tag the release
git tag -a v1.0.0 -m "Release version 1.0.0"

# Push to repository
git push origin release/v1.0.0 --tags
```

### Step 2: Testing

```bash
# Run all tests
python manage.py test

# Run specific test modules
python manage.py test core.tests

# Check for issues
python manage.py check --deploy

# Run production readiness check
python check_production_readiness.py
```

### Step 3: Build & Deploy

#### Option A: Elastic Beanstalk

```bash
# Initialize EB (first time only)
eb init

# Create environment (first time only)
eb create production

# Deploy updates
eb deploy production

# Check environment health
eb health production

# View logs
eb logs production
```

#### Option B: Docker Deployment

```bash
# Build image
docker build -t eki-mvp:latest .

# Test locally
docker run -p 8000:8000 eki-mvp:latest

# Push to registry
docker tag eki-mvp:latest registry.example.com/eki-mvp:latest
docker push registry.example.com/eki-mvp:latest

# Deploy to production
docker-compose -f docker-compose.prod.yml up -d
```

#### Option C: Traditional Server

```bash
# SSH to server
ssh user@production-server

# Pull latest code
cd /var/www/eki-mvp
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart gunicorn
sudo systemctl restart nginx
```

### Step 4: Verification

```bash
# Check application is running
curl -I https://your-domain.com

# Test API endpoints
curl https://your-domain.com/api/health/

# Monitor logs
tail -f /var/log/eki-mvp/production.log

# Check database connections
python manage.py dbshell --command "SELECT 1;"
```

## Post-Deployment

### 1. Monitoring

Set up monitoring for:
- Application health
- Error rates
- Response times
- Database performance
- Disk space
- Memory usage

### 2. Logging

Configure centralized logging:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/production.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
```

### 3. Backup Strategy

Automated backups:
```bash
# Database backup (daily)
0 2 * * * /path/to/backup_database.sh

# Media files backup (weekly)
0 3 * * 0 /path/to/backup_media.sh

# Full system backup (monthly)
0 4 1 * * /path/to/full_backup.sh
```

### 4. Rollback Plan

If deployment fails:

```bash
# Elastic Beanstalk
eb deploy production --version previous-version

# Docker
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build <previous-image>

# Git-based deployment
git revert HEAD
git push origin main
# Then re-deploy
```

## Common Issues & Solutions

### Issue 1: Static Files Not Loading

**Symptoms:** 404 errors for CSS/JS files

**Solution:**
```bash
python manage.py collectstatic --noinput --clear
sudo systemctl restart nginx
```

### Issue 2: Database Migration Errors

**Symptoms:** Migration conflicts or failures

**Solution:**
```bash
# Check migration status
python manage.py showmigrations

# Fake problematic migration
python manage.py migrate --fake core 0001

# Re-run migrations
python manage.py migrate
```

### Issue 3: Memory Issues

**Symptoms:** Application crashes, high memory usage

**Solution:**
```bash
# Adjust gunicorn workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
```

### Issue 4: SSL/HTTPS Issues

**Symptoms:** Certificate errors, redirect loops

**Solution:**
```python
# In settings.py
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
```

## Security Hardening

### 1. Regular Updates

```bash
# Update dependencies monthly
pip list --outdated
pip install --upgrade <package-name>

# Update system packages
apt update && apt upgrade -y
```

### 2. Access Control

```bash
# Limit SSH access
sudo ufw allow from <your-ip> to any port 22

# Use SSH keys only
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no

# Restart SSH
sudo systemctl restart sshd
```

### 3. Database Security

```sql
-- Create read-only user for analytics
CREATE USER analytics_readonly WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE eki_prod TO analytics_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_readonly;
```

### 4. Secrets Management

Use a secrets manager:
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault

Never commit secrets to version control.

## Performance Optimization

### 1. Database Optimization

```python
# Use select_related and prefetch_related
estudiantes = Estudiante.objects.select_related('cliente').prefetch_related('cursos')

# Add database indexes
class Meta:
    indexes = [
        models.Index(fields=['telefono', '-fecha_registro']),
    ]

# Use database connection pooling
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 600,
    }
}
```

### 2. Caching

```python
# Cache expensive queries
from django.core.cache import cache

def get_active_courses():
    courses = cache.get('active_courses')
    if courses is None:
        courses = list(Curso.objects.filter(activo=True))
        cache.set('active_courses', courses, 3600)  # 1 hour
    return courses
```

### 3. Asynchronous Tasks

```python
# Use Celery for background tasks
from celery import shared_task

@shared_task
def send_campaign_messages(campaign_id):
    campaign = Campana.objects.get(id=campaign_id)
    # Send messages...
```

## Documentation

Maintain up-to-date documentation:

1. **README.md** - Project overview and setup
2. **CHANGELOG.md** - Version history
3. **API_DOCS.md** - API endpoints and usage
4. **DEPLOYMENT.md** - This file
5. **TROUBLESHOOTING.md** - Common issues

## Support & Maintenance

### Regular Tasks

Daily:
- Check error logs
- Monitor system health
- Review security alerts

Weekly:
- Review performance metrics
- Check for dependency updates
- Test backup restoration

Monthly:
- Security audit
- Performance optimization review
- Documentation updates

## Contact

For deployment issues, contact:
- DevOps Team: devops@example.com
- Emergency: +1-xxx-xxx-xxxx

---

**Last Updated:** February 2, 2026  
**Version:** 1.0.0
