# Dockerfile para Django + Gunicorn + Jazzmin
FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos del proyecto

COPY . /app

# Instala dependencias del sistema necesarias para compilar paquetes
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
       libpq-dev \
       libffi-dev \
       libssl-dev \
       libxml2-dev \
       libxslt1-dev \
       libjpeg-dev \
       zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*


# Instala dependencias Python directamente desde requirements.txt
RUN pip install --upgrade pip --no-cache-dir \
    && pip install --no-cache-dir -r requirements.txt

# Expone el puerto 8000
EXPOSE 8000

# Comando para ejecutar migraciones, collectstatic, crear superusuario y arrancar Gunicorn con 2 workers
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && echo \"from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')\" | python manage.py shell && gunicorn mvp_project.wsgi:application --bind 0.0.0.0:8000 --workers=2"]
