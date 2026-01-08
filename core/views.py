from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from .models import Campana, Estudiante, WhatsappLog, EnvioLog  # ✅ Agregado EnvioLog
from .message_handler import procesar_twilio_webhook, procesar_meta_webhook

@staff_member_required
def dashboard_view(request):
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    
    # 1. Calcular Métricas REALES (solo WhatsappLog)
    total_campanas = Campana.objects.count()
    estudiantes_activos = Estudiante.objects.filter(activo=True).count()
    
    # Métricas de WhatsApp (DATOS REALES)
    whatsapp_logs = WhatsappLog.objects.all().order_by('-fecha')[:10]
    whatsapp_total = WhatsappLog.objects.count()
    whatsapp_enviados = WhatsappLog.objects.filter(tipo='SENT').count()
    whatsapp_recibidos = WhatsappLog.objects.filter(tipo='INCOMING').count()
    
    # Conversaciones únicas (estudiantes que han conversado)
    conversaciones_activas = WhatsappLog.objects.values('telefono').distinct().count()
    
    # Datos para gráficos - Últimos 7 días
    hoy = datetime.now().date()
    hace_7_dias = hoy - timedelta(days=7)
    
    # Mensajes por día (últimos 7 días)
    mensajes_por_dia = WhatsappLog.objects.filter(
        fecha__gte=hace_7_dias
    ).annotate(
        dia=TruncDate('fecha')
    ).values('dia').annotate(
        total=Count('id')
    ).order_by('dia')
    
    # Preparar datos para Chart.js
    dias_labels = []
    dias_valores = []
    for i in range(7):
        dia = hoy - timedelta(days=6-i)
        dias_labels.append(dia.strftime('%d/%m'))
        count = next((m['total'] for m in mensajes_por_dia if m['dia'] == dia), 0)
        dias_valores.append(count)
    
    # Mensajes por tipo (últimos 30 días) - DATOS REALES
    hace_30_dias = hoy - timedelta(days=30)
    mensajes_enviados_30d = WhatsappLog.objects.filter(
        fecha__gte=hace_30_dias,
        tipo='SENT'
    ).count()
    mensajes_recibidos_30d = WhatsappLog.objects.filter(
        fecha__gte=hace_30_dias,
        tipo='INCOMING'
    ).count()

    context = {
        'total_campanas': total_campanas,
        'estudiantes_activos': estudiantes_activos,
        'conversaciones_activas': conversaciones_activas,
        
        # WhatsApp Logs (DATOS REALES)
        'whatsapp_logs': whatsapp_logs,
        'whatsapp_total': whatsapp_total,
        'whatsapp_enviados': whatsapp_enviados,
        'whatsapp_recibidos': whatsapp_recibidos,
        
        # Datos para gráficos
        'chart_dias_labels': json.dumps(dias_labels),
        'chart_dias_valores': json.dumps(dias_valores),
        'chart_enviados_30d': mensajes_enviados_30d,
        'chart_recibidos_30d': mensajes_recibidos_30d,
        
        # Timestamp para auto-refresh
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
    }
    
    return render(request, 'admin/dashboard_metrics.html', context)


# ---------- Vista de importación de estudiantes ----------
@staff_member_required
def importar_estudiantes(request):
    """Vista para importar estudiantes desde un archivo Excel."""
    context = {}
    
    if request.method == 'POST':
        archivo = request.FILES.get('archivo_excel')
        
        if not archivo:
            context['error'] = "Por favor selecciona un archivo Excel"
            return render(request, 'admin/importar_estudiantes.html', context)
        
        try:
            # Verificar que sea Excel
            if not archivo.name.endswith(('.xlsx', '.xls')):
                context['error'] = 'El archivo debe ser .xlsx o .xls'
                return render(request, 'admin/importar_estudiantes.html', context)
            
            # Cargar el libro de trabajo
            wb = openpyxl.load_workbook(archivo)
            ws = wb.active
            
            estudiantes_creados = 0
            estudiantes_actualizados = 0
            errores = []
            
            # Iteramos desde la fila 2 (saltar encabezados)
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    # Esperamos: Nombre en columna A, Teléfono en columna B
                    nombre = row[0]
                    telefono = row[1]
                    
                    # Validar que no estén vacíos
                    if not nombre or not telefono:
                        continue
                    
                    # Limpiar teléfono y nombre
                    telefono_str = str(telefono).strip()
                    nombre_str = str(nombre).strip()
                    
                    # Crear o actualizar estudiante
                    estudiante, creado = Estudiante.objects.update_or_create(
                        telefono=telefono_str,
                        defaults={
                            'nombre': nombre_str,
                            'activo': True
                        }
                    )
                    
                    if creado:
                        estudiantes_creados += 1
                    else:
                        estudiantes_actualizados += 1
                    
                except Exception as e:
                    errores.append(f"Fila {row_idx}: {str(e)}")
            
            # Configurar contexto de éxito
            context['exito'] = True
            context['creados'] = estudiantes_creados
            context['actualizados'] = estudiantes_actualizados
            context['total'] = estudiantes_creados + estudiantes_actualizados
            
            if errores:
                context['advertencias'] = errores[:10]  # Mostrar primeras 10
        
        except Exception as e:
            context['error'] = f'Error al procesar el archivo: {str(e)}'
    
    # GET: Mostrar formulario
    return render(request, 'admin/importar_estudiantes.html', context)


# ---------- Vista de descarga de reportes ----------
@staff_member_required
def descargar_reportes(request):
    """Vista para descargar reportes en Excel filtrando por fechas."""
    context = {}
    
    if request.method == 'POST':
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        tipo_reporte = request.POST.get('tipo_reporte', 'todos')  # todos, envios, whatsapp
        
        try:
            # Parsear fechas
            inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d') if fecha_inicio else None
            fin = datetime.strptime(fecha_fin, '%Y-%m-%d') if fecha_fin else None
            
            # Ajustar fin de día
            if fin:
                fin = fin.replace(hour=23, minute=59, second=59)
            
            # Crear workbook
            wb = openpyxl.Workbook()
            wb.remove(wb.active)  # Eliminar hoja por defecto
            
            # Estilos
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            
            # ========== ENVÍOS ==========
            if tipo_reporte in ['todos', 'envios']:
                ws_envios = wb.create_sheet('Envíos')
                
                # Filtrar por fecha
                queryset = EnvioLog.objects.all()
                if inicio:
                    queryset = queryset.filter(fecha_envio__gte=inicio)
                if fin:
                    queryset = queryset.filter(fecha_envio__lte=fin)
                queryset = queryset.order_by('-fecha_envio')
                
                # Encabezados
                headers = ['ID', 'Estudiante', 'Teléfono', 'Campaña', 'Plantilla', 'Estado', 'Fecha', 'Respuesta API']
                ws_envios.append(headers)
                
                # Aplicar estilos a encabezados
                for cell in ws_envios[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                
                # Datos
                for log in queryset:
                    fecha_str = log.fecha_envio.strftime('%Y-%m-%d %H:%M:%S') if log.fecha_envio else ''
                    row = [
                        log.id,
                        log.estudiante.nombre,
                        log.estudiante.telefono,
                        log.campana.nombre,
                        log.campana.plantilla.nombre_interno,
                        log.estado,
                        fecha_str,
                        log.respuesta_api or ''
                    ]
                    ws_envios.append(row)
                
                # Ajustar ancho de columnas
                ws_envios.column_dimensions['A'].width = 8
                ws_envios.column_dimensions['B'].width = 20
                ws_envios.column_dimensions['C'].width = 15
                ws_envios.column_dimensions['D'].width = 20
                ws_envios.column_dimensions['E'].width = 20
                ws_envios.column_dimensions['F'].width = 12
                ws_envios.column_dimensions['G'].width = 20
                ws_envios.column_dimensions['H'].width = 30
            
            # ========== WHATSAPP ==========
            if tipo_reporte in ['todos', 'whatsapp']:
                ws_whatsapp = wb.create_sheet('WhatsApp')
                
                # Filtrar por fecha
                queryset = WhatsappLog.objects.all()
                if inicio:
                    queryset = queryset.filter(fecha__gte=inicio)
                if fin:
                    queryset = queryset.filter(fecha__lte=fin)
                queryset = queryset.order_by('-fecha')
                
                # Encabezados
                headers = ['ID', 'Teléfono', 'Tipo', 'Estado', 'Mensaje', 'Fecha', 'ID Mensaje']
                ws_whatsapp.append(headers)
                
                # Aplicar estilos a encabezados
                for cell in ws_whatsapp[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                
                # Datos
                for log in queryset:
                    fecha_str = log.fecha.strftime('%Y-%m-%d %H:%M:%S') if log.fecha else ''
                    tipo = '📥 Entrante' if log.estado == 'INCOMING' else '📤 Saliente'
                    row = [
                        log.id,
                        log.telefono,
                        tipo,
                        log.estado,
                        log.mensaje or '',
                        fecha_str,
                        log.mensaje_id or ''
                    ]
                    ws_whatsapp.append(row)
                
                # Ajustar ancho de columnas
                ws_whatsapp.column_dimensions['A'].width = 8
                ws_whatsapp.column_dimensions['B'].width = 15
                ws_whatsapp.column_dimensions['C'].width = 15
                ws_whatsapp.column_dimensions['D'].width = 12
                ws_whatsapp.column_dimensions['E'].width = 50
                ws_whatsapp.column_dimensions['F'].width = 20
                ws_whatsapp.column_dimensions['G'].width = 25
            
            # Generar respuesta
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            response['Content-Disposition'] = f'attachment; filename="Reporte_Eki_{fecha_str}.xlsx"'
            wb.save(response)
            return response
        
        except Exception as e:
            context['error'] = f"Error al generar reporte: {str(e)}"
    
    # GET: mostrar formulario
    # Calcular primer día del mes actual y último día
    hoy = datetime.now()
    primer_dia_mes = hoy.replace(day=1)
    if hoy.month == 12:
        ultimo_dia_mes = primer_dia_mes.replace(year=hoy.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        ultimo_dia_mes = primer_dia_mes.replace(month=hoy.month + 1, day=1) - timedelta(days=1)
    
    context['fecha_inicio_default'] = primer_dia_mes.strftime('%Y-%m-%d')
    context['fecha_fin_default'] = ultimo_dia_mes.strftime('%Y-%m-%d')
    
    return render(request, 'admin/descargar_reportes.html', context)


# ---------- Webhook para WhatsApp Cloud API ----------
@csrf_exempt
@csrf_exempt
def whatsapp_webhook(request):
    """
    Webhook universal para WhatsApp (Meta + Twilio)
    GET: Verificación del token
    POST: Procesa mensajes entrantes de ambos proveedores
    """
    if request.method == 'GET':
        # Verificación para Meta WhatsApp
        verify_token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        expected = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'eki_whatsapp_verify_token_2025')
        if verify_token and expected and verify_token == expected:
            return HttpResponse(challenge)
        return HttpResponse('Forbidden', status=403)

    if request.method == 'POST':
        print("🔵 WEBHOOK RECIBIÓ POST")
        
        try:
            # Intentar parsear como JSON (Meta)
            payload = json.loads(request.body.decode('utf-8'))
            print(f"🔵 Payload (JSON): {payload}")
            
            # Detectar si es Meta o Twilio
            if 'entry' in payload:
                # ===== META WHATSAPP =====
                print("📍 Detectado: META WhatsApp")
                procesar_meta_webhook(payload)
            else:
                # Podría ser Twilio con JSON
                print("⚠️ JSON recibido pero no es Meta")
                return JsonResponse({'ok': True})
                
        except json.JSONDecodeError:
            # Podría ser Twilio (form-data)
            print("🔵 Payload (Form-Data) - Probablemente Twilio")
            procesar_twilio_webhook(request.POST)
        
        except Exception as e:
            print(f"❌ Error en webhook: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)

        return JsonResponse({'ok': True})


def _procesar_twilio_webhook(post_data):
    """Procesa webhooks de Twilio WhatsApp"""
    try:
        print("🔵 TWILIO: Procesando...")
        
        # Twilio envía datos en formato form-data
        msg_body = post_data.get('Body', '')
        msg_from = post_data.get('From', '')  # whatsapp:+573001234567
        msg_to = post_data.get('To', '')      # whatsapp:+14155238886
        msg_sid = post_data.get('MessageSid', f'twilio_{timezone.now().timestamp()}')
        
        # Limpiar número
        if msg_from.startswith('whatsapp:'):
            msg_from = msg_from.replace('whatsapp:', '')
        
        print(f"📱 De: {msg_from} | Mensaje: {msg_body}")
        
        # Buscar o crear estudiante
        telefono_limpio = msg_from.replace('+', '').replace(' ', '')
        estudiante = None
        try:
            estudiante = Estudiante.objects.get(telefono=telefono_limpio)
            print(f"✅ Estudiante encontrado: {estudiante.nombre}")
        except Estudiante.DoesNotExist:
            print(f"⚠️ Estudiante no encontrado para {telefono_limpio}")
        
        # 1. Guardar mensaje entrante
        WhatsappLog.objects.create(
            telefono=msg_from,
            mensaje=msg_body,
            mensaje_id=msg_sid,
            tipo='INCOMING',
            estudiante=estudiante  # ✅ Asignar estudiante
        )
        print(f"✅ Guardado INCOMING")
        
        # 2. Generar respuesta con IA
        try:
            from .ai_assistant import responder_con_ia
            texto_respuesta = responder_con_ia(msg_body, msg_from)
            print(f"✅ IA generó respuesta: {texto_respuesta[:50]}...")
        except Exception as e:
            print(f"❌ Error IA: {e}, usando respuesta genérica")
            texto_respuesta = "Hola! Gracias por tu mensaje. Estoy aquí para ayudarte."
        
        # 3. Enviar respuesta via Twilio
        try:
            from twilio.rest import Client
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            twilio_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
            
            if not account_sid or not auth_token:
                print("❌ Credenciales Twilio faltantes")
                return
            
            client = Client(account_sid, auth_token)
            
            # Asegurar formato whatsapp:
            destino_formateado = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
            
            mensaje = client.messages.create(
                body=texto_respuesta,
                from_=twilio_number,
                to=destino_formateado
            )
            
            print(f"✅ Mensaje enviado via Twilio: {mensaje.sid}")
            
            # Guardar log de respuesta
            WhatsappLog.objects.create(
                telefono=msg_from,
                mensaje=texto_respuesta,
                mensaje_id=mensaje.sid,
                tipo='SENT',
                estudiante=estudiante  # ✅ Asignar estudiante
            )
            print(f"✅ Guardado SENT")
            
        except Exception as e:
            print(f"❌ Error enviando respuesta Twilio: {str(e)}")
            import traceback
            traceback.print_exc()
    
    except Exception as e:
        print(f"❌ Error en _procesar_twilio_webhook: {str(e)}")
        import traceback
        traceback.print_exc()


def _procesar_meta_webhook(payload):
    """Procesa webhooks de Meta WhatsApp (mantiene compatibilidad)"""
    try:
        print("🔵 META: Procesando...")
        entries = payload.get('entry', [])
        
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
                    
                    # Buscar estudiante
                    telefono_limpio = phone.replace('+', '').replace(' ', '')
                    estudiante = None
                    try:
                        estudiante = Estudiante.objects.get(telefono=telefono_limpio)
                        print(f"✅ Estudiante encontrado: {estudiante.nombre}")
                    except Estudiante.DoesNotExist:
                        print(f"⚠️ Estudiante no encontrado para {telefono_limpio}")
                    
                    # Guardar mensaje
                    WhatsappLog.objects.create(
                        telefono=phone,
                        mensaje=text,
                        mensaje_id=msg_id,
                        tipo='INCOMING',
                        estudiante=estudiante  # ✅ Asignar estudiante
                    )
                    
                    # Generar respuesta
                    try:
                        from .ai_assistant import responder_con_ia
                        texto_respuesta = responder_con_ia(text, phone)
                    except Exception as e:
                        print(f"Error IA: {e}")
                        intent = detect_intent(text)
                        texto_respuesta = get_response_for_intent(intent, 'Usuario')
                    
                    # Enviar respuesta
                    resultado_envio = enviar_whatsapp(phone, texto_respuesta)
                    
                    if resultado_envio.get('success'):
                        WhatsappLog.objects.create(
                            telefono=phone,
                            mensaje=texto_respuesta,
                            mensaje_id=resultado_envio.get('mensaje_id'),
                            tipo='SENT',
                            estudiante=estudiante  # ✅ Asignar estudiante
                        )
    
    except Exception as e:
        print(f"❌ Error en _procesar_meta_webhook: {str(e)}")
        import traceback
        traceback.print_exc()


@staff_member_required
def probar_twilio_view(request):
    """Vista para probar integración con Twilio WhatsApp"""
    context = {
        'mensaje': None,
        'error': False,
        'resultado': None
    }
    
    if request.method == 'POST':
        try:
            from twilio.rest import Client
            import os
            
            # Obtener datos del formulario
            tipo_mensaje = request.POST.get('tipo_mensaje')
            usar_template = request.POST.get('usar_template') == 'on'
            telefono = request.POST.get('telefono', '').strip()
            mensaje_texto = request.POST.get('mensaje', '').strip()
            url_imagen = request.POST.get('url_imagen', '').strip()
            
            # Validar credenciales
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            template_sid = os.environ.get('TWILIO_TEMPLATE_SID')
            
            if not account_sid or not auth_token:
                context['mensaje'] = '<strong>❌ Error:</strong> Las credenciales de Twilio no están configuradas en el archivo .env'
                context['error'] = True
                return render(request, 'admin/probar_twilio.html', context)
            
            # Validar teléfono
            if not telefono:
                context['mensaje'] = '<strong>❌ Error:</strong> Debes proporcionar un número de teléfono'
                context['error'] = True
                return render(request, 'admin/probar_twilio.html', context)
            
            # Asegurar formato whatsapp:
            if not telefono.startswith('+'):
                telefono = f'+{telefono}'
            if not telefono.startswith('whatsapp:'):
                telefono_whatsapp = f'whatsapp:{telefono}'
            else:
                telefono_whatsapp = telefono
            
            # Crear cliente Twilio
            client = Client(account_sid, auth_token)
            
            # Si se usa template aprobado
            if usar_template and template_sid:
                message = client.messages.create(
                    content_sid=template_sid,
                    from_="whatsapp:+14155238886",
                    to=telefono_whatsapp
                )
            else:
                # Preparar parámetros del mensaje libre
                params = {
                    "to": telefono_whatsapp,
                    "from_": "whatsapp:+14155238886",  # Sandbox number
                    "body": mensaje_texto
                }
                
                # Si es mensaje con imagen, agregar media_url
                if tipo_mensaje == 'imagen' and url_imagen:
                    params["media_url"] = [url_imagen]
                
                # Enviar mensaje
                message = client.messages.create(**params)
            
            # Crear resultado formateado
            resultado_texto = f"""
✅ MENSAJE ENVIADO EXITOSAMENTE

📝 SID: {message.sid}
📊 Estado: {message.status}
📅 Fecha: {message.date_created}
📱 Destino: {telefono}
"""
            
            if usar_template and template_sid:
                resultado_texto += f"📋 Template SID: {template_sid}\n"
            else:
                resultado_texto += f"💬 Mensaje: {mensaje_texto[:100]}{'...' if len(mensaje_texto) > 100 else ''}\n"
                if tipo_mensaje == 'imagen' and url_imagen:
                    resultado_texto += f"🖼️  Imagen: {url_imagen}\n"
            
            context['mensaje'] = f'<strong>✅ ¡Éxito!</strong> El mensaje fue enviado correctamente. SID: {message.sid}'
            context['error'] = False
            context['resultado'] = resultado_texto
            
            # Guardar log
            WhatsappLog.objects.create(
                telefono=telefono.replace('whatsapp:', '').replace('+', ''),
                mensaje=mensaje_texto,
                mensaje_id=message.sid,
                estado='SENT'
            )
            
        except Exception as e:
            context['mensaje'] = f'<strong>❌ Error al enviar:</strong> {str(e)}'
            context['error'] = True
            context['resultado'] = f"ERROR:\n{str(e)}"
    
    return render(request, 'admin/probar_twilio.html', context)


@staff_member_required
def calendario_campanas_view(request):
    """Vista de calendario de campañas programadas"""
    from django.utils import timezone
    
    ahora = timezone.now()
    
    # Campañas pendientes (programadas pero no ejecutadas)
    campanas_pendientes = Campana.objects.filter(
        fecha_programada__isnull=False,
        ejecutada=False
    ).order_by('fecha_programada')
    
    # Campañas ejecutadas que tenían programación
    campanas_ejecutadas = Campana.objects.filter(
        fecha_programada__isnull=False,
        ejecutada=True
    ).order_by('-fecha_programada')[:10]
    
    context = {
        'campanas_pendientes': campanas_pendientes,
        'campanas_ejecutadas': campanas_ejecutadas,
    }
    
    return render(request, 'admin/calendario_campanas.html', context)


@staff_member_required
def conversaciones_view(request):
    """Vista de conversaciones estilo WhatsApp"""
    print("🔍 DEBUG: Iniciando conversaciones_view")
    
    # Obtener todos los estudiantes que tienen mensajes
    estudiantes_con_mensajes = []
    
    # PRIMERO: Obtener todos los WhatsappLog con estudiante asignado
    whatsapp_con_estudiante = WhatsappLog.objects.filter(estudiante__isnull=False).select_related('estudiante')
    estudiantes_ids_whatsapp = set(whatsapp_con_estudiante.values_list('estudiante_id', flat=True))
    
    print(f"📊 DEBUG: {whatsapp_con_estudiante.count()} mensajes WhatsApp con estudiante asignado")
    print(f"📊 DEBUG: {len(estudiantes_ids_whatsapp)} estudiantes únicos con mensajes WhatsApp")
    
    # SEGUNDO: Obtener estudiantes con EnvioLog
    envios_log = EnvioLog.objects.filter(estudiante__isnull=False).select_related('estudiante')
    estudiantes_ids_envios = set(envios_log.values_list('estudiante_id', flat=True))
    
    print(f"📊 DEBUG: {envios_log.count()} mensajes de campañas enviadas")
    print(f"📊 DEBUG: {len(estudiantes_ids_envios)} estudiantes únicos con envíos")
    
    # Combinar ambos sets
    todos_ids = estudiantes_ids_whatsapp | estudiantes_ids_envios
    
    print(f"📊 DEBUG: {len(todos_ids)} estudiantes TOTALES con conversaciones")
    
    # Obtener objetos Estudiante
    if todos_ids:
        estudiantes = Estudiante.objects.filter(id__in=todos_ids)
    else:
        estudiantes = Estudiante.objects.none()
    
    for est in estudiantes:
        try:
            # Obtener último mensaje de WhatsApp
            ultimo_whatsapp = WhatsappLog.objects.filter(estudiante=est).order_by('-fecha').first()
            
            # Obtener último envío
            ultimo_envio = EnvioLog.objects.filter(estudiante=est).order_by('-fecha_envio').first()
            
            # Determinar cuál es más reciente
            ultima_fecha = None
            ultimo_mensaje = None
            total_mensajes = 0
            
            if ultimo_whatsapp and ultimo_envio:
                # Convertir ambas fechas a aware si es necesario
                fecha_whatsapp = ultimo_whatsapp.fecha
                fecha_envio = ultimo_envio.fecha_envio
                
                # Asegurar que ambas son timezone-aware
                if timezone.is_naive(fecha_whatsapp):
                    fecha_whatsapp = timezone.make_aware(fecha_whatsapp)
                if timezone.is_naive(fecha_envio):
                    fecha_envio = timezone.make_aware(fecha_envio)
                
                if fecha_whatsapp > fecha_envio:
                    ultima_fecha = fecha_whatsapp
                    ultimo_mensaje = ultimo_whatsapp.mensaje[:50]
                else:
                    ultima_fecha = fecha_envio
                    ultimo_mensaje = f"📤 Campaña: {ultimo_envio.campana.nombre if ultimo_envio.campana else 'Sin nombre'}"
                
                total_mensajes = WhatsappLog.objects.filter(estudiante=est).count() + EnvioLog.objects.filter(estudiante=est).count()
                
            elif ultimo_whatsapp:
                ultima_fecha = ultimo_whatsapp.fecha
                if timezone.is_naive(ultima_fecha):
                    ultima_fecha = timezone.make_aware(ultima_fecha)
                ultimo_mensaje = ultimo_whatsapp.mensaje[:50]
                total_mensajes = WhatsappLog.objects.filter(estudiante=est).count()
                
            elif ultimo_envio:
                ultima_fecha = ultimo_envio.fecha_envio
                if timezone.is_naive(ultima_fecha):
                    ultima_fecha = timezone.make_aware(ultima_fecha)
                ultimo_mensaje = f"📤 Campaña: {ultimo_envio.campana.nombre if ultimo_envio.campana else 'Sin nombre'}"
                total_mensajes = EnvioLog.objects.filter(estudiante=est).count()
            
            if ultima_fecha:
                est.ultima_fecha = ultima_fecha
                est.ultimo_mensaje = ultimo_mensaje
                est.total_mensajes = total_mensajes
                estudiantes_con_mensajes.append(est)
                
        except Exception as e:
            print(f"❌ ERROR procesando estudiante {est.id}: {str(e)}")
            continue
    
    # Ordenar por fecha más reciente
    estudiantes_con_mensajes.sort(
        key=lambda x: x.ultima_fecha if hasattr(x, 'ultima_fecha') and x.ultima_fecha else timezone.now() - timedelta(days=365*10), 
        reverse=True
    )
    
    print(f"✅ DEBUG: {len(estudiantes_con_mensajes)} estudiantes procesados para mostrar")
    
    # Estudiante seleccionado
    estudiante_id = request.GET.get('estudiante')
    estudiante_seleccionado = None
    mensajes = []
    page_obj = None
    
    if estudiante_id:
        try:
            estudiante_seleccionado = Estudiante.objects.get(id=estudiante_id)
            print(f"👤 DEBUG: Cargando mensajes para {estudiante_seleccionado.nombre}")
            
            # Crear lista unificada de mensajes
            lista_mensajes = []
            
            # WhatsApp logs (usar estudiante FK en lugar de teléfono)
            whatsapp_msgs = WhatsappLog.objects.filter(estudiante=estudiante_seleccionado).order_by('fecha')
            print(f"💬 DEBUG: {whatsapp_msgs.count()} mensajes WhatsApp encontrados")
            
            for msg in whatsapp_msgs:
                fecha = msg.fecha
                if timezone.is_naive(fecha):
                    fecha = timezone.make_aware(fecha)
                    
                lista_mensajes.append({
                    'mensaje': msg.mensaje,
                    'fecha': fecha,
                    'estado': msg.estado,
                    'tipo': 'recibido' if msg.tipo == 'INCOMING' else 'enviado'  # ✅ Usar campo 'tipo' en lugar de 'estado'
                })
            
            # Envio logs (mensajes enviados por campañas)
            envios = EnvioLog.objects.filter(estudiante=estudiante_seleccionado).select_related('campana', 'campana__plantilla').order_by('fecha_envio')
            print(f"📤 DEBUG: {envios.count()} mensajes de campañas encontrados")
            
            for envio in envios:
                fecha = envio.fecha_envio
                if timezone.is_naive(fecha):
                    fecha = timezone.make_aware(fecha)
                
                # Obtener el mensaje de la plantilla
                if envio.campana and envio.campana.plantilla:
                    mensaje_campana = envio.campana.plantilla.cuerpo_mensaje
                    # Personalizar con el nombre del estudiante
                    mensaje_personalizado = mensaje_campana.replace('{nombre}', estudiante_seleccionado.nombre)
                else:
                    mensaje_personalizado = f"Campaña: {envio.campana.nombre if envio.campana else 'Sin nombre'}"
                    
                lista_mensajes.append({
                    'mensaje': mensaje_personalizado,
                    'fecha': fecha,
                    'estado': envio.estado,
                    'tipo': 'enviado'
                })
            
            # Ordenar por fecha
            lista_mensajes.sort(key=lambda x: x['fecha'] if x['fecha'] else timezone.now() - timedelta(days=365*10))
            
            print(f"✅ DEBUG: {len(lista_mensajes)} mensajes totales unificados")
            
            # Paginación
            paginator = Paginator(lista_mensajes, 50)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
            mensajes = page_obj.object_list
            
        except Estudiante.DoesNotExist:
            print(f"❌ ERROR: Estudiante {estudiante_id} no existe")
        except Exception as e:
            print(f"❌ ERROR cargando mensajes: {str(e)}")
            import traceback
            traceback.print_exc()
    
    context = {
        'estudiantes': estudiantes_con_mensajes[:50],  # Limitar a 50 contactos
        'estudiante_seleccionado': estudiante_seleccionado,
        'mensajes': mensajes,
        'page_obj': page_obj,
        'total_conversaciones': len(estudiantes_con_mensajes),
    }
    
    print(f"🎯 DEBUG: Renderizando template con {len(context['estudiantes'])} estudiantes")
    
    return render(request, 'admin/conversaciones.html', context)


@staff_member_required
def chat_prueba_view(request):
    """Vista para probar la IA sin necesidad de WhatsApp/ngrok"""
    return render(request, 'admin/chat_prueba.html')


@staff_member_required
def chat_prueba_api(request):
    """API para el chat de prueba"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mensaje = data.get('mensaje', '')
            telefono = data.get('telefono', 'test_chat')
            
            print(f"🔵 Chat de prueba - Mensaje: {mensaje}")
            
            # Guardar mensaje entrante
            WhatsappLog.objects.create(
                telefono=telefono,
                mensaje=mensaje,
                mensaje_id=f"test_{timezone.now().timestamp()}",
                tipo='INCOMING'
            )
            
            # Obtener respuesta de la IA
            try:
                from .ai_assistant import responder_con_ia
                respuesta = responder_con_ia(mensaje, telefono)
                print(f"✅ IA respondió: {respuesta}")
            except Exception as e:
                print(f"❌ Error en IA: {e}")
                # Fallback
                from .intent_detector import detect_intent
                from .response_templates import get_response_for_intent
                intent = detect_intent(mensaje)
                respuesta = get_response_for_intent(intent, 'Usuario')
            
            # Guardar respuesta
            WhatsappLog.objects.create(
                telefono=telefono,
                mensaje=respuesta,
                mensaje_id=f"test_response_{timezone.now().timestamp()}",
                tipo='SENT'
            )
            
            return JsonResponse({
                'success': True,
                'respuesta': respuesta
            })
            
        except Exception as e:
            print(f"❌ Error en chat de prueba: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@staff_member_required
def ranking_gamificacion_view(request):
    """Vista del ranking de gamificación"""
    from .models import PerfilGamificacion, Badge, BadgeEstudiante
    from django.db.models import Count, Max, Sum
    
    # Obtener top 20 del ranking
    ranking = PerfilGamificacion.objects.select_related('estudiante').prefetch_related(
        'estudiante__badges_obtenidos__badge'
    ).order_by('-puntos_totales')[:20]
    
    # Agregar emoji de nivel a cada perfil
    emojis = ['🌱', '🌿', '🍃', '🌾', '🌳', '🌲', '🎋', '🌺', '💎', '👑']
    for perfil in ranking:
        perfil.emoji = emojis[perfil.nivel - 1] if perfil.nivel <= 10 else '🏆'
        perfil.total_badges = perfil.get_badges().count()
    
    # Estadísticas generales
    stats = {
        'total_estudiantes': PerfilGamificacion.objects.count(),
        'puntos_totales': PerfilGamificacion.objects.aggregate(Sum('puntos_totales'))['puntos_totales__sum'] or 0,
        'badges_obtenidos': BadgeEstudiante.objects.count(),
        'racha_maxima': PerfilGamificacion.objects.aggregate(
            Max('racha_dias_maxima')
        )['racha_dias_maxima__max'] or 0,
    }
    
    # Todos los badges con contador de cuántos lo tienen
    all_badges = Badge.objects.annotate(
        total=Count('estudiantes')
    ).order_by('-total', 'nombre')
    
    context = {
        'ranking': ranking,
        'stats': stats,
        'all_badges': all_badges,
    }
    
    return render(request, 'admin/ranking_gamificacion.html', context)

