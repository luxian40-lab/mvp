import os
import django

# Silenciar output de settings
import sys
import io
old_stderr = sys.stderr
sys.stderr = io.StringIO()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production')
django.setup()

sys.stderr = old_stderr  # Restaurar stderr

from core.models import Estudiante, ProgresoEstudiante, ModuloCompletado, WhatsappLog

# Buscar estudiante Julián
telefono = "573202948806"  # Sin el whatsapp: prefix
estudiante = Estudiante.objects.filter(telefono__contains=telefono).first()

if estudiante:
    print(f"✅ Estudiante encontrado: {estudiante.nombre}")
    print(f"   Teléfono: {estudiante.telefono}")
    print(f"   Estado onboarding: {estudiante.estado_onboarding}")
    print(f"   ID: {estudiante.id}")
    print()
    
    # Ver progresos
    progresos = ProgresoEstudiante.objects.filter(estudiante=estudiante)
    print(f"📚 Progresos ({progresos.count()}):")
    for prog in progresos:
        print(f"   - Curso: {prog.curso.nombre}")
        print(f"     Módulo actual: {prog.modulo_actual.numero if prog.modulo_actual else 'None'} - {prog.modulo_actual.titulo if prog.modulo_actual else 'N/A'}")
        print(f"     Completado: {prog.completado}")
        print(f"     Avance: {prog.porcentaje_avance()}%")
        print()
    
    # Ver módulos completados
    completados = ModuloCompletado.objects.filter(progreso__estudiante=estudiante)
    print(f"✅ Módulos completados ({completados.count()}):")
    for comp in completados:
        print(f"   - {comp.modulo.numero}. {comp.modulo.titulo}")
    print()
    
    # Ver últimos 10 mensajes
    logs = WhatsappLog.objects.filter(telefono__contains=telefono).order_by('-fecha')[:15]
    print(f"💬 Últimos mensajes:")
    for log in logs:
        tipo_emoji = "📩" if log.tipo == "INCOMING" else "📤"
        mensaje_corto = log.mensaje[:80] + "..." if len(log.mensaje) > 80 else log.mensaje
        print(f"   {tipo_emoji} {log.fecha.strftime('%H:%M:%S')}: {mensaje_corto}")
    
else:
    print(f"❌ No se encontró estudiante con teléfono: {telefono}")
    print("\nBuscando por otros números...")
    estudiantes = Estudiante.objects.all()
    for est in estudiantes:
           # Eliminado filtro por nombre Julian/Julián
           print(f"   - {est.nombre}: {est.telefono}")
