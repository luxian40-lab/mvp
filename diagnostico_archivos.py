import os
import django

# Configura el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production')
django.setup()

from core.models_extras import ArchivoModulo

print("Total:", ArchivoModulo.objects.count())
print("Con archivo:", ArchivoModulo.objects.exclude(archivo='').exclude(archivo=None).count())
print("Con url_externa:", ArchivoModulo.objects.exclude(url_externa='').exclude(url_externa=None).count())
print("Solo archivo:", ArchivoModulo.objects.exclude(archivo='').exclude(archivo=None).filter(url_externa__isnull=True).count())
print("Solo url_externa:", ArchivoModulo.objects.exclude(url_externa='').exclude(url_externa=None).filter(archivo__isnull=True).count())
