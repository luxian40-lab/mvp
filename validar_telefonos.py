#!/usr/bin/env python
"""
SCRIPT: Validar y Normalizar Números de Teléfono
Asegura que todos los teléfonos estén en formato: 57XXXXXXXXX
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante
import re

def normalizar_telefono(telefono):
    """
    Normaliza un teléfono a formato: 57XXXXXXXXX
    
    Acepta formatos:
    - 57XXXXXXXXX (ya normalizado)
    - 3XXXXXXXXX (sin el 57, agrega 57)
    - +573XXXXXXXXX (con +57)
    - +57 3 XXX XXX XXX (con espacios)
    """
    if not telefono:
        return None
    
    # Remover espacios y caracteres especiales
    telefono = re.sub(r'[\s\-\(\)\.]+', '', str(telefono).strip())
    
    # Remover + al inicio
    if telefono.startswith('+'):
        telefono = telefono[1:]
    
    # Si empieza con 573, ya tiene el 57
    if telefono.startswith('573') and len(telefono) == 12:
        return telefono
    
    # Si empieza con 3, agregar 57
    if telefono.startswith('3') and len(telefono) == 10:
        return f"57{telefono}"
    
    # Si empieza con 573 pero no tiene la longitud correcta
    if telefono.startswith('573'):
        return None
    
    return None

def main():
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

if __name__ == '__main__':
    main()
