web: gunicorn mvp_project.wsgi:application --worker-class gthread --workers 2 --threads 6 --timeout 180 --graceful-timeout 30 --max-requests 400 --max-requests-jitter 50 --bind 0.0.0.0:8000 --log-level info --worker-tmp-dir /dev/shm
worker: celery -A mvp_project worker --loglevel=info --concurrency=1 --max-tasks-per-child=50
beat: celery -A mvp_project beat --loglevel=info
