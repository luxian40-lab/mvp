# 1 worker web: Nat/Chroma en t3 agotan RAM con 2 workers (SIGKILL OOM).
web: gunicorn mvp_project.wsgi:application --worker-class gthread --workers 1 --threads 8 --timeout 180 --graceful-timeout 30 --max-requests 300 --max-requests-jitter 40 --bind 0.0.0.0:8000 --log-level info --worker-tmp-dir /dev/shm
worker: celery -A mvp_project worker -Q celery -n fast@%h --loglevel=info --concurrency=1 --max-tasks-per-child=150
worker_rag: celery -A mvp_project worker -Q rag_index -n rag@%h --loglevel=info --concurrency=1 --max-tasks-per-child=20
beat: celery -A mvp_project beat --loglevel=info
