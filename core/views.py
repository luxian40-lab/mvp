from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse, FileResponse
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, Max, Count
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from django.utils import timezone
import requests
import tempfile
import os
import logging

# Logger para debugging
logger = logging.getLogger(__name__)

from .models import Campana, Estudiante, WhatsappLog, EnvioLog
from .models_extras import ArchivoModulo
from .utils import enviar_whatsapp
from .intent_detector import detect_intent
from .response_templates import get_response_for_intent


def _transcribir_audio_twilio(media_url):
    """
    Transcribe un audio de Twilio usando VOSK (GRATUITO, OFFLINE).
    
    VOSK: Modelo de reconocimiento de voz offline completamente gratuito.
    - Costo: $0 (sin límites)
    - Velocidad: Muy rápida (local)
    - Idioma: Español colombiano
    
    Alternativa: OpenAI Whisper ($0.006/min) si VOSK no está disponible.
    
    Args:
        media_url: URL del audio en Twilio
    
    Returns:
        str: Texto transcrito
    """
    try:
        # Obtener credenciales de Twilio para descargar el audio
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        
        # Descargar el audio
        response = requests.get(media_url, auth=(account_sid, auth_token))
        response.raise_for_status()
        
        audio_size = len(response.content)
        print(f"🎤 Transcribiendo audio ({audio_size} bytes)...")
        
        # Guardar temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp_file:
            tmp_file.write(response.content)
            audio_path = tmp_file.name
        
        try:
            # OPCIÓN 1: VOSK (GRATUITO - PRIORIDAD)
            try:
                texto = _transcribir_con_vosk(audio_path)
                if texto and texto != "listo":
                    print(f"✅ Vosk transcribió: '{texto}'")
                    return texto
            except Exception as vosk_error:
                print(f"⚠️ Vosk no disponible: {vosk_error}")
            
            # OPCIÓN 2: WHISPER (FALLBACK PAGADO)
            openai_api_key = getattr(settings, 'OPENAI_API_KEY', '')
            if openai_api_key and audio_size < 500000:  # Solo audios cortos
                print("🔄 Usando Whisper como fallback...")
                from openai import OpenAI
                client = OpenAI(api_key=openai_api_key)
                
                with open(audio_path, 'rb') as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="es",
                        prompt="Listo, continuar, menú, cursos, progreso, ayuda"
                    )
                
                texto = transcription.text.strip()
                print(f"✅ Whisper transcribió: '{texto}'")
                return texto if texto else "listo"
            
            # OPCIÓN 3: FALLBACK INTELIGENTE
            print("⚠️ Sin transcripción disponible - usando fallback")
            return "listo"
            
        finally:
            # Eliminar archivo temporal
            if os.path.exists(audio_path):
                os.remove(audio_path)
    
    except Exception as e:
        print(f"❌ Error en transcripción: {e}")
        return "listo"


def _transcribir_con_vosk(audio_path):
    """
    Transcribe audio usando VOSK (gratuito, offline).
    
    Instalación requerida:
    - pip install vosk
    - Descargar modelo: https://alphacephei.com/vosk/models
    - Colocar en: models/vosk-model-small-es-0.42/
    """
    try:
        import json
        from vosk import Model, KaldiRecognizer
        from pydub import AudioSegment
        import wave
        
        # Ruta al modelo de Vosk (configurar en settings)
        model_path = getattr(settings, 'VOSK_MODEL_PATH', 'models/vosk-model-small-es-0.42')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo Vosk no encontrado en {model_path}")
        
        # Cargar modelo (se cachea automáticamente)
        model = Model(model_path)
        
        # Convertir audio a formato WAV 16kHz mono (requerido por Vosk)
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        
        # Guardar como WAV temporal
        wav_path = audio_path.replace('.ogg', '_vosk.wav').replace('.mp3', '_vosk.wav')
        audio.export(wav_path, format='wav')
        
        # Transcribir usando wave module (más confiable)
        recognizer = KaldiRecognizer(model, 16000)
        
        wf = wave.open(wav_path, "rb")
        
        # Procesar por chunks
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            recognizer.AcceptWaveform(data)
        
        wf.close()
        
        # Obtener resultado final
        result = json.loads(recognizer.FinalResult())
        texto = result.get('text', '').strip()
        
        print(f"✅ Vosk transcribió: '{texto}'")
        
        # Limpiar archivo WAV temporal
        if os.path.exists(wav_path):
            os.remove(wav_path)
        
        return texto if texto else "listo"
        
    except Exception as e:
        print(f"❌ Error Vosk: {e}")
        raise  # Re-lanzar para que el fallback funcione


@staff_member_required
def dashboard_view(request):
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    
    # Filtro por cliente (opcional)
    cliente_id = request.GET.get('cliente')
    cliente_seleccionado = None
    
    if cliente_id:
        try:
            cliente_seleccionado = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            pass
    
    # Filtrar estudiantes por cliente si está seleccionado
    estudiantes_query = Estudiante.objects.filter(activo=True)
    if cliente_seleccionado:
        estudiantes_query = estudiantes_query.filter(cliente=cliente_seleccionado)
    
    # 1. Calcular Métricas REALES (solo WhatsappLog)
    total_campanas = Campana.objects.count()
    if cliente_seleccionado:
        total_campanas = Campana.objects.filter(cliente=cliente_seleccionado).count()
    
    estudiantes_activos = estudiantes_query.count()
    
    # Obtener teléfonos de estudiantes del cliente
    telefonos_cliente = []
    if cliente_seleccionado:
        telefonos_cliente = [est.telefono.replace('+', '').replace(' ', '') for est in estudiantes_query]
    
    # Métricas de WhatsApp (DATOS REALES) - filtradas por cliente
    whatsapp_logs_query = WhatsappLog.objects.all()
    if cliente_seleccionado and telefonos_cliente:
        whatsapp_logs_query = whatsapp_logs_query.filter(telefono__in=telefonos_cliente)
    
    whatsapp_logs = whatsapp_logs_query.order_by('-fecha')[:10]
    whatsapp_total = whatsapp_logs_query.count()
    whatsapp_enviados = whatsapp_logs_query.filter(tipo='SENT').count()
    whatsapp_recibidos = whatsapp_logs_query.filter(tipo='INCOMING').count()
    
    # Conversaciones únicas (estudiantes que han conversado)
    conversaciones_activas = whatsapp_logs_query.values('telefono').distinct().count()
    
    # Datos para gráficos - Últimos 7 días
    hoy = datetime.now().date()
    hace_7_dias = hoy - timedelta(days=7)
    
    # Mensajes por día (últimos 7 días)
    mensajes_por_dia = whatsapp_logs_query.filter(
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
    mensajes_enviados_30d = whatsapp_logs_query.filter(
        fecha__gte=hace_30_dias,
        tipo='SENT'
    ).count()
    mensajes_recibidos_30d = whatsapp_logs_query.filter(
        fecha__gte=hace_30_dias,
        tipo='INCOMING'
    ).count()
    
    # Obtener todos los clientes para el selector
    todos_clientes = Cliente.objects.all().order_by('nombre')

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
        
        # Selector de cliente
        'todos_clientes': todos_clientes,
        'cliente_seleccionado': cliente_seleccionado,
        
        # Timestamp para auto-refresh
        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
    }
    
    return render(request, 'admin/dashboard_metrics.html', context)


# ---------- Vista de instrucciones ----------
@staff_member_required
def instrucciones_view(request):
    """Vista para mostrar el instructivo completo de Eki."""
    return render(request, 'admin/instrucciones.html')


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
                _procesar_meta_webhook(payload)
            else:
                # Podría ser Twilio con JSON
                print("⚠️ JSON recibido pero no es Meta")
                return JsonResponse({'ok': True})
                
        except json.JSONDecodeError:
            # Podría ser Twilio (form-data)
            print("🔵 Payload (Form-Data) - Probablemente Twilio")
            _procesar_twilio_webhook(request.POST)
        
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
        
        # 🎤 DETECTAR AUDIO: Twilio envía audios como MediaUrl
        num_media = int(post_data.get('NumMedia', 0))
        if num_media > 0 and not msg_body:
            # Usuario envió audio sin texto
            media_url = post_data.get('MediaUrl0', '')
            media_type = post_data.get('MediaContentType0', '')
            
            if 'audio' in media_type:
                print(f"🎤 Audio recibido: {media_url}")
                # Transcribir audio con OpenAI Whisper
                try:
                    msg_body = _transcribir_audio_twilio(media_url)
                    print(f"✅ Audio transcrito: {msg_body}")
                except Exception as e:
                    print(f"❌ Error transcribiendo audio: {e}")
                    msg_body = "listo"  # Fallback común para continuar lección
        
        # Limpiar número (quitar whatsapp: y normalizar igual que el modelo)
        if msg_from.startswith('whatsapp:'):
            msg_from = msg_from.replace('whatsapp:', '')
        
        # Normalizar teléfono igual que el modelo (sin +, sin espacios, sin guiones)
        import re
        telefono_limpio = re.sub(r'\D', '', msg_from)  # Solo dígitos
        if len(telefono_limpio) == 10:
            telefono_limpio = f"57{telefono_limpio}"
        
        print(f"📱 De: {msg_from} → Limpio: {telefono_limpio} | Mensaje: {msg_body}")
        
        # 1. Guardar mensaje entrante con teléfono limpio
        WhatsappLog.objects.create(
            telefono=telefono_limpio,
            mensaje=msg_body,
            mensaje_id=msg_sid,
            tipo='INCOMING'
        )
        print(f"✅ Guardado INCOMING")
        
        # 2. Buscar estudiante con teléfono limpio
        try:
            estudiante = Estudiante.objects.get(telefono=telefono_limpio)
            print(f"✅ Estudiante encontrado: {estudiante.nombre} (ID: {estudiante.id})")
        except Estudiante.DoesNotExist:
            # Si no existe, ir directo a habeas data (se creará en security_handler)
            print(f"⚠️ Estudiante nuevo: {telefono_limpio} - Iniciará habeas data")
            estudiante = None
        
        # 3. 🛡️ PRIORIDAD 1: Verificar seguridad (Habeas Data)
        from .security_handler import verificar_seguridad_completa
        bloqueado, respuesta_seguridad, estudiante = verificar_seguridad_completa(estudiante, msg_body, telefono_limpio)
        
        if bloqueado:
            print(f"🛡️ Bloqueado por seguridad/habeas data")
            texto_respuesta = respuesta_seguridad
        else:
            # 3.5 PRIORIDAD: Si está respondiendo pregunta de módulo
            if estudiante.estado_onboarding == 'esperando_respuesta_modulo':
                from .pregunta_handler import validar_respuesta
                print(f"📝 Validando respuesta a pregunta de módulo")
                
                es_correcta, mensaje_respuesta, modulo_completado = validar_respuesta(estudiante, msg_body)
                
                # Obtener progreso para avanzar al siguiente módulo
                if modulo_completado:
                    from .helpers_examenes import puede_avanzar_modulo
                    
                    progreso = modulo_completado.progreso
                    modulo_actual = modulo_completado.modulo
                    
                    # ⚠️ VERIFICAR EXAMEN OBLIGATORIO ANTES DE AVANZAR
                    puede_avanzar, mensaje_examen, detalles = puede_avanzar_modulo(estudiante, modulo_actual)
                    
                    if not puede_avanzar:
                        # NO puede avanzar - examen obligatorio no aprobado
                        mensaje_respuesta += f"""

━━━━━━━━━━━━━━━━━━━━

🔒 *Examen Obligatorio*

{mensaje_examen}

Para continuar al siguiente módulo debes aprobar el examen de este módulo.

Escribe *"examen"* cuando estés listo para intentarlo."""
                        
                        WhatsappLog.objects.create(
                            telefono=from_number,
                            mensaje=mensaje_respuesta,
                            mensaje_id=f"response_{timezone.now().timestamp()}",
                            tipo='SENT'
                        )
                        return HttpResponse(f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{mensaje_respuesta}</Message></Response>', content_type='text/xml')
                    
                    # Buscar siguiente módulo
                    siguiente_modulo = progreso.curso.modulos.filter(
                        numero__gt=modulo_actual.numero
                    ).order_by('numero').first()
                    
                    if siguiente_modulo:
                        # Actualizar progreso al siguiente módulo
                        progreso.modulo_actual = siguiente_modulo
                        progreso.save()
                        
                        porcentaje = progreso.porcentaje_avance()
                        from .response_templates import obtener_video_url
                        video_url = obtener_video_url(siguiente_modulo)
                        
                        # Verificar si tiene archivos multimedia
                        archivos_multimedia = siguiente_modulo.archivos_multimedia.filter(activo=True)
                        archivos_msg = ""
                        if archivos_multimedia.exists():
                            archivos_msg = f"\n\n📁 *{archivos_multimedia.count()} archivo(s) multimedia disponibles*"
                            for archivo in archivos_multimedia[:3]:  # Máximo 3
                                icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                archivos_msg += f"\n{icono} {archivo.titulo}"
                        
                        mensaje_respuesta += f"""

━━━━━━━━━━━━━━━━━━━━

Progreso del curso: {porcentaje}%

📖 *Módulo {siguiente_modulo.numero}: {siguiente_modulo.titulo}*

{siguiente_modulo.descripcion}

{siguiente_modulo.contenido}{archivos_msg}

━━━━━━━━━━━━━━━━━━━━

Cuando termines, escribe: *"listo"*"""
                        
                        if video_url:
                            mensaje_respuesta += f"\n\n🎥 Video educativo:\n{video_url}"
                        
                        # Mostrar si el siguiente módulo tiene examen obligatorio
                        if siguiente_modulo.examen_obligatorio:
                            mensaje_respuesta += f"\n\n⚠️ *Este módulo tiene examen obligatorio ({siguiente_modulo.puntaje_minimo_aprobacion}% para aprobar)*"
                    
                    else:
                        # Completó todos los módulos
                        progreso.completado = True
                        progreso.fecha_completado = timezone.now()
                        progreso.save()
                        
                        mensaje_respuesta += f"""

━━━━━━━━━━━━━━━━━━━━

🎓 *¡FELICITACIONES!*

Has completado el curso: *{progreso.curso.nombre}*

🏆 Certificado disponible en tu perfil

*¿Qué deseas hacer ahora?*

1️⃣ Ver otros cursos
2️⃣ Ver mi progreso
3️⃣ Menú principal"""
                
                texto_respuesta = mensaje_respuesta
                print(f"✅ Respuesta validada: {'Correcta' if es_correcta else 'Incorrecta'}")
                
                # IMPORTANTE: Enviar respuesta inmediatamente después de validar
                # (tanto si es correcta como incorrecta)
                WhatsappLog.objects.create(
                    telefono=from_number,
                    mensaje=texto_respuesta,
                    mensaje_id=f"response_{timezone.now().timestamp()}",
                    tipo='SENT',
                    estudiante=estudiante
                )
                return HttpResponse(
                    f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{texto_respuesta}</Message></Response>',
                    content_type='text/xml'
                )
            
            # 4. Detectar intent y usar templates primero
            else:
                from .intent_detector import detect_intent
                from .response_templates import get_response_for_intent
                
                intent = detect_intent(msg_body)
                print(f"🎯 Intent detectado: {intent}")
                intent = detect_intent(msg_body)
                print(f"🎯 Intent detectado: {intent}")
            
                # Si hay un intent conocido, usar template
                if intent != 'desconocido':
                    texto_respuesta = get_response_for_intent(
                        intent, 
                        estudiante.nombre,
                        estudiante_id=estudiante.id,
                        mensaje_original=msg_body
                    )
                    print(f"✅ Respuesta desde template: {texto_respuesta[:50]}...")
                else:
                    # Solo si no hay intent, usar IA para preguntas sobre agricultura
                    print(f"🤖 Usando IA para pregunta sobre agricultura")
                    try:
                        from .ai_assistant import responder_con_ia
                        texto_respuesta = responder_con_ia(msg_body, msg_from)
                        print(f"✅ IA generó respuesta: {texto_respuesta[:50]}...")
                    except Exception as e:
                        print(f"❌ Error IA: {e}, usando respuesta genérica")
                        texto_respuesta = "Disculpa, tengo problemas técnicos. Escribe 'menú' para ver las opciones."
        
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
            
            # Usar el teléfono original (con +) para enviar por Twilio
            destino_formateado = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
            
            # Check if response is a multi-message (marked with [MULTI_MSG])
            if texto_respuesta.startswith('[MULTI_MSG]'):
                # Extract and send multiple messages
                partes = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                
                for idx, parte in enumerate(partes):
                    if not parte.strip():
                        continue
                    
                    mensaje = client.messages.create(
                        body=parte.strip(),
                        from_=twilio_number,
                        to=destino_formateado
                    )
                    
                    print(f"✅ Mensaje {idx+1}/{len(partes)} enviado via Twilio: {mensaje.sid}")
                    
                    # Guardar log de respuesta con teléfono limpio
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=parte.strip(),
                        mensaje_id=mensaje.sid,
                        tipo='SENT'
                    )
                    print(f"✅ Guardado SENT")
                    
                    # Small delay between messages to avoid rate limiting
                    import time
                    time.sleep(0.5)
            else:
                # Single message (original behavior)
                mensaje = client.messages.create(
                    body=texto_respuesta,
                    from_=twilio_number,
                    to=destino_formateado
                )
                
                print(f"✅ Mensaje enviado via Twilio: {mensaje.sid}")
                
                # Guardar log de respuesta con teléfono limpio
                WhatsappLog.objects.create(
                    telefono=telefono_limpio,
                    mensaje=texto_respuesta,
                    mensaje_id=mensaje.sid,
                    tipo='SENT'
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
                    
                    # Guardar mensaje
                    WhatsappLog.objects.create(
                        telefono=phone,
                        mensaje=text,
                        mensaje_id=msg_id,
                        tipo='INCOMING'
                    )
                    
                    # Obtener o crear estudiante
                    estudiante, _ = Estudiante.objects.get_or_create(
                        telefono=phone,
                        defaults={'nombre': 'Usuario', 'activo': True}
                    )
                    
                    # Verificar seguridad primero
                    from .security_handler import verificar_seguridad_completa
                    bloqueado, respuesta_seguridad = verificar_seguridad_completa(estudiante, text)
                    
                    if bloqueado:
                        texto_respuesta = respuesta_seguridad
                    else:
                        # Detectar intent
                        intent = detect_intent(text)
                        
                        if intent != 'desconocido':
                            # Usar template
                            texto_respuesta = get_response_for_intent(
                                intent, 
                                estudiante.nombre,
                                estudiante_id=estudiante.id,
                                mensaje_original=text
                            )
                        else:
                            # Usar IA solo para preguntas
                            try:
                                from .ai_assistant import responder_con_ia
                                texto_respuesta = responder_con_ia(text, phone)
                            except Exception as e:
                                print(f"Error IA: {e}")
                                texto_respuesta = "Disculpa, tengo problemas técnicos. Escribe 'menú' para ver las opciones."
                    
                    # Enviar respuesta
                    resultado_envio = enviar_whatsapp(phone, texto_respuesta)
                    
                    if resultado_envio.get('success'):
                        WhatsappLog.objects.create(
                            telefono=phone,
                            mensaje=texto_respuesta,
                            mensaje_id=resultado_envio.get('mensaje_id'),
                            tipo='SENT'
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
    # Obtener todos los estudiantes que tienen mensajes
    estudiantes_con_mensajes = []
    
    # Obtener todos los estudiantes
    todos_estudiantes = Estudiante.objects.all()
    
    for est in todos_estudiantes:
        try:
            telefono_limpio = est.telefono.replace('+', '').replace(' ', '')
            
            # Contar mensajes de WhatsApp
            total_whatsapp = WhatsappLog.objects.filter(telefono=telefono_limpio).count()
            
            # Contar mensajes de envíos
            total_envios = EnvioLog.objects.filter(estudiante=est).count()
            
            if total_whatsapp > 0 or total_envios > 0:
                # Obtener último mensaje
                ultimo_whatsapp = WhatsappLog.objects.filter(telefono=telefono_limpio).order_by('-fecha').first()
                ultimo_envio = EnvioLog.objects.filter(estudiante=est).order_by('-fecha_envio').first()
                
                # Determinar cuál es más reciente
                ultima_fecha = None
                ultimo_mensaje = None
                
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
                        ultimo_mensaje = ultimo_whatsapp.mensaje
                    else:
                        ultima_fecha = fecha_envio
                        ultimo_mensaje = f"Campaña: {ultimo_envio.campana.nombre}"
                elif ultimo_whatsapp:
                    ultima_fecha = ultimo_whatsapp.fecha
                    if timezone.is_naive(ultima_fecha):
                        ultima_fecha = timezone.make_aware(ultima_fecha)
                    ultimo_mensaje = ultimo_whatsapp.mensaje
                elif ultimo_envio:
                    ultima_fecha = ultimo_envio.fecha_envio
                    if timezone.is_naive(ultima_fecha):
                        ultima_fecha = timezone.make_aware(ultima_fecha)
                    ultimo_mensaje = f"Campaña: {ultimo_envio.campana.nombre}"
                
                est.ultima_fecha = ultima_fecha
                est.ultimo_mensaje = ultimo_mensaje
                est.total_mensajes = total_whatsapp + total_envios
                estudiantes_con_mensajes.append(est)
        except Exception as e:
            # Si hay algún error con un estudiante, continuar con el siguiente
            print(f"Error procesando estudiante {est.id}: {str(e)}")
            continue
    
    # Ordenar por fecha más reciente
    estudiantes_con_mensajes.sort(
        key=lambda x: x.ultima_fecha if hasattr(x, 'ultima_fecha') and x.ultima_fecha else timezone.now() - timedelta(days=365*10), 
        reverse=True
    )
    
    # Estudiante seleccionado
    estudiante_id = request.GET.get('estudiante')
    estudiante_seleccionado = None
    mensajes = []
    page_obj = None
    
    if estudiante_id:
        try:
            estudiante_seleccionado = Estudiante.objects.get(id=estudiante_id)
            telefono_limpio = estudiante_seleccionado.telefono.replace('+', '').replace(' ', '')
            
            # Crear lista unificada de mensajes
            lista_mensajes = []
            
            # WhatsApp logs
            for msg in WhatsappLog.objects.filter(telefono=telefono_limpio):
                fecha = msg.fecha
                if timezone.is_naive(fecha):
                    fecha = timezone.make_aware(fecha)
                    
                lista_mensajes.append({
                    'mensaje': msg.mensaje,
                    'fecha': fecha,
                    'estado': msg.estado,
                    'tipo': 'recibido' if msg.estado == 'INCOMING' else 'enviado'
                })
            
            # Envio logs (mensajes enviados por campañas)
            for envio in EnvioLog.objects.filter(estudiante=estudiante_seleccionado).select_related('campana', 'campana__plantilla'):
                fecha = envio.fecha_envio
                if timezone.is_naive(fecha):
                    fecha = timezone.make_aware(fecha)
                
                # Obtener el mensaje de la plantilla
                mensaje_campana = envio.campana.plantilla.cuerpo_mensaje
                # Personalizar con el nombre del estudiante
                mensaje_personalizado = mensaje_campana.replace('{nombre}', estudiante_seleccionado.nombre)
                    
                lista_mensajes.append({
                    'mensaje': mensaje_personalizado,
                    'fecha': fecha,
                    'estado': envio.estado,
                    'tipo': 'enviado'
                })
            
            # Ordenar por fecha
            lista_mensajes.sort(key=lambda x: x['fecha'] if x['fecha'] else timezone.now() - timedelta(days=365*10))
            
            # Paginación
            paginator = Paginator(lista_mensajes, 50)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
            mensajes = page_obj.object_list
            
        except Estudiante.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error cargando mensajes: {str(e)}")
    
    context = {
        'estudiantes': estudiantes_con_mensajes[:50],  # Limitar a 50 contactos
        'estudiante_seleccionado': estudiante_seleccionado,
        'mensajes': mensajes,
        'page_obj': page_obj,
    }
    
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


def obtener_archivos_modulo_view(request, modulo_id):
    """
    API para obtener archivos multimedia de un módulo específico
    Usado por estudiantes para ver contenido disponible
    """
    from .models import Modulo
    
    try:
        modulo = get_object_or_404(Modulo, id=modulo_id)
        archivos = modulo.archivos_multimedia.filter(activo=True).order_by('orden', 'id')
        
        archivos_data = []
        for archivo in archivos:
            archivos_data.append({
                'id': archivo.id,
                'tipo': archivo.get_tipo_display(),
                'titulo': archivo.titulo,
                'descripcion': archivo.descripcion,
                'url_descarga': f'/media/descargar-archivo/{archivo.id}/' if archivo.archivo else None,
                'url_externa': archivo.url_externa,
                'disponible_offline': archivo.disponible_offline,
                'tamano_mb': archivo.tamano_mb(),
                'duracion_segundos': archivo.duracion_segundos,
            })
        
        return JsonResponse({
            'success': True,
            'modulo': {
                'id': modulo.id,
                'titulo': modulo.titulo,
                'numero': modulo.numero,
            },
            'archivos': archivos_data,
            'total': len(archivos_data)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def descargar_archivo_multimedia(request, archivo_id):
    """
    Descarga un archivo multimedia específico
    Permite descarga offline si está habilitada
    """
    try:
        archivo = get_object_or_404(ArchivoModulo, id=archivo_id)
        
        if not archivo.archivo:
            return JsonResponse({
                'error': 'Este archivo no tiene descarga disponible. Usa la URL externa.'
            }, status=400)
        
        # Verificar si la descarga offline está permitida
        if not archivo.disponible_offline:
            return JsonResponse({
                'error': 'La descarga offline no está habilitada para este archivo.'
            }, status=403)
        
        # Retornar el archivo para descarga
        response = FileResponse(archivo.archivo.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{archivo.titulo}.{archivo.archivo.name.split(".")[-1]}"'
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'error': f'Error al descargar archivo: {str(e)}'
        }, status=500)


@staff_member_required
def test_email_gmail_view(request):
    """Vista para probar la configuración de Gmail"""
    from .email_test import test_gmail_connection, format_email_status_html
    
    context = {
        'title': 'Probar Conexión Gmail',
        'status_html': format_email_status_html(),
        'resultado': None
    }
    
    if request.method == 'POST':
        success, message = test_gmail_connection()
        context['resultado'] = {
            'success': success,
            'message': message
        }
    
    return render(request, 'admin/test_email.html', context)


# ========================================
# VISTAS PARA GENERACIÓN DE CURSOS CON IA
# ========================================

@staff_member_required
def subir_documento_curso(request):
    """
    Vista para subir documento (PDF/Word) y generar curso con IA.
    Paso 1: Subida del archivo.
    """
    from .models import Cliente
    
    context = {
        'clientes': Cliente.objects.all().order_by('nombre')
    }
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            archivo = request.FILES.get('documento')
            cliente_id = request.POST.get('cliente_id')
            modelo_ia = request.POST.get('modelo_ia', 'gpt-3.5-turbo')
            
            # Validaciones
            if not archivo:
                context['error'] = "Debes subir un archivo"
                return render(request, 'admin/subir_documento_curso.html', context)
            
            if not cliente_id:
                context['error'] = "Debes seleccionar un cliente"
                return render(request, 'admin/subir_documento_curso.html', context)
            
            try:
                cliente = Cliente.objects.get(id=cliente_id)
            except Cliente.DoesNotExist:
                context['error'] = "Cliente no encontrado"
                return render(request, 'admin/subir_documento_curso.html', context)
            
            # Validar tipo de archivo
            nombre_archivo = archivo.name.lower()
            if not (nombre_archivo.endswith('.pdf') or nombre_archivo.endswith('.docx') or nombre_archivo.endswith('.txt')):
                context['error'] = "Solo se permiten archivos PDF, Word (.docx) o TXT"
                return render(request, 'admin/subir_documento_curso.html', context)
            
            # Procesar archivo
            from .utils_ia import extraer_texto_documento, generar_estructura_curso_con_ia, validar_estructura_curso
            
            # Paso 1: Extraer texto
            context['procesando'] = True
            texto = extraer_texto_documento(archivo)
            
            if len(texto) < 500:
                context['error'] = "El documento es muy corto (mínimo 500 caracteres)"
                return render(request, 'admin/subir_documento_curso.html', context)
            
            # Paso 2: Generar estructura con IA
            estructura = generar_estructura_curso_con_ia(texto, modelo=modelo_ia)
            
            # Paso 3: Validar estructura
            es_valida, errores = validar_estructura_curso(estructura)
            
            if not es_valida:
                context['error'] = f"La IA generó una estructura inválida: {', '.join(errores)}"
                context['advertencia'] = "Intenta con un documento diferente o modelo GPT-4"
                return render(request, 'admin/subir_documento_curso.html', context)
            
            # Guardar estructura en sesión para el siguiente paso
            request.session['estructura_curso'] = estructura
            request.session['cliente_id'] = cliente_id
            request.session['archivo_nombre'] = archivo.name
            request.session['modelo_usado'] = modelo_ia
            
            # Redirigir a vista previa
            from django.shortcuts import redirect
            return redirect('vista_previa_curso_ia')
            
        except ValueError as e:
            context['error'] = str(e)
            return render(request, 'admin/subir_documento_curso.html', context)
        except Exception as e:
            context['error'] = f"Error inesperado: {str(e)}"
            logger.error(f"Error en subir_documento_curso: {e}")
            import traceback
            traceback.print_exc()
            return render(request, 'admin/subir_documento_curso.html', context)
    
    return render(request, 'admin/subir_documento_curso.html', context)


@staff_member_required
def vista_previa_curso_ia(request):
    """
    Vista para mostrar preview del curso generado y permitir edición.
    Paso 2: Revisión y edición antes de guardar.
    """
    from .models import Cliente
    from .utils_ia import guardar_curso_desde_estructura
    
    # Obtener estructura de la sesión
    estructura = request.session.get('estructura_curso')
    cliente_id = request.session.get('cliente_id')
    archivo_nombre = request.session.get('archivo_nombre')
    modelo_usado = request.session.get('modelo_usado', 'gpt-3.5-turbo')
    
    if not estructura or not cliente_id:
        from django.shortcuts import redirect
        from django.contrib import messages
        messages.error(request, "No hay datos de curso. Debes subir un documento primero.")
        return redirect('subir_documento_curso')
    
    try:
        cliente = Cliente.objects.get(id=cliente_id)
    except Cliente.DoesNotExist:
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.error(request, "Cliente no encontrado")
        return redirect('subir_documento_curso')
    
    context = {
        'estructura': estructura,
        'cliente': cliente,
        'archivo_nombre': archivo_nombre,
        'modelo_usado': modelo_usado,
        'total_modulos': len(estructura.get('modulos', [])),
        'total_lecciones': sum(len(m.get('lecciones', [])) for m in estructura.get('modulos', [])),
        'total_preguntas': sum(
            sum(len(l.get('preguntas', [])) for l in m.get('lecciones', []))
            for m in estructura.get('modulos', [])
        ),
    }
    
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'guardar':
            try:
                # Actualizar estructura con datos editados del formulario
                estructura['titulo'] = request.POST.get('titulo', estructura['titulo'])
                estructura['descripcion'] = request.POST.get('descripcion', estructura['descripcion'])
                estructura['duracion_estimada'] = request.POST.get('duracion_estimada', estructura.get('duracion_estimada', '4 semanas'))
                estructura['nivel'] = request.POST.get('nivel', estructura.get('nivel', 'Intermedio'))
                estructura['puntos_por_leccion'] = int(request.POST.get('puntos_por_leccion', estructura.get('puntos_por_leccion', 50)))
                estructura['puntos_por_quiz'] = int(request.POST.get('puntos_por_quiz', estructura.get('puntos_por_quiz', 100)))
                
                # Guardar curso en la base de datos
                curso = guardar_curso_desde_estructura(estructura, cliente, archivo_nombre)
                
                # Limpiar sesión
                del request.session['estructura_curso']
                del request.session['cliente_id']
                del request.session['archivo_nombre']
                if 'modelo_usado' in request.session:
                    del request.session['modelo_usado']
                
                # Redirigir al admin del curso
                from django.shortcuts import redirect
                from django.contrib import messages
                messages.success(
                    request, 
                    f'¡Curso "{curso.titulo}" creado exitosamente! Revisa y activa cuando esté listo.'
                )
                return redirect(f'/admin/core/curso/{curso.id}/change/')
                
            except Exception as e:
                context['error'] = f"Error al guardar el curso: {str(e)}"
                logger.error(f"Error guardando curso: {e}")
                import traceback
                traceback.print_exc()
        
        elif accion == 'regenerar':
            # TODO: Implementar regeneración parcial en Fase 3
            context['advertencia'] = "Regeneración parcial disponible en la próxima versión"
        
        elif accion == 'cancelar':
            # Limpiar sesión y redirigir
            del request.session['estructura_curso']
            del request.session['cliente_id']
            del request.session['archivo_nombre']
            if 'modelo_usado' in request.session:
                del request.session['modelo_usado']
            
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.info(request, "Creación de curso cancelada")
            return redirect('subir_documento_curso')
    
    return render(request, 'admin/vista_previa_curso_ia.html', context)
