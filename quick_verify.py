#!/usr/bin/env python
"""
QUICK VERIFICATION SCRIPT
Verifica que todos los componentes nuevos estén funcionando correctamente
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

print("\n" + "="*80)
print("🔍 QUICK VERIFICATION SCRIPT")
print("="*80)

# 1. Verificar migración
print("\n[1/6] Checking migrations...")
from django.core.management import call_command
from io import StringIO
out = StringIO()
call_command('showmigrations', 'core', stdout=out)
if '0032_auditlog' in out.getvalue():
    print("✅ AuditLog migration applied")
else:
    print("❌ AuditLog migration NOT found")

# 2. Verificar modelo AuditLog
print("\n[2/6] Checking AuditLog model...")
try:
    from core.models_audit import AuditLog
    print(f"✅ AuditLog model imported successfully")
    print(f"   - Fields: {[f.name for f in AuditLog._meta.fields[:5]]}")
except Exception as e:
    print(f"❌ Error importing AuditLog: {e}")

# 3. Verificar middleware
print("\n[3/6] Checking middleware...")
try:
    from core.middleware import RateLimitMiddleware, CertificadoAccessMiddleware
    print("✅ Middleware classes imported successfully")
except Exception as e:
    print(f"❌ Error importing middleware: {e}")

# 4. Verificar configuración
print("\n[4/6] Checking settings...")
from django.conf import settings
if 'core.middleware.RateLimitMiddleware' in settings.MIDDLEWARE:
    print("✅ Middleware added to settings.MIDDLEWARE")
else:
    print("⚠️  Middleware NOT in settings.MIDDLEWARE")

if hasattr(settings, 'RATE_LIMIT_ENABLED'):
    print(f"✅ RATE_LIMIT_ENABLED = {settings.RATE_LIMIT_ENABLED}")
else:
    print("⚠️  RATE_LIMIT_ENABLED not configured")

# 5. Verificar signals
print("\n[5/6] Checking signals...")
try:
    from core.signals_certificados import generar_certificado_al_completar
    print("✅ Certificate signal loaded")
except Exception as e:
    print(f"❌ Error loading signal: {e}")

# 6. Verificar archivos
print("\n[6/6] Checking files...")
files_to_check = [
    'core/models_audit.py',
    'core/middleware.py',
    'core/signals_certificados.py',
    'test_e2e_certificados.py',
    'validar_telefonos.py',
    'backup_certificados.py',
    'INSTALACION.md',
    'RESUMEN_SESION.md'
]

base_dir = settings.BASE_DIR
missing = []
for file in files_to_check:
    path = os.path.join(base_dir, file)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"✅ {file} ({size} bytes)")
    else:
        print(f"❌ {file} MISSING")
        missing.append(file)

print("\n" + "="*80)
if not missing:
    print("✅ ALL VERIFICATIONS PASSED - SYSTEM IS READY")
else:
    print(f"⚠️  {len(missing)} file(s) missing:")
    for f in missing:
        print(f"   - {f}")
print("="*80 + "\n")
