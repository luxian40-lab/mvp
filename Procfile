web: gunicorn mvp_project.wsgi:application --worker-class gthread --workers 5 --threads 8 --timeout 1200 --bind 0.0.0.0:8000 --log-level info
worker: celery -A mvp_project worker --loglevel=info --concurrency=6
beat: celery -A mvp_project beat --loglevel=info
