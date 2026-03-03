web: gunicorn --bind :8000 --workers 3 --threads 2 --timeout 120 mvp_project.wsgi:application
worker: celery -A mvp_project worker --loglevel=info --concurrency=2
beat: celery -A mvp_project beat --loglevel=info
