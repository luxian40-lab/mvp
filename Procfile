web: gunicorn mvp_project.wsgi:application --worker-class gthread --workers 3 --threads 6 --timeout 600 --max-requests 500 --max-requests-jitter 80 --bind 0.0.0.0:8000 --log-level info
worker: celery -A mvp_project worker --loglevel=info --concurrency=3
beat: celery -A mvp_project beat --loglevel=info
