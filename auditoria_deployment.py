#!/usr/bin/env python
"""
🚀 AUDITORÍA PRE-DEPLOYMENT: Qué falta para mañana
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from django.conf import settings
from django.core.management import call_command
from io import StringIO

print("=" * 80)
print("🚀 AUDITORÍA PRE-DEPLOYMENT - CHECKLIST FINAL")
print("=" * 80)

# 1. ESTADO DE MIGRACIONES
print("\n📋 1. MIGRACIONES DE BD:")
try:
    out = StringIO()
    call_command('showmigrations', 'core', stdout=out)
    output = out.getvalue()
    if '[X]' in output:
        migraciones_aplicadas = output.count('[X]')
        print(f"   ✅ {migraciones_aplicadas} migraciones aplicadas")
    else:
        print("   ❌ Hay migraciones pendientes")
except Exception as e:
    print(f"   ⚠️  Error: {e}")

# 2. CONFIGURACIÓN CRÍTICA
print("\n⚙️  2. CONFIGURACIÓN CRÍTICA:")
checks = [
    ("DEBUG", settings.DEBUG, False, "Debe ser False en producción"),
    ("SECRET_KEY", 'django-insecure' not in settings.SECRET_KEY, True, "Debe tener SECRET_KEY segura"),
    ("ALLOWED_HOSTS", len(settings.ALLOWED_HOSTS) > 0, True, "Debe tener hosts configurados"),
    ("DATABASE", settings.DATABASES.get('default', {}).get('ENGINE'), True, "Debe tener BD configurada"),
]

for name, value, expected, msg in checks:
    if isinstance(expected, bool):
        status = "✅" if value == expected else "❌"
    else:
        status = "✅" if bool(value) else "❌"
    print(f"   {status} {name}: {msg}")

# 3. VARIABLES DE ENTORNO CRÍTICAS
print("\n🔐 3. VARIABLES DE ENTORNO REQUERIDAS:")
env_vars = [
    'TWILIO_ACCOUNT_SID',
    'TWILIO_AUTH_TOKEN',
    'TWILIO_WHATSAPP_FROM',
    'OPENAI_API_KEY',
    'SECRET_KEY',
]

env_configured = 0
for var in env_vars:
    has_var = bool(os.environ.get(var))
    status = "✅" if has_var else "❌"
    value_preview = os.environ.get(var, "")[:10] if has_var else "NO CONFIGURADA"
    print(f"   {status} {var}: {value_preview}...")
    if has_var:
        env_configured += 1

print(f"\n   📊 {env_configured}/{len(env_vars)} variables configuradas")

# 4. EMAIL CONFIGURATION
print("\n📧 4. CONFIGURACIÓN DE EMAIL:")
email_checks = [
    ('EMAIL_HOST', settings.EMAIL_HOST),
    ('EMAIL_PORT', settings.EMAIL_PORT),
    ('EMAIL_HOST_USER', settings.EMAIL_HOST_USER),
]

email_ok = all(getattr(settings, key, None) for key, _ in email_checks)
for key, _ in email_checks:
    value = getattr(settings, key, "NO CONFIGURADO")
    status = "✅" if value and value != "NO CONFIGURADO" else "⚠️ "
    print(f"   {status} {key}: {value}")

if not email_ok:
    print("   ⚠️  EMAIL NO COMPLETAMENTE CONFIGURADO - Las notificaciones de soporte no funcionarán")

# 5. ALMACENAMIENTO DE ARCHIVOS
print("\n💾 5. ALMACENAMIENTO DE ARCHIVOS:")
media_root = settings.MEDIA_ROOT
media_exists = os.path.exists(media_root)
print(f"   {'✅' if media_exists else '❌'} MEDIA_ROOT: {media_root}")
print(f"   {'✅' if media_exists else '❌'} Carpeta existe: {media_exists}")

if media_exists:
    cert_path = os.path.join(media_root, 'certificados')
    cert_count = 0
    if os.path.exists(cert_path):
        for root, dirs, files in os.walk(cert_path):
            cert_count += len([f for f in files if f.endswith('.pdf')])
    print(f"   📄 PDFs de certificados: {cert_count}")

# 6. APLICACIONES Y MODELOS
print("\n🗂️  6. ESTADO DE APLICACIONES:")
from django.apps import apps

modelos_criticos = [
    'Estudiante',
    'Curso', 
    'Modulo',
    'Certificado',
    'SolicitudSoporte',
    'WhatsappLog',
    'EnvioLog',
]

todos_existen = True
for modelo in modelos_criticos:
    try:
        apps.get_model('core', modelo)
        print(f"   ✅ {modelo}")
    except:
        print(f"   ❌ {modelo} - FALTA")
        todos_existen = False

# 7. URLS CONFIGURADAS
print("\n🔗 7. RUTAS CRÍTICAS CONFIGURADAS:")
from django.urls import reverse

rutas = [
    ('webhook whatsapp', 'webhook_whatsapp'),
    ('verificar certificado', 'verificar_certificado'),
    ('descargar certificado', 'descargar_certificado'),
]

print(f"   Para verificar rutas, ejecuta: python manage.py show_urls | grep -E 'certificado|webhook'")

# 8. RESUMEN FINAL
print("\n" + "=" * 80)
print("📊 RESUMEN:")
print("=" * 80)

critical_ok = (
    settings.DEBUG == False and
    'django-insecure' not in settings.SECRET_KEY and
    env_configured >= 4 and
    media_exists and
    todos_existen
)

if critical_ok:
    print("\n✅ SISTEMA LISTO PARA PRODUCCIÓN\n")
    print("   Próximos pasos:")
    print("   1. Verificar variables .env en servidor")
    print("   2. Hacer test end-to-end con usuario real")
    print("   3. Configurar email para notificaciones de soporte")
    print("   4. Backup de BD antes de deploy")
    print("   5. Monitorear logs después de deploy")
else:
    print("\n⚠️  FALTAN CONFIGURACIONES CRÍTICAS\n")
    print("   Cosas pendientes:")
    if settings.DEBUG:
        print("   • Cambiar DEBUG a False")
    if 'django-insecure' in settings.SECRET_KEY:
        print("   • Generar SECRET_KEY segura")
    if env_configured < 4:
        print("   • Configurar variables de entorno críticas")
    if not email_ok:
        print("   • Configurar servidor SMTP para email")

print("\n" + "=" * 80)
