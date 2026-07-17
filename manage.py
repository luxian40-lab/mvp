#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _load_local_env():
    """Carga .env / .env.local en la raíz del repo (no versionados)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parent
    load_dotenv(root / '.env')
    load_dotenv(root / '.env.local', override=False)


def _on_elastic_beanstalk() -> bool:
    return bool(
        os.environ.get('ELASTIC_BEANSTALK')
        or os.environ.get('AWS_EXECUTION_ENV')
        or os.environ.get('AWS_EB_ENVIRONMENT_NAME')
    )


def _force_production_settings() -> bool:
    return os.environ.get('EKI_USE_PRODUCTION_SETTINGS', '').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )


_load_local_env()


def main():
    """Run administrative tasks."""
    # EB / AWS: production. Laptop: settings base (sin S3 forzado ni sondeo RDS).
    # Override local→prod: EKI_USE_PRODUCTION_SETTINGS=1
    if _on_elastic_beanstalk() or _force_production_settings():
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production')
    else:
        # Si .env dejó production por costumbre, corregir en laptop.
        if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('settings_production'):
            os.environ['DJANGO_SETTINGS_MODULE'] = 'mvp_project.settings'
        else:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
