from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .models import Campana, EnvioLog, Estudiante

@staff_member_required
def dashboard_view(request):
    # 1. Calcular Métricas
    total_campanas = Campana.objects.count()
    
    # Contamos logs
    total_envios = EnvioLog.objects.count()
    exitosos = EnvioLog.objects.filter(estado='ENVIADO').count()
    fallidos = EnvioLog.objects.filter(estado='FALLIDO').count()
    pendientes = EnvioLog.objects.filter(estado='PENDIENTE').count()
    
    estudiantes_activos = Estudiante.objects.filter(activo=True).count()

    context = {
        'total_campanas': total_campanas,
        'total_envios': total_envios,
        'exitosos': exitosos,
        'fallidos': fallidos,
        'pendientes': pendientes,
        'estudiantes_activos': estudiantes_activos,
    }
    
    # Renderizamos la plantilla que vamos a crear en el paso 2
    return render(request, 'admin/dashboard_metrics.html', context)