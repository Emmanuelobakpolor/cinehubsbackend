web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --timeout 600 --workers 2 --worker-class gthread --threads 4
worker: celery -A config.celery worker --loglevel=info
beat: celery -A config.celery beat --loglevel=info
