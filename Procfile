web: gunicorn mvp_project.wsgi:application --bind 0.0.0.0:$PORT --workers 3
web: gunicorn mvp_project.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 2 --timeout 120 --log-level info --error-logfile logs/gunicorn-error.log --access-logfile logs/gunicorn-access.log
