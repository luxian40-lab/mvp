# Dockerfile para Django + Gunicorn + Jazzmin usando Amazon Linux 2023
FROM public.ecr.aws/amazonlinux/amazonlinux:2023

# Instala Python 3.10 y dependencias del sistema
RUN dnf -y update && \
    dnf -y install python3.10 python3.10-devel gcc postgresql-devel \
    libffi-devel openssl-devel libxml2-devel libxslt-devel libjpeg-turbo-devel zlib-devel \
    libpng-devel pkgconf-pkg-config && \
    python3.10 -m ensurepip && \
    python3.10 -m pip install --upgrade pip wheel && \
    dnf clean all

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos del proyecto
COPY . /app

RUN python3.10 -m venv /app/venv && \
    export PATH="/app/venv/bin:$PATH" && \
    /app/venv/bin/pip install --upgrade pip wheel && \
    /app/venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/app/venv/bin:$PATH"

# Expone el puerto 8000
EXPOSE 8000

# Comando de inicio
CMD sh -c "echo '===== ENVIRONMENT VARIABLES ====='; env; echo '===== END ENV ====='; echo '+ python3.10 manage.py migrate --noinput' && python3.10 manage.py migrate --noinput || { echo '==== MIGRATE FAILED ===='; sleep 600; exit 1; } && echo '+ python3.10 manage.py collectstatic --noinput' && python3.10 manage.py collectstatic --noinput || { echo '==== COLLECTSTATIC FAILED ===='; sleep 600; exit 1; } && echo '+ Crear superusuario admin' && echo \"from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')\" | python3.10 manage.py shell || { echo '==== CREAR SUPERUSUARIO FAILED ===='; sleep 600; exit 1; } && echo '+ gunicorn mvp_project.wsgi:application --bind 0.0.0.0:8000 --workers=2 --log-level debug' && gunicorn mvp_project.wsgi:application --bind 0.0.0.0:8000 --workers=2 --log-level debug || { echo '==== GUNICORN FAILED ===='; sleep 600; exit 1; }"
# Dockerfile para Django + Gunicorn + Jazzmin
FROM python:3.10

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos del proyecto

COPY . /app

# Instala dependencias del sistema necesarias para compilar paquetes
RUN apt-get update \
     && apt-get install -y --no-install-recommends \
         zlib1g-dev \
         zlib1g \
         libz-dev \
         build-essential \
         gcc \
         libpq-dev \
         libffi-dev \
         libssl-dev \
         libxml2-dev \
         libxslt1-dev \
         libjpeg-dev \
         libjpeg-turbo8-dev \
         libpng-dev \
         pkg-config \
     && rm -rf /var/lib/apt/lists/*


# Instala dependencias Python directamente desde requirements.txt
RUN pip install --upgrade pip --no-cache-dir \
    && pip install --no-cache-dir -r requirements.txt

# Expone el puerto 8000
EXPOSE 8000

CMD sh -c "echo '===== ENVIRONMENT VARIABLES ====='; env; echo '===== END ENV ====='; echo '+ python manage.py migrate --noinput' && python manage.py migrate --noinput || { echo '==== MIGRATE FAILED ===='; sleep 600; exit 1; } && echo '+ python manage.py collectstatic --noinput' && python manage.py collectstatic --noinput || { echo '==== COLLECTSTATIC FAILED ===='; sleep 600; exit 1; } && echo '+ Crear superusuario admin' && echo \"from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')\" | python manage.py shell || { echo '==== CREAR SUPERUSUARIO FAILED ===='; sleep 600; exit 1; } && echo '+ gunicorn mvp_project.wsgi:application --bind 0.0.0.0:8000 --workers=2 --log-level debug' && gunicorn mvp_project.wsgi:application --bind 0.0.0.0:8000 --workers=2 --log-level debug || { echo '==== GUNICORN FAILED ===='; sleep 600; exit 1; }"
