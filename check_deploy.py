"""
Script de preparación para deployment en Render
Verifica que todo esté listo antes de subir a producción
"""
import os
import sys
from pathlib import Path

print("=" * 70)
print("🚀 PREPARACIÓN PARA DEPLOYMENT EN RENDER")
print("=" * 70)

errors = []
warnings = []
success = []

# 1. Verificar archivos necesarios
print("\n[1/6] 📄 Verificando archivos necesarios...")

required_files = {
    'requirements.txt': 'Dependencias de Python',
    'build.sh': 'Script de construcción',
    'render.yaml': 'Configuración de Render',
    '.gitignore': 'Ignorar archivos sensibles',
    'manage.py': 'Django management',
}

for file, desc in required_files.items():
    if Path(file).exists():
        success.append(f"✅ {file} - {desc}")
    else:
        errors.append(f"❌ Falta {file} - {desc}")

# 2. Verificar requirements.txt
print("\n[2/6] 📦 Verificando dependencias...")

try:
    with open('requirements.txt', 'r') as f:
        requirements = f.read()
        
    critical_deps = ['Django', 'gunicorn', 'psycopg2-binary', 'dj-database-url', 
                     'whitenoise', 'openai', 'python-dotenv']
    
    for dep in critical_deps:
        if dep.lower() in requirements.lower():
            success.append(f"✅ {dep} en requirements.txt")
        else:
            errors.append(f"❌ Falta {dep} en requirements.txt")
            
except Exception as e:
    errors.append(f"❌ Error leyendo requirements.txt: {str(e)}")

# 3. Verificar build.sh
print("\n[3/6] 🔨 Verificando build script...")

try:
    with open('build.sh', 'r') as f:
        build_script = f.read()
        
    required_commands = ['pip install', 'collectstatic', 'migrate']
    
    for cmd in required_commands:
        if cmd in build_script:
            success.append(f"✅ Comando '{cmd}' en build.sh")
        else:
            warnings.append(f"⚠️ Falta comando '{cmd}' en build.sh")
            
except Exception as e:
    errors.append(f"❌ Error leyendo build.sh: {str(e)}")

# 4. Verificar .env de ejemplo
print("\n[4/6] 🔐 Verificando variables de entorno...")

env_vars = {
    'WHATSAPP_TOKEN': 'Token de Meta WhatsApp',
    'WHATSAPP_PHONE_ID': 'ID del teléfono de WhatsApp',
    'OPENAI_API_KEY': 'API Key de OpenAI',
    'SECRET_KEY': 'Secret key de Django',
}

if Path('.env').exists():
    with open('.env', 'r') as f:
        env_content = f.read()
        
    for var, desc in env_vars.items():
        if var in env_content:
            # Verificar que no esté vacío
            if f'{var}=' in env_content:
                line = [l for l in env_content.split('\n') if l.startswith(f'{var}=')]
                if line and '=' in line[0]:
                    value = line[0].split('=', 1)[1].strip()
                    if value and value != '' and not value.startswith('#'):
                        success.append(f"✅ {var} configurado")
                    else:
                        warnings.append(f"⚠️ {var} está vacío - {desc}")
                else:
                    warnings.append(f"⚠️ {var} está vacío - {desc}")
        else:
            warnings.append(f"⚠️ Falta {var} - {desc}")
else:
    warnings.append("⚠️ No se encontró archivo .env (normal si ya está en producción)")

# 5. Verificar settings.py para producción
print("\n[5/6] ⚙️ Verificando configuración de Django...")

try:
    with open('mvp_project/settings.py', 'r') as f:
        settings = f.read()
        
    production_checks = {
        'whitenoise': 'WhiteNoise para archivos estáticos',
        'dj_database_url': 'Soporte para PostgreSQL',
        "os.environ.get('DATABASE_URL')": 'Configuración de base de datos',
        'ALLOWED_HOSTS': 'Hosts permitidos',
    }
    
    for check, desc in production_checks.items():
        if check in settings:
            success.append(f"✅ {desc}")
        else:
            errors.append(f"❌ Falta configuración: {desc}")
            
except Exception as e:
    errors.append(f"❌ Error leyendo settings.py: {str(e)}")

# 6. Verificar que .env NO esté en git
print("\n[6/6] 🔒 Verificando seguridad...")

try:
    with open('.gitignore', 'r') as f:
        gitignore = f.read()
        
    if '.env' in gitignore:
        success.append("✅ .env está en .gitignore (seguro)")
    else:
        errors.append("❌ ¡PELIGRO! .env NO está en .gitignore")
        
    if 'db.sqlite3' in gitignore:
        success.append("✅ db.sqlite3 está en .gitignore")
    else:
        warnings.append("⚠️ db.sqlite3 debería estar en .gitignore")
        
except Exception as e:
    errors.append(f"❌ Error leyendo .gitignore: {str(e)}")

# Mostrar resultados
print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

if success:
    print(f"\n✅ ÉXITOS ({len(success)}):")
    for s in success[:10]:  # Mostrar solo primeros 10
        print(f"   {s}")
    if len(success) > 10:
        print(f"   ... y {len(success) - 10} más")

if warnings:
    print(f"\n⚠️ ADVERTENCIAS ({len(warnings)}):")
    for w in warnings:
        print(f"   {w}")

if errors:
    print(f"\n❌ ERRORES CRÍTICOS ({len(errors)}):")
    for e in errors:
        print(f"   {e}")

print("\n" + "=" * 70)

if errors:
    print("❌ HAY ERRORES CRÍTICOS - Corrígelos antes de hacer deploy")
    print("\n💡 Pasos sugeridos:")
    print("   1. Revisa los errores listados arriba")
    print("   2. Corrige cada uno")
    print("   3. Ejecuta este script de nuevo")
    sys.exit(1)
elif warnings:
    print("⚠️ TODO LISTO pero hay algunas advertencias")
    print("\n💡 Recomendaciones:")
    print("   1. Revisa las advertencias (no críticas)")
    print("   2. Puedes continuar con el deploy")
    print("   3. Configura las variables en Render.com")
else:
    print("✅ ¡TODO PERFECTO! Listo para deploy")
    print("\n🚀 Próximos pasos:")
    print("   1. git init (si no lo has hecho)")
    print("   2. git add .")
    print('   3. git commit -m "Initial commit"')
    print("   4. Crear repo en GitHub")
    print("   5. git push origin main")
    print("   6. Conectar con Render.com")

print("\n📖 Guía completa: GUIA_META_WHATSAPP_RENDER.md")
print("=" * 70)
