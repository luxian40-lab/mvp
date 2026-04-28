web: gunicorn mvp_project.wsgi:application --workers 3 --threads 2 --timeout 60 --bind 0.0.0.0:8000 --log-level info
worker: celery -A mvp_project worker --loglevel=info --concurrency=2
beat: celery -A mvp_project beat --loglevel=info
