#!/usr/bin/env python
"""
Script completo para importar estudiantes y enviar campaña con plantilla aprobada
"""
import os
import django
import pandas as pd
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, Campana, Plantilla, Linea
from core.enviar_plantillas import enviar_campana_con_plantilla

def importar_estudiantes_desde_excel(archivo_excel: str):
    """
    Importa estudiantes desde un archivo Excel
    
    Columnas requeridas:
    - nombre
    - telefono (formato: 573001234567 o +573001234567)
    - ubicacion (opcional)
    """
    print(f"\n📂 Leyendo archivo: {archivo_excel}")
    
    try:
        df = pd.read_excel(archivo_excel)
        print(f"   ✅ Archivo cargado: {len(df)} filas")
    except Exception as e:
        print(f"   ❌ Error al leer archivo: {e}")
        return 0
    
    # Verificar columnas
    columnas_requeridas = ['nombre', 'telefono']
    if not all(col in df.columns for col in columnas_requeridas):
        print(f"   ❌ El archivo debe tener las columnas: {columnas_requeridas}")
        print(f"   Columnas encontradas: {list(df.columns)}")
        return 0
    
    creados = 0
    actualizados = 0
    errores = 0
    
    print(f"\n📥 Importando estudiantes...")
    
    for index, row in df.iterrows():
        try:
            nombre = str(row['nombre']).strip()
            telefono = str(row['telefono']).strip()
            ubicacion = str(row.get('ubicacion', '')).strip() if 'ubicacion' in row else ''
            
            # Limpiar teléfono
            telefono = telefono.replace('+', '').replace(' ', '').replace('-', '')
            if not telefono.startswith('57'):
                telefono = f'57{telefono}'
            
            # Crear o actualizar estudiante
            estudiante, created = Estudiante.objects.update_or_create(
                telefono=telefono,
                defaults={
                    'nombre': nombre,
                    'ubicacion': ubicacion,
                    'activo': True
                }
            )
            
            if created:
                creados += 1
                print(f"   ✅ Creado: {nombre} ({telefono})")
            else:
                actualizados += 1
                print(f"   🔄 Actualizado: {nombre} ({telefono})")
                
        except Exception as e:
            errores += 1
            print(f"   ❌ Error en fila {index + 2}: {e}")
    
    print(f"\n📊 Resumen:")
    print(f"   Creados: {creados}")
    print(f"   Actualizados: {actualizados}")
    print(f"   Errores: {errores}")
    
    return creados + actualizados


def crear_plantilla_bienvenida():
    """
    Crea plantilla de bienvenida en la base de datos
    """
    print("\n📝 Verificando plantilla de bienvenida...")
    
    plantilla, created = Plantilla.objects.get_or_create(
        nombre='Bienvenida Estudiante',
        defaults={
            'cuerpo_mensaje': '''Hola {{nombre}} 👋

Bienvenido a Eki, tu plataforma de educación agrícola.

Tenemos un nuevo curso disponible: {{curso}}

¿Quieres empezar? Responde "SI" para inscribirte.''',
            'tiene_imagen': False,
            'proveedor': 'twilio',
            'twilio_template_sid': ''  # Aquí va el Content SID de Twilio cuando esté aprobado
        }
    )
    
    if created:
        print(f"   ✅ Plantilla creada: {plantilla.nombre}")
    else:
        print(f"   ✅ Plantilla ya existe: {plantilla.nombre}")
    
    if not plantilla.twilio_template_sid:
        print(f"\n   ⚠️  IMPORTANTE: Debes agregar el Content SID de Twilio")
        print(f"   1. Ve a: https://console.twilio.com/us1/develop/sms/content-editor")
        print(f"   2. Crea la plantilla y cópialo SID (ejemplo: HXa1b2c3...)")
        print(f"   3. Agrégalo en Admin > Plantillas > {plantilla.nombre}")
    
    return plantilla


def crear_campana_con_estudiantes(nombre_campana: str, curso_nombre: str = 'Plátano Hartón'):
    """
    Crea una campaña y asigna todos los estudiantes activos
    """
    print(f"\n📢 Creando campaña: {nombre_campana}")
    
    # Verificar que exista plantilla
    try:
        plantilla = Plantilla.objects.get(nombre='Bienvenida Estudiante')
    except Plantilla.DoesNotExist:
        print("   ❌ No existe la plantilla 'Bienvenida Estudiante'")
        return None
    
    # Crear campaña
    campana, created = Campana.objects.get_or_create(
        nombre=nombre_campana,
        defaults={
            'plantilla': plantilla,
            'descripcion': f'Campaña de bienvenida para curso {curso_nombre}',
            'estado': 'Programada',
            'proveedor': 'twilio'
        }
    )
    
    if created:
        print(f"   ✅ Campaña creada")
    else:
        print(f"   ✅ Campaña ya existe")
    
    # Agregar estudiantes activos
    estudiantes = Estudiante.objects.filter(activo=True)
    
    if estudiantes.count() == 0:
        print("   ⚠️  No hay estudiantes activos")
        return campana
    
    print(f"\n📋 Agregando destinatarios...")
    agregados = 0
    
    for estudiante in estudiantes:
        # Crear variables personalizadas
        variables = {
            'nombre': estudiante.nombre,
            'curso': curso_nombre
        }
        
        linea, created = Linea.objects.get_or_create(
            campana=campana,
            estudiante=estudiante,
            defaults={
                'variables_personalizadas': variables
            }
        )
        
        if created:
            agregados += 1
    
    print(f"   ✅ {agregados} destinatarios agregados")
    print(f"   Total en campaña: {campana.lineas.count()}")
    
    return campana


def enviar_campana(campana_id: int):
    """
    Envía una campaña con plantilla aprobada
    """
    try:
        campana = Campana.objects.get(id=campana_id)
    except Campana.DoesNotExist:
        print(f"❌ No existe campaña con ID {campana_id}")
        return
    
    print(f"\n📤 Enviando campaña: {campana.nombre}")
    print(f"   Destinatarios: {campana.lineas.count()}")
    
    # Verificar que la plantilla tenga Content SID
    if not campana.plantilla.twilio_template_sid:
        print(f"\n   ❌ ERROR: La plantilla no tiene Content SID de Twilio")
        print(f"   Debes crear y aprobar la plantilla en Twilio primero")
        return
    
    # Confirmar envío
    print(f"\n   ⚠️  Esto enviará {campana.lineas.count()} mensajes de WhatsApp")
    confirmar = input("   ¿Continuar? (SI/NO): ")
    
    if confirmar.upper() != 'SI':
        print("   ❌ Envío cancelado")
        return
    
    # Enviar
    resultado = enviar_campana_con_plantilla(campana.id)
    
    print(f"\n📊 Resultado:")
    print(f"   Exitosos: {resultado['exitosos']}")
    print(f"   Fallidos: {resultado['fallidos']}")
    print(f"   Total: {resultado['total']}")
    
    if resultado['errores']:
        print(f"\n⚠️  Errores encontrados:")
        for error in resultado['errores'][:5]:  # Mostrar primeros 5
            print(f"   - {error}")


def menu_principal():
    """
    Menú interactivo
    """
    print("=" * 70)
    print("📱 SISTEMA DE CAMPAÑAS WHATSAPP - EKI")
    print("=" * 70)
    
    while True:
        print("\n¿Qué deseas hacer?\n")
        print("1. Importar estudiantes desde Excel")
        print("2. Crear plantilla de bienvenida")
        print("3. Crear campaña con todos los estudiantes")
        print("4. Enviar campaña existente")
        print("5. Ver resumen del sistema")
        print("6. Salir")
        
        opcion = input("\nOpción: ").strip()
        
        if opcion == '1':
            archivo = input("\nRuta del archivo Excel: ").strip()
            if os.path.exists(archivo):
                importar_estudiantes_desde_excel(archivo)
            else:
                print(f"❌ Archivo no encontrado: {archivo}")
        
        elif opcion == '2':
            crear_plantilla_bienvenida()
        
        elif opcion == '3':
            nombre = input("\nNombre de la campaña: ").strip()
            curso = input("Nombre del curso (Enter = Plátano Hartón): ").strip()
            if not curso:
                curso = 'Plátano Hartón'
            crear_campana_con_estudiantes(nombre, curso)
        
        elif opcion == '4':
            try:
                campana_id = int(input("\nID de la campaña: ").strip())
                enviar_campana(campana_id)
            except ValueError:
                print("❌ Debe ser un número")
        
        elif opcion == '5':
            print("\n📊 RESUMEN DEL SISTEMA")
            print("=" * 70)
            print(f"Estudiantes activos: {Estudiante.objects.filter(activo=True).count()}")
            print(f"Campañas totales: {Campana.objects.count()}")
            print(f"Plantillas disponibles: {Plantilla.objects.count()}")
            
            print("\n📢 Campañas:")
            for campana in Campana.objects.all()[:10]:
                destinatarios = campana.lineas.count()
                print(f"   {campana.id}. {campana.nombre} - {destinatarios} destinatarios - {campana.estado}")
        
        elif opcion == '6':
            print("\n👋 ¡Hasta luego!")
            break
        
        else:
            print("❌ Opción inválida")


def crear_excel_ejemplo():
    """
    Crea un archivo Excel de ejemplo
    """
    datos = {
        'nombre': ['Juan Pérez', 'María González', 'Carlos Rodríguez'],
        'telefono': ['3001234567', '3109876543', '3157654321'],
        'ubicacion': ['Antioquia', 'Valle', 'Cundinamarca']
    }
    
    df = pd.DataFrame(datos)
    archivo = 'estudiantes_ejemplo.xlsx'
    df.to_excel(archivo, index=False)
    print(f"✅ Archivo de ejemplo creado: {archivo}")
    return archivo


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--ejemplo':
        # Crear Excel de ejemplo
        archivo = crear_excel_ejemplo()
        print(f"\nPuedes editar este archivo y luego importarlo")
    else:
        # Menú principal
        menu_principal()
