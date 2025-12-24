import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import WhatsappLog

print("=" * 70)
print("📊 LOGS DE WHATSAPP")
print("=" * 70)

total = WhatsappLog.objects.count()
print(f"\nTotal de registros: {total}")

if total > 0:
    print("\nÚltimos 5 registros:")
    print("-" * 70)
    for log in WhatsappLog.objects.all().order_by('-id')[:5]:
        tipo_emoji = "📤" if log.tipo == "SENT" else "📥"
        print(f"{tipo_emoji} {log.tipo:10} | {log.telefono:20} | {log.mensaje[:40] if log.mensaje else '(vacío)'}")
else:
    print("\n❌ NO HAY REGISTROS EN LA BASE DE DATOS")
    print("\nEsto significa que el webhook NO está guardando los logs.")
    print("Posibles causas:")
    print("1. El código del webhook tiene un error")
    print("2. La migración no se aplicó correctamente")
    print("3. Django está mostrando una página de error en lugar de ejecutar el código")

print("=" * 70)
