"""
🔍 VERIFICADOR DE CONFIGURACIÓN PRE-DEPLOYMENT
Verifica que tu proyecto esté listo para deployment
"""

import os
import sys
from pathlib import Path

# Colores para terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check_file_exists(filepath, required=True):
    """Verifica que un archivo existe"""
    exists = Path(filepath).exists()
    status = f"{GREEN}✓{RESET}" if exists else f"{RED}✗{RESET}"
    required_text = "(REQUERIDO)" if required else "(OPCIONAL)"
    print(f"{status} {filepath} {required_text}")
    return exists

def check_env_var(var_name, required=True):
    """Verifica que una variable de entorno esté definida"""
    from dotenv import load_dotenv
    load_dotenv()
    
    value = os.getenv(var_name)
    has_value = value is not None and value != ''
    status = f"{GREEN}✓{RESET}" if has_value else f"{RED}✗{RESET}"
    required_text = "(REQUERIDO)" if required else "(OPCIONAL)"
    
    # Ocultar valores sensibles
    display_value = "***" if has_value and len(value) > 10 else value
    print(f"{status} {var_name} = {display_value} {required_text}")
    return has_value

def check_installed_package(package_name):
    """Verifica que un paquete esté instalado"""
    try:
        __import__(package_name)
        print(f"{GREEN}✓{RESET} {package_name}")
        return True
    except ImportError:
        print(f"{RED}✗{RESET} {package_name}")
        return False

def main():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}🔍 VERIFICADOR PRE-DEPLOYMENT - EKI MVP{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    issues = []
    
    # 1. Archivos críticos
    print(f"\n{YELLOW}📁 Verificando archivos críticos...{RESET}")
    if not check_file_exists('requirements.txt'):
        issues.append("Falta requirements.txt")
    if not check_file_exists('Procfile'):
        issues.append("Falta Procfile")
    if not check_file_exists('runtime.txt'):
        issues.append("Falta runtime.txt")
    if not check_file_exists('.env'):
        issues.append("Falta .env (copia de .env.example)")
    if not check_file_exists('.env.example'):
        issues.append("Falta .env.example")
    if not check_file_exists('.gitignore'):
        issues.append("Falta .gitignore")
    
    # 2. Paquetes críticos
    print(f"\n{YELLOW}📦 Verificando dependencias instaladas...{RESET}")
    critical_packages = [
        ('django', 'django'),
        ('gunicorn', 'gunicorn'),
        ('psycopg2', 'psycopg2'),
        ('boto3', 'boto3'),
        ('storages', 'storages'),
        ('dotenv', 'python-dotenv'),
        ('whitenoise', 'whitenoise')
    ]
    
    for import_name, package_name in critical_packages:
        try:
            __import__(import_name)
            print(f"{GREEN}✓{RESET} {package_name}")
        except ImportError:
            print(f"{RED}✗{RESET} {package_name}")
            issues.append(f"Falta paquete: {package_name}")
    
    # 3. Variables de entorno - Django Core
    print(f"\n{YELLOW}🔒 Verificando variables Django Core...{RESET}")
    if not check_env_var('SECRET_KEY'):
        issues.append("Falta SECRET_KEY")
    if not check_env_var('DEBUG', required=False):
        print(f"  {YELLOW}⚠{RESET} Tip: DEBUG debería ser 'False' en producción")
    check_env_var('ALLOWED_HOSTS', required=False)
    
    # 4. Variables de entorno - Database
    print(f"\n{YELLOW}🗄️ Verificando configuración de base de datos...{RESET}")
    has_db_url = check_env_var('DATABASE_URL', required=False)
    if not has_db_url:
        print(f"  {YELLOW}⚠{RESET} DATABASE_URL no configurada (OK para desarrollo local)")
        print(f"  {YELLOW}⚠{RESET} REQUERIDO para producción")
    
    # 5. Variables de entorno - AWS S3
    print(f"\n{YELLOW}☁️ Verificando configuración AWS S3...{RESET}")
    use_s3 = os.getenv('USE_S3', 'False') == 'True'
    print(f"  USE_S3 = {use_s3}")
    
    if use_s3:
        if not check_env_var('AWS_ACCESS_KEY_ID'):
            issues.append("USE_S3=True pero falta AWS_ACCESS_KEY_ID")
        if not check_env_var('AWS_SECRET_ACCESS_KEY'):
            issues.append("USE_S3=True pero falta AWS_SECRET_ACCESS_KEY")
        if not check_env_var('AWS_STORAGE_BUCKET_NAME'):
            issues.append("USE_S3=True pero falta AWS_STORAGE_BUCKET_NAME")
        check_env_var('AWS_S3_REGION_NAME', required=False)
    else:
        print(f"  {YELLOW}ℹ{RESET} S3 deshabilitado (archivos en carpeta local)")
        print(f"  {YELLOW}⚠{RESET} Recuerda habilitar S3 en producción (USE_S3=True)")
    
    # 6. Variables de entorno - WhatsApp
    print(f"\n{YELLOW}📱 Verificando configuración WhatsApp...{RESET}")
    check_env_var('WHATSAPP_API_TOKEN', required=False)
    check_env_var('WHATSAPP_PHONE_ID', required=False)
    check_env_var('WHATSAPP_WEBHOOK_TOKEN', required=False)
    
    # 7. Settings.py configuration
    print(f"\n{YELLOW}⚙️ Verificando settings.py...{RESET}")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
        import django
        django.setup()
        
        from django.conf import settings
        
        # Verificar storages en INSTALLED_APPS
        if 'storages' in settings.INSTALLED_APPS:
            print(f"{GREEN}✓{RESET} 'storages' en INSTALLED_APPS")
        else:
            print(f"{RED}✗{RESET} 'storages' NO está en INSTALLED_APPS")
            issues.append("Falta 'storages' en INSTALLED_APPS")
        
        # Verificar WhiteNoise
        if 'whitenoise.middleware.WhiteNoiseMiddleware' in settings.MIDDLEWARE:
            print(f"{GREEN}✓{RESET} WhiteNoise configurado")
        else:
            print(f"{YELLOW}⚠{RESET} WhiteNoise no está en MIDDLEWARE")
        
    except Exception as e:
        print(f"{RED}✗{RESET} Error al cargar settings: {e}")
        issues.append(f"Error en settings.py: {e}")
    
    # 8. Resumen final
    print(f"\n{BLUE}{'='*60}{RESET}")
    if not issues:
        print(f"{GREEN}✅ ¡TODO LISTO PARA DEPLOYMENT!{RESET}")
        print(f"\n{GREEN}Próximos pasos:{RESET}")
        print(f"  1. Crear RDS PostgreSQL en AWS")
        print(f"  2. Crear Bucket S3 para audios")
        print(f"  3. Configurar variables de entorno en AWS App Runner")
        print(f"  4. Deploy desde GitHub")
        print(f"  5. Ejecutar migraciones en producción")
    else:
        print(f"{RED}⚠️ PROBLEMAS ENCONTRADOS ({len(issues)}):{RESET}")
        for issue in issues:
            print(f"  {RED}•{RESET} {issue}")
        print(f"\n{YELLOW}Corrige estos problemas antes de deployar.{RESET}")
        return 1
    
    print(f"{BLUE}{'='*60}{RESET}\n")
    return 0

if __name__ == '__main__':
    sys.exit(main())
