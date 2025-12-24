import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import WhatsappLog

logs = WhatsappLog.objects.all().order_by('-fecha')[:5]
print(f'📊 Total logs: {WhatsappLog.objects.count()}')
print('🔵 Últimos 5:')
for l in logs:
    print(f'  {l.fecha.strftime("%H:%M:%S")} | {l.tipo:8s} | {l.mensaje[:40]}')
