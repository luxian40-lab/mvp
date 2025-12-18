from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.conf import settings
import json

from .models import Campana, EnvioLog, Estudiante, WhatsappLog
from .utils import enviar_whatsapp

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
    
    # WhatsApp logs (últimos 10)
    whatsapp_logs = WhatsappLog.objects.all().order_by('-fecha')[:10]
    whatsapp_total = WhatsappLog.objects.count()
    whatsapp_enviados = WhatsappLog.objects.filter(estado='SENT').count()
    whatsapp_entrantes = WhatsappLog.objects.filter(estado='INCOMING').count()

    context = {
        'total_campanas': total_campanas,
        'total_envios': total_envios,
        'exitosos': exitosos,
        'fallidos': fallidos,
        'pendientes': pendientes,
        'estudiantes_activos': estudiantes_activos,
        'whatsapp_logs': whatsapp_logs,
        'whatsapp_total': whatsapp_total,
        'whatsapp_enviados': whatsapp_enviados,
        'whatsapp_entrantes': whatsapp_entrantes,
    }
    
    # Renderizamos la plantilla que vamos a crear en el paso 2
    return render(request, 'admin/dashboard_metrics.html', context)


# ---------- Webhook para WhatsApp Cloud API ----------
@csrf_exempt
def whatsapp_webhook(request):
    """GET: Verificación del token (hub.verify_token).
       POST: Procesa mensajes entrantes y actualizaciones de estado.
    """
    if request.method == 'GET':
        verify_token = request.GET.get('hub.verify_token') or request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        expected = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', None)
        if verify_token and expected and verify_token == expected:
            return HttpResponse(challenge)
        return HttpResponse('Forbidden', status=403)

    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

        entries = payload.get('entry', []) or payload.get('entry', [])

        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})

                # Mensajes entrantes
                messages = value.get('messages', [])
                for m in messages:
                    phone = m.get('from')
                    msg_id = m.get('id')
                    text = ''
                    if 'text' in m and isinstance(m['text'], dict):
                        text = m['text'].get('body', '')
                    # Guardamos registro entrante
                    WhatsappLog.objects.create(
                        telefono=phone,
                        mensaje=text,
                        mensaje_id=msg_id,
                        estado='INCOMING'
                    )

                # Estados (delivery receipts)
                statuses = value.get('statuses', [])
                for s in statuses:
                    msg_id = s.get('id')
                    status = s.get('status')
                    if msg_id:
                        WhatsappLog.objects.filter(mensaje_id=msg_id).update(estado=status)

        return JsonResponse({'ok': True})
