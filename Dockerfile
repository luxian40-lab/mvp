# Dockerfile para Django + Gunicorn + Jazzmin
FROM python:3.14-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos del proyecto
COPY . /app



# Instala dependencias
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Expone el puerto 8000
EXPOSE 8000

# Comando para ejecutar migraciones, collectstatic y arrancar Gunicorn con 2 workers
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn mvp_project.wsgi:application --bind 0.0.0.0:8000 --workers=2"]
