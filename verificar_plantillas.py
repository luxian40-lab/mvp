#!/usr/bin/env python
"""
Script para verificar el estado de las plantillas y sus Content Templates
"""
import os
import sys
import django
import logging

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eki_mvp.settings')
django.setup()

from core.models import Plantilla

logger = logging.getLogger("verificar_plantillas")

def main():
    try:
        print("🔍 VERIFICACIÓN DE PLANTILLAS Y CONTENT TEMPLATES")
        print("=" * 60)

        plantillas = Plantilla.objects.all().order_by('categoria', 'nombre_interno')

        if not plantillas:
            print("❌ No hay plantillas configuradas")
            return

        categorias = {}
        for plantilla in plantillas:
            cat = plantilla.get_categoria_display()
            if cat not in categorias:
                categorias[cat] = []
            categorias[cat].append(plantilla)

        for categoria, plantillas_cat in categorias.items():
            print(f"\n🌾 {categoria.upper()}")
            print("-" * 40)

            for plantilla in plantillas_cat:
                estado = "❌ SIN CONFIGURAR"
                if plantilla.twilio_template_sid:
                    if plantilla.aprobada_twilio:
                        estado = f"✅ CONFIGURADO (SID: {plantilla.twilio_template_sid[:12]}...)"
                    else:
                        estado = f"⏳ PENDIENTE (SID: {plantilla.twilio_template_sid[:12]}...)"

                print(f"  📝 {plantilla.nombre_interno}")
                print(f"     Estado: {estado}")
                print(f"     Activa: {'✅' if plantilla.activa else '❌'}")
                print(f"     Usos: {plantilla.veces_usada}")
                print()

        # Resumen
        total = plantillas.count()
        configuradas = plantillas.filter(twilio_template_sid__isnull=False, aprobada_twilio=True).count()
        pendientes = plantillas.filter(twilio_template_sid__isnull=False, aprobada_twilio=False).count()
        sin_configurar = plantillas.filter(twilio_template_sid__isnull=True).count()

        print("\n📊 RESUMEN")
        print("=" * 30)
        print(f"Total de plantillas: {total}")
        print(f"✅ Con Content Template: {configuradas}")
        print(f"⏳ Pendientes de aprobación: {pendientes}")
        print(f"❌ Sin configurar: {sin_configurar}")
        if configuradas == 0:
            print("\n⚠️  ADVERTENCIA:")
            print("   No tienes plantillas con Content Templates configurados.")
            print("   Las campañas usarán envío directo (sin template).")
            print("\n   Para usar Content Templates:")
            print("   1. Ve a https://console.twilio.com/us1/develop/sms/content-editor")
            print("   2. Crea plantillas de WhatsApp")
            print("   3. Configura los SIDs en las plantillas del admin")
            print("   4. Marca como 'Aprobada en Twilio'")
    except Exception as e:
        logger.exception(f"Error en verificación de plantillas: {e}")
        print(f"\n[ERROR] Ocurrió un error inesperado: {e}")

if __name__ == "__main__":
    main()
    print(f"✅ Con Content Template: {configuradas}")
    print(f"⏳ Pendientes de aprobación: {pendientes}")
    print(f"❌ Sin configurar: {sin_configurar}")

    if configuradas == 0:
        print("\n⚠️  ADVERTENCIA:")
        print("   No tienes plantillas con Content Templates configurados.")
        print("   Las campañas usarán envío directo (sin template).")
        print("\n   Para usar Content Templates:")
        print("   1. Ve a https://console.twilio.com/us1/develop/sms/content-editor")
        print("   2. Crea plantillas de WhatsApp")
        print("   3. Configura los SIDs en las plantillas del admin")
        print("   4. Marca como 'Aprobada en Twilio'")

if __name__ == "__main__":
    verificar_plantillas()