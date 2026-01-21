# PROD Procfile for Elastic Beanstalk
# Start Gunicorn web process
web: gunicorn mvp_project.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --log-level info

# Optional: Celery worker (uncomment if used)
# worker: celery -A mvp_project worker --loglevel=info --concurrency=2
# ========================================
# PROCFILE - PRODUCCION (AWS/Heroku)
# ========================================
# Le dice a la plataforma como ejecutar tu aplicacion

# Servidor web con Gunicorn (configuracion optimizada)
# Procfile para producción: indica cómo iniciar procesos
web: gunicorn mvp_project.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --log-level info

# Worker de Celery (descomentar si lo implementas)
# worker: celery -A mvp_project worker --loglevel=info --concurrency=2


