
#!/usr/bin/env python
"""
SCRIPT: Validar y Normalizar Números de Teléfono
Asegura que todos los teléfonos estén en formato: 57XXXXXXXXX
"""

import os
import django
import logging
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante

logger = logging.getLogger("validar_telefonos")

def normalizar_telefono(telefono):
    """
    Normaliza un teléfono a formato: 57XXXXXXXXX
    ...existing code...
    return None

def main():
    try:
        print("\n" + "="*80)
        print("🔍 VALIDAR Y NORMALIZAR TELÉFONOS")
        print("="*80)
        estudiantes = Estudiante.objects.all()
        print(f"\n📊 Total de estudiantes: {estudiantes.count()}")
        validos = 0
        invalidos = []
        normalizados = 0
        print("\n" + "-"*80)
        for estudiante in estudiantes:
            telefono_original = estudiante.telefono
            telefono_normalizado = normalizar_telefono(telefono_original)
            if telefono_normalizado:
                if telefono_normalizado != telefono_original:
                    # Verificar que no exista otro estudiante con el número normalizado
                    otro = Estudiante.objects.filter(telefono=telefono_normalizado).exclude(id=estudiante.id).exists()
                    if not otro:
                        estudiante.telefono = telefono_normalizado
                        estudiante.save()
                        print(f"✅ {estudiante.nombre}: {telefono_original} → {telefono_normalizado}")
                        normalizados += 1
                    else:
                        print(f"⚠️  {estudiante.nombre}: Duplicado potencial: {telefono_normalizado}")
                        invalidos.append((estudiante.nombre, telefono_original, "Duplicado"))
                else:
                    validos += 1
            else:
                print(f"❌ {estudiante.nombre}: {telefono_original} (INVÁLIDO)")
                invalidos.append((estudiante.nombre, telefono_original, "Formato inválido"))
        print("\n" + "="*80)
        print("📊 RESULTADO")
        print("="*80)
        print(f"✅ Teléfonos válidos: {validos}")
        print(f"✏️  Teléfonos normalizados: {normalizados}")
        print(f"❌ Teléfonos inválidos: {len(invalidos)}")
        if invalidos:
            print("\n❌ Estudiantes con teléfono inválido:")
            for nombre, telefono, razon in invalidos:
                print(f"   • {nombre}: {telefono} ({razon})")
        print("\n" + "="*80)
    except Exception as e:
        logger.exception(f"Error en validación/normalización de teléfonos: {e}")
        print(f"\n[ERROR] Ocurrió un error inesperado: {e}")

if __name__ == '__main__':
    main()
