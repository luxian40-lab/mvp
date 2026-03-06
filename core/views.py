from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
# Vista unificada del dashboard admin
@staff_member_required
def dashboard_unificado(request):
    """
    Dashboard profesional unificado de eki.
    Métricas reales: cursos, clientes, estudiantes, certificados, gamificación,
    WhatsApp, IA, y progreso educativo.
    """
    from django.db.models import Count, Avg, Sum, Q, F
    from django.db.models.functions import TruncDate
    from datetime import datetime, timedelta
    import json

    # --- Filtros opcionales ---
    cliente_id = request.GET.get('cliente')
    curso_id = request.GET.get('curso')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    clientes_all = Cliente.objects.all().order_by('nombre')
    cursos_all = Curso.objects.all().order_by('nombre')

    estudiantes_q = Estudiante.objects.filter(activo=True)
    if cliente_id:
        estudiantes_q = estudiantes_q.filter(cliente_id=cliente_id)

    # --- Métricas principales ---
    total_cursos = Curso.objects.count()
    total_clientes = Cliente.objects.count()
    total_estudiantes = estudiantes_q.count()

    # WhatsApp
    total_mensajes_whatsapp = WhatsappLog.objects.count()
    mensajes_enviados = WhatsappLog.objects.filter(tipo='SENT').count()
    mensajes_recibidos = WhatsappLog.objects.filter(tipo='INCOMING').count()
    total_audios = WhatsappLog.objects.filter(es_audio=True).count()
    total_agentes_ia = WhatsappLog.objects.filter(agente_usado__isnull=False).exclude(agente_usado='').count()

    # Progreso educativo
    total_progreso = ProgresoEstudiante.objects.count()
    total_modulos_completados = ModuloCompletado.objects.count()
    cursos_completados = ProgresoEstudiante.objects.filter(completado=True).count()

    # Certificados
    try:
        from .models_certificados import Certificado
        total_certificados = Certificado.objects.count()
    except Exception:
        total_certificados = 0

    # Gamificación
    try:
        from .gamificacion import PerfilGamificacion
        total_perfiles_gam = PerfilGamificacion.objects.count()
        puntos_promedio = PerfilGamificacion.objects.aggregate(avg=Avg('puntos_totales'))['avg'] or 0
        top_estudiantes = PerfilGamificacion.objects.select_related('estudiante').order_by('-puntos_totales')[:10]
    except Exception:
        total_perfiles_gam = 0
        puntos_promedio = 0
        top_estudiantes = []

    # Ubicaciones (municipio)
    ubicaciones_municipio = (
        Estudiante.objects.filter(activo=True)
        .exclude(municipio__isnull=True).exclude(municipio='')
        .values('municipio')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )

    # Progreso por curso
    progreso_por_curso = Curso.objects.annotate(
        total_estudiantes=Count('progresoestudiante', distinct=True),
        total_modulos_completados=Count('progresoestudiante__modulos_completados', distinct=True),
        completados=Count('progresoestudiante', filter=Q(progresoestudiante__completado=True), distinct=True)
    )

    # --- Datos para gráficos (últimos 7 días) ---
    hoy = datetime.now().date()
    hace_7_dias = hoy - timedelta(days=7)
    mensajes_por_dia = (
        WhatsappLog.objects.filter(fecha__gte=hace_7_dias)
        .annotate(dia=TruncDate('fecha'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )
    chart_labels = []
    chart_values = []
    for i in range(7):
        dia = hoy - timedelta(days=6 - i)
        chart_labels.append(dia.strftime('%d/%m'))
        count = next((m['total'] for m in mensajes_por_dia if m['dia'] == dia), 0)
        chart_values.append(count)

    # Distribución de tipos de mensaje (for pie chart)
    tipos_msg = WhatsappLog.objects.values('tipo').annotate(total=Count('id')).order_by('-total')
    chart_tipos_labels = [t['tipo'] or 'Otro' for t in tipos_msg]
    chart_tipos_values = [t['total'] for t in tipos_msg]

    # --- Prospectos B2B ---
    try:
        from .models import ProspectoB2B
        total_prospectos = ProspectoB2B.objects.count()
    except Exception:
        total_prospectos = 0

    # --- Tasa de completación ---
    total_inscripciones = ProgresoEstudiante.objects.count()
    tasa_completacion = round((cursos_completados / total_inscripciones * 100), 1) if total_inscripciones > 0 else 0

    # --- Filtro municipio (para Tab Reportes) ---
    municipio_filtro = request.GET.get('municipio', '')
    municipios = list(
        Estudiante.objects.filter(activo=True)
        .exclude(municipio__isnull=True).exclude(municipio='')
        .values_list('municipio', flat=True).distinct().order_by('municipio')
    )

    # --- Detalle por estudiante (Tab Reportes B2B) ---
    # Optimizado: prefetch para evitar N+1
    from django.db.models import Count, Subquery, OuterRef, IntegerField
    from django.db.models.functions import Coalesce
    from .gamificacion import PerfilGamificacion as PG_detail

    est_q = Estudiante.objects.filter(activo=True).select_related('cliente')
    if cliente_id:
        est_q = est_q.filter(cliente_id=cliente_id)
    if municipio_filtro:
        est_q = est_q.filter(municipio=municipio_filtro)

    est_ids = list(est_q[:200].values_list('id', flat=True))

    # Pre-cargar progresos con select_related('curso') y annotaciones
    progresos_map = {}
    for p in ProgresoEstudiante.objects.filter(
        estudiante_id__in=est_ids
    ).select_related('curso').annotate(
        total_mods=Count('curso__modulos'),
        mods_comp=Count('modulos_completados'),
    ):
        progresos_map.setdefault(p.estudiante_id, p)

    # Pre-cargar gamificación
    puntos_map = dict(
        PG_detail.objects.filter(estudiante_id__in=est_ids)
        .values_list('estudiante_id', 'puntos_totales')
    )

    estudiantes_detalle = []
    for est in est_q.filter(id__in=est_ids):
        progreso = progresos_map.get(est.id)
        puntos_est = puntos_map.get(est.id, 0)
        avance = 0
        curso_nombre = '-'
        if progreso:
            curso_nombre = progreso.curso.nombre if progreso.curso else '-'
            total_mods = progreso.total_mods or 0
            mods_comp = progreso.mods_comp or 0
            avance = round(mods_comp / total_mods * 100) if total_mods > 0 else 0
        estudiantes_detalle.append({
            'nombre': est.nombre,
            'cedula': est.cedula,
            'organizacion': est.cliente.nombre if est.cliente else '-',
            'municipio': est.municipio or '-',
            'curso': curso_nombre,
            'avance': avance,
            'puntos': puntos_est,
        })

    # --- Detalle por cliente (organización) ---
    clientes_detalle = []
    for c in clientes_all:
        est_cliente = Estudiante.objects.filter(cliente=c, activo=True)
        n_est = est_cliente.count()
        tels = [e.telefono for e in est_cliente if e.telefono]
        n_cursos = Curso.objects.filter(progresoestudiante__estudiante__cliente=c).distinct().count()
        n_audio = WhatsappLog.objects.filter(telefono__in=tels, es_audio=True).count() if tels else 0
        n_ia = WhatsappLog.objects.filter(telefono__in=tels, agente_usado__isnull=False).exclude(agente_usado='').count() if tels else 0
        n_comp = ProgresoEstudiante.objects.filter(estudiante__cliente=c, completado=True).count()
        clientes_detalle.append({
            'nombre': c.nombre,
            'cursos': n_cursos,
            'estudiantes': n_est,
            'uso_audio': n_audio,
            'uso_ia': n_ia,
            'cursos_completados': n_comp,
        })

    # --- Tickets de soporte (Tab Auditoría) ---
    try:
        from .models import SolicitudSoporte
        tickets_soporte = SolicitudSoporte.objects.select_related('estudiante').order_by('-fecha_solicitud')[:50]
    except Exception:
        tickets_soporte = []

    # --- Excel export ---
    if request.GET.get('exportar') == 'excel':
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Estudiantes'
        headers = ['Nombre', 'Cédula', 'Organización', 'Municipio', 'Curso', 'Avance %', 'Puntos']
        header_fill = PatternFill(start_color='3b5bdb', end_color='3b5bdb', fill_type='solid')
        header_font = Font(color='FFFFFF', bold=True)
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
        for row_idx, est in enumerate(estudiantes_detalle, 2):
            ws.cell(row=row_idx, column=1, value=est['nombre'])
            ws.cell(row=row_idx, column=2, value=est['cedula'])
            ws.cell(row=row_idx, column=3, value=est['organizacion'])
            ws.cell(row=row_idx, column=4, value=est['municipio'])
            ws.cell(row=row_idx, column=5, value=est['curso'])
            ws.cell(row=row_idx, column=6, value=est['avance'])
            ws.cell(row=row_idx, column=7, value=est['puntos'])
        for col in range(1, 8):
            ws.column_dimensions[chr(64 + col)].width = 20
        from django.http import HttpResponse as ExcelResponse
        response = ExcelResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=reporte_eki_b2b.xlsx'
        wb.save(response)
        return response

    context = {
        # Métricas principales
        'total_cursos': total_cursos,
        'total_clientes': total_clientes,
        'total_estudiantes': total_estudiantes,
        'total_mensajes_whatsapp': total_mensajes_whatsapp,
        'mensajes_enviados': mensajes_enviados,
        'mensajes_recibidos': mensajes_recibidos,
        'total_audios': total_audios,
        'total_agentes_ia': total_agentes_ia,
        'total_progreso': total_progreso,
        'total_modulos_completados': total_modulos_completados,
        'cursos_completados': cursos_completados,
        'total_certificados': total_certificados,
        'total_perfiles_gam': total_perfiles_gam,
        'puntos_promedio': round(puntos_promedio, 1),
        'top_estudiantes': top_estudiantes,
        'total_prospectos': total_prospectos,
        'tasa_completacion': tasa_completacion,
        # Ubicaciones
        'ubicaciones_municipio': ubicaciones_municipio,
        # Progreso por curso
        'progreso_por_curso': progreso_por_curso,
        # Gráficos
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
        'chart_tipos_labels': json.dumps(chart_tipos_labels),
        'chart_tipos_values': json.dumps(chart_tipos_values),
        # Filtros
        'clientes': clientes_all,
        'cursos': cursos_all,
        'cliente_filtro': int(cliente_id) if cliente_id else None,
        'curso_filtro': int(curso_id) if curso_id else None,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'municipios': municipios,
        'municipio_filtro': municipio_filtro,
        # Detalle
        'clientes_detalle': clientes_detalle,
        'estudiantes_detalle': estudiantes_detalle,
        # Tickets
        'tickets_soporte': tickets_soporte,
    }
    return render(request, 'admin/dashboard.html', context)
from django.http import HttpResponse, JsonResponse, FileResponse, HttpResponseBadRequest
from django.core.files.storage import default_storage
import mimetypes
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

from .models import Campana, Estudiante, WhatsappLog, EnvioLog, Cliente, Curso, ProgresoEstudiante, ModuloCompletado
from .models_extras import ArchivoModulo
from .utils import enviar_whatsapp
from .intent_detector import detect_intent
from .response_templates import get_response_for_intent

from django.views.decorators.csrf import csrf_exempt

# Endpoint proxy para servir archivos de S3 desde el dominio propio
@csrf_exempt
def serve_media_proxy(request, filename):
    s3_url = f"https://eki-produccion.s3.us-east-2.amazonaws.com/{filename}"
    r = requests.get(s3_url, stream=True)
    if r.status_code == 200:
        content_type = r.headers.get('Content-Type', 'application/octet-stream')
        content_length = r.headers.get('Content-Length')
        # Forzar Content-Disposition inline para WhatsApp
        content_disposition = f'inline; filename="{filename}"'
        response = FileResponse(r.raw, content_type=content_type)
        if content_length:
            response['Content-Length'] = content_length
        response['Content-Disposition'] = content_disposition
        # WhatsApp/Twilio requieren CORS headers a veces
        response['Access-Control-Allow-Origin'] = '*'
        return response
    else:
        return HttpResponseBadRequest("Archivo no encontrado o error en S3")

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
    
    # Usar solo plantillas existentes. Si no existe dashboard_metrics.html, usar dashboard_metricas.html
    return render(request, 'admin/dashboard_metricas.html', context)


# ---------- Vista de instrucciones ----------
@staff_member_required
def instrucciones_view(request):
    """Vista para mostrar el instructivo completo de eki."""
    return render(request, 'admin/instrucciones.html')


# ---------- Vista de importación de estudiantes ----------
@staff_member_required
def importar_estudiantes(request):
    """Vista para importar estudiantes desde un archivo Excel.
    Formato obligatorio: Cédula | Nombre | Teléfono | Municipio | Departamento | Género | Edad | Curso | Cliente
    """
    context = {}
    
    if request.method == 'POST':
        archivo = request.FILES.get('archivo_excel')
        
        if not archivo:
            context['error'] = "Por favor selecciona un archivo Excel"
            return render(request, 'admin/importar_estudiantes.html', context)
        
        try:
            if not archivo.name.endswith(('.xlsx', '.xls')):
                context['error'] = 'El archivo debe ser .xlsx o .xls'
                return render(request, 'admin/importar_estudiantes.html', context)
            
            wb = openpyxl.load_workbook(archivo, data_only=True)
            ws = wb.active
            
            estudiantes_creados = 0
            estudiantes_actualizados = 0
            inscritos = 0
            errores = []
            
            import re
            from django.db import IntegrityError
            
            def _normalizar_celda(val):
                """Convierte celdas Excel a string limpio (int/float → str sin decimales)."""
                if val is None:
                    return ''
                if isinstance(val, float):
                    if val == int(val):
                        return str(int(val))
                    return str(val)
                if isinstance(val, int):
                    return str(val)
                return str(val).strip()
            
            def _limpiar_texto(val):
                """Limpia texto: strip, lower, elimina espacios dobles."""
                if not val:
                    return ''
                return re.sub(r'\s+', ' ', val.strip().lower())
            
            def _normalizar_telefono(raw):
                """Normaliza teléfono colombiano: solo dígitos, prefijo 57."""
                tel = re.sub(r'\D', '', raw)
                if tel.startswith('57') and len(tel) == 12:
                    return tel
                if len(tel) == 10 and tel.startswith('3'):
                    return '57' + tel
                if len(tel) == 7 or len(tel) == 10:
                    return '57' + tel
                return tel
            
            GENEROS_VALIDOS = {'m': 'M', 'f': 'F', 'o': 'O', 'masculino': 'M', 'femenino': 'F', 
                               'otro': 'O', 'hombre': 'M', 'mujer': 'F', 'nr': 'NR', 'no reporta': 'NR'}
            
            # Columnas: A=Cédula | B=Nombre | C=Teléfono | D=Municipio | E=Departamento | F=Género | G=Edad | H=Curso | I=Cliente
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if not row or all(cell is None or str(cell).strip() == '' for cell in row[:3]):
                    continue
                
                try:
                    cedula = _normalizar_celda(row[0]) if len(row) > 0 else ''
                    nombre = _normalizar_celda(row[1]) if len(row) > 1 else ''
                    telefono_raw = _normalizar_celda(row[2]) if len(row) > 2 else ''
                    municipio = _limpiar_texto(_normalizar_celda(row[3])) if len(row) > 3 else ''
                    departamento = _limpiar_texto(_normalizar_celda(row[4])) if len(row) > 4 else ''
                    genero_raw = _limpiar_texto(_normalizar_celda(row[5])) if len(row) > 5 else ''
                    edad_raw = _normalizar_celda(row[6]) if len(row) > 6 else ''
                    curso_nombre = _normalizar_celda(row[7]) if len(row) > 7 else ''
                    cliente_nombre = _normalizar_celda(row[8]) if len(row) > 8 else ''
                    
                    # Validar campos obligatorios
                    campos_faltantes = []
                    if not cedula: campos_faltantes.append('Cédula')
                    if not nombre: campos_faltantes.append('Nombre')
                    if not telefono_raw: campos_faltantes.append('Teléfono')
                    if not municipio: campos_faltantes.append('Municipio')
                    if not departamento: campos_faltantes.append('Departamento')
                    if not genero_raw: campos_faltantes.append('Género')
                    if not edad_raw: campos_faltantes.append('Edad')
                    
                    if campos_faltantes:
                        errores.append(f"Fila {row_idx}: Faltan campos obligatorios: {', '.join(campos_faltantes)}")
                        continue
                    
                    # Normalizar teléfono
                    telefono = _normalizar_telefono(telefono_raw)
                    if not telefono or len(telefono) < 10:
                        errores.append(f"Fila {row_idx}: Teléfono inválido '{telefono_raw}'")
                        continue
                    
                    # Normalizar género
                    genero = GENEROS_VALIDOS.get(genero_raw, '')
                    if not genero:
                        errores.append(f"Fila {row_idx}: Género '{genero_raw}' no válido (use: M, F, O, NR)")
                        continue
                    
                    # Validar edad
                    edad = None
                    if edad_raw:
                        try:
                            edad = int(re.sub(r'\D', '', edad_raw))
                            if edad < 1 or edad > 120:
                                errores.append(f"Fila {row_idx}: Edad '{edad_raw}' fuera de rango (1-120)")
                                continue
                        except (ValueError, TypeError):
                            errores.append(f"Fila {row_idx}: Edad '{edad_raw}' no es un número válido")
                            continue
                    
                    # Buscar cliente
                    cliente = None
                    if cliente_nombre:
                        try:
                            cliente = Cliente.objects.get(nombre__iexact=cliente_nombre.strip())
                        except Cliente.DoesNotExist:
                            errores.append(f"Fila {row_idx}: Cliente '{cliente_nombre}' no encontrado")
                    
                    # Crear o actualizar por CÉDULA (clave única)
                    defaults = {
                        'nombre': nombre.strip().title(),
                        'telefono': telefono,
                        'municipio': municipio,
                        'departamento': departamento,
                        'genero': genero,
                        'edad': edad,
                        'tipo_documento': 'CC',
                        'estado_onboarding': 'completado',
                        'estado_chat': 'ACTIVO',
                        'acepto_terminos': True,
                        'activo': True,
                    }
                    if cliente:
                        defaults['cliente'] = cliente
                    
                    try:
                        estudiante, creado = Estudiante.objects.update_or_create(
                            cedula=cedula,
                            defaults=defaults
                        )
                        if creado:
                            estudiantes_creados += 1
                        else:
                            estudiantes_actualizados += 1
                    except IntegrityError as e:
                        if 'telefono' in str(e).lower():
                            errores.append(f"Fila {row_idx}: Teléfono '{telefono}' ya registrado para otro estudiante")
                        else:
                            errores.append(f"Fila {row_idx}: Error de integridad - {str(e)}")
                        continue
                    
                    # Inscribir en curso si se especificó
                    if curso_nombre:
                        try:
                            curso = Curso.objects.get(nombre__iexact=curso_nombre.strip())
                            progreso, prog_creado = ProgresoEstudiante.objects.get_or_create(
                                estudiante=estudiante,
                                curso=curso,
                                defaults={'progreso': 0, 'completado': False}
                            )
                            if prog_creado:
                                inscritos += 1
                        except Curso.DoesNotExist:
                            errores.append(f"Fila {row_idx}: Curso '{curso_nombre}' no encontrado")
                
                except Exception as e:
                    errores.append(f"Fila {row_idx}: {str(e)}")
            
            context['exito'] = True
            context['creados'] = estudiantes_creados
            context['actualizados'] = estudiantes_actualizados
            context['inscritos'] = inscritos
            context['total'] = estudiantes_creados + estudiantes_actualizados
            
            if errores:
                context['advertencias'] = errores[:20]
        
        except Exception as e:
            context['error'] = f'Error al procesar el archivo: {str(e)}'
    
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
                    tipo = '📥 Entrante' if log.tipo == 'INCOMING' else '📤 Saliente'
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
            response['Content-Disposition'] = f'attachment; filename="Reporte_eki_{fecha_str}.xlsx"'
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
        import sys
        print("🔵 WEBHOOK RECIBIÓ POST", flush=True)
        logger.info("🔵 WEBHOOK RECIBIÓ POST")
        
        try:
            # Intentar parsear como JSON (Meta)
            payload = json.loads(request.body.decode('utf-8'))
            print(f"🔵 Payload (JSON): {payload}", flush=True)
            logger.info(f"🔵 Payload (JSON): {payload}")
            
            # Detectar si es Meta o Twilio
            if 'entry' in payload:
                # ===== META WHATSAPP =====
                logger.info("📍 Detectado: META WhatsApp")
                _procesar_meta_webhook(payload)
            else:
                # Podría ser Twilio con JSON — intentar procesarlo como Twilio también
                print("⚠️ JSON recibido pero no es Meta — intentando como Twilio", flush=True)
                logger.info("⚠️ JSON recibido pero no es Meta, verificando si tiene datos Twilio")
                # Algunos webhooks de Twilio pueden llegar como JSON
                if 'Body' in payload or 'From' in payload or 'MessageStatus' in payload:
                    print("🔵 JSON con datos Twilio detectado — procesando", flush=True)
                    _procesar_twilio_webhook(payload)
                else:
                    print("⚠️ JSON desconocido — ignorando", flush=True)
                return HttpResponse('OK')
                
        except json.JSONDecodeError:
            # Podría ser Twilio (form-data)
            print("🔵 Payload (Form-Data) - Probablemente Twilio", flush=True)
            print(f"POST keys: {list(request.POST.keys())}", flush=True)
            logger.info("🔵 Payload (Form-Data) - Probablemente Twilio")
            twilio_result = _procesar_twilio_webhook(request.POST)
            # Si _procesar_twilio_webhook devuelve TwiML HttpResponse, retornarlo
            if isinstance(twilio_result, HttpResponse):
                return twilio_result
        
        except Exception as e:
            print(f"❌ Error en webhook: {str(e)}", flush=True)
            logger.error(f"❌ Error en webhook: {str(e)}")
            import traceback
            traceback.print_exc()
            return HttpResponse('Error', status=500)

        return HttpResponse('OK')


def _escape_twiml(text):
    """Escapa caracteres especiales para TwiML XML."""
    if not text:
        return text
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def _procesar_twilio_webhook(post_data):
    """Procesa webhooks de Twilio WhatsApp"""
    # ============================================================
    # FILTRO 1: Ignorar status callbacks de Twilio (queued/sent/delivered)
    # Twilio envía callbacks de estado al mismo webhook, NO son mensajes
    # ============================================================
    message_status = post_data.get('MessageStatus', post_data.get('SmsStatus', ''))
    if message_status and message_status.lower() in ['queued', 'sending', 'sent', 'delivered', 'undelivered', 'failed', 'read']:
        logger.debug(f"Status callback ignorado: {message_status}")
        return
    
    # FILTRO 2: Ignorar si no hay Body ni Media (status callback sin MessageStatus)
    raw_body = post_data.get('Body', '')
    raw_media = int(post_data.get('NumMedia', 0))
    if not raw_body and raw_media == 0 and not post_data.get('From', ''):
        logger.debug("Webhook vacio ignorado (sin Body ni Media)")
        return
    
    try:
        logger.info("🔵 TWILIO: Procesando...")
        
        # Twilio envía datos en formato form-data
        msg_body = post_data.get('Body', '')
        msg_from = post_data.get('From', '')  # whatsapp:+573001234567
        msg_to = post_data.get('To', '')      # whatsapp:+14155238886
        msg_sid = post_data.get('MessageSid', f'twilio_{timezone.now().timestamp()}')
        
        logger.info(f"📱 Body: {msg_body} | From: {msg_from} | To: {msg_to}")
        
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
        
        logger.info(f"📱 De: {msg_from} → Limpio: {telefono_limpio} | Mensaje: {msg_body}")
        logger.info(f"TWILIO MSG: From={telefono_limpio} Body='{msg_body[:50]}'")
        
        # 1. Guardar mensaje entrante con teléfono limpio
        WhatsappLog.objects.create(
            telefono=telefono_limpio,
            mensaje=msg_body,
            mensaje_id=msg_sid,
            tipo='INCOMING'
        )
        logger.info(f"✅ Guardado INCOMING")
        
        # ============================================================
        # FASE 0: INTERCEPCIÓN DE NO REGISTRADOS (Lead Generation)
        # Si el número no existe en Estudiante, activar "Modo Ventas"
        # ============================================================
        try:
            estudiante = Estudiante.objects.select_related('cliente').get(telefono=telefono_limpio)
            logger.info(f"Estudiante encontrado: {estudiante.nombre} (ID: {estudiante.id})")
        except Estudiante.DoesNotExist:
            # Verificar si ya es un prospecto B2B existente
            from .models import ProspectoB2B
            prospecto = None
            try:
                prospecto = ProspectoB2B.objects.get(telefono=telefono_limpio)
            except ProspectoB2B.DoesNotExist:
                pass
            
            msg_lower = msg_body.strip().lower()
            
            if prospecto:
                # Prospecto existente - procesar su respuesta
                if prospecto.esperando_email:
                    # Validar si parece un email
                    import re as re_email
                    email_match = re_email.search(r'[\w.+-]+@[\w-]+\.[\w.]+', msg_body)
                    if email_match:
                        prospecto.email = email_match.group(0)
                        prospecto.esperando_email = False
                        prospecto.fecha_ultimo_contacto = timezone.now()
                        prospecto.save()
                        
                        # Notificar al equipo de ventas por email
                        try:
                            from django.core.mail import send_mail
                            send_mail(
                                subject=f"🏢 Nuevo Lead B2B - {prospecto.empresa or prospecto.telefono}",
                                message=f"Nuevo prospecto capturado por el bot:\n\nTeléfono: {prospecto.telefono}\nEmpresa: {prospecto.empresa}\nEmail: {prospecto.email}\nMensaje: {prospecto.mensaje_original}",
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[getattr(settings, 'EMAIL_SOPORTE', 'comunidad.educativa@eki.com.co')],
                                fail_silently=True
                            )
                        except Exception:
                            pass
                        
                        texto_respuesta = (
                            "✅ *¡Perfecto!*\n\n"
                            f"Hemos registrado tu correo: *{prospecto.email}*\n\n"
                            "Nuestro equipo de ventas te contactará muy pronto "
                            "para contarte todo sobre las capacitaciones de eki. 🚜\n\n"
                            "¡Gracias por tu interés! 🌱"
                        )
                    else:
                        texto_respuesta = "📧 Por favor envía un correo electrónico válido (ej: nombre@empresa.com)"
                elif msg_lower in ['1', 'empresa', 'eki para mi empresa']:
                    prospecto.esperando_email = True
                    prospecto.fecha_ultimo_contacto = timezone.now()
                    prospecto.save()
                    texto_respuesta = (
                        "🏢 *¡Excelente!*\n\n"
                        "Nos encantaría ayudar a capacitar a tu equipo.\n\n"
                        "📧 Por favor envíanos tu *correo electrónico* "
                        "y un asesor de ventas te contactará:\n\n"
                        "👉 Ejemplo: juan@miempresa.com"
                    )
                elif msg_lower in ['3', 'ayuda', 'soy estudiante', 'estudiante']:
                    texto_respuesta = (
                        "🙋‍♂️ *¡Entendido!*\n\n"
                        "Si eres estudiante y cambiaste de número, "
                        "por favor contacta a tu coordinador o escribe a:\n\n"
                        "📧 comunidad.educativa@eki.com.co\n\n"
                        "Incluye tu nombre completo y número de cédula para que podamos ayudarte."
                    )
                else:
                    from .whatsapp_service import enviar_mensaje_ventas
                    enviar_mensaje_ventas(msg_from)
                    return
                
                # Enviar respuesta al prospecto
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                except Exception as e:
                    print(f"❌ Error enviando a prospecto: {e}")
                return
            
            else:
                # Nuevo prospecto - crear y enviar mensaje de ventas
                ProspectoB2B.objects.create(
                    telefono=telefono_limpio,
                    mensaje_original=msg_body,
                    origen='whatsapp_bot'
                )
                from .whatsapp_service import enviar_mensaje_ventas
                enviar_mensaje_ventas(msg_from)
                logger.info(f"🏢 Nuevo prospecto B2B capturado: {telefono_limpio}")
                return
        
        # ============================================================
        # MÁQUINA DE ESTADOS B2B (Onboarding con Botones Twilio)
        # ============================================================
        estado_chat = getattr(estudiante, 'estado_chat', None)
        logger.info(f"📍 Estado estudiante {estudiante.nombre}: estado_chat={estado_chat}, onboarding={estudiante.estado_onboarding}, acepto={estudiante.acepto_terminos}")
        
        # Migrar estudiantes legacy al nuevo sistema
        if not estado_chat or estado_chat in ('', None):
            if estudiante.acepto_terminos and estudiante.estado_onboarding == 'completado':
                estudiante.estado_chat = 'ACTIVO'
            elif estudiante.acepto_terminos:
                estudiante.estado_chat = 'ESPERANDO_CEDULA'
            else:
                estudiante.estado_chat = 'ESPERANDO_HABEAS_DATA'
            estudiante.save()
            estado_chat = estudiante.estado_chat
            logger.info(f"📍 Legacy migration: estado_chat → {estado_chat}")
        
        # Auto-corregir: admin creó estudiante con acepto_terminos=True pero estado_chat quedó en ESPERANDO_HABEAS_DATA
        if estado_chat == 'ESPERANDO_HABEAS_DATA' and estudiante.acepto_terminos:
            if estudiante.estado_onboarding == 'completado':
                estudiante.estado_chat = 'ACTIVO'
            else:
                estudiante.estado_chat = 'ESPERANDO_CEDULA'
            estudiante.save()
            estado_chat = estudiante.estado_chat
            logger.info(f"📍 Auto-corrección admin: estado_chat → {estado_chat}")
        
        # --- BARRERA 1: HABEAS DATA ---
        if estado_chat == 'ESPERANDO_HABEAS_DATA':
            msg_lower = msg_body.strip().lower()
            keywords_acepto = ['acepto', 'sí', 'si', 'aceptar', 'ok', 'yes', 'acepto', 'de acuerdo']
            keywords_no = ['no acepto', 'no', 'rechazo', 'rechazar']
            
            if any(k in msg_lower for k in keywords_acepto):
                estudiante.acepto_terminos = True
                estudiante.fecha_aceptacion_terminos = timezone.now()
                estudiante.estado_chat = 'ESPERANDO_CEDULA'
                estudiante.save()
                
                texto_respuesta = (
                    "✅ *¡Gracias por aceptar!*\n\n"
                    "Para verificar tu identidad, por favor escribe "
                    "tu *número de cédula* (solo los números, sin puntos ni espacios).\n\n"
                    "👉 Ejemplo: 1234567890"
                )
            elif any(k in msg_lower for k in keywords_no):
                texto_respuesta = (
                    "😔 Entendemos tu decisión.\n\n"
                    "Sin la aceptación de la política de datos no podemos "
                    "activar tu cuenta en la plataforma.\n\n"
                    "Si cambias de opinión, escríbenos en cualquier momento. 🌱"
                )
            else:
                # Enviar habeas data con botones (intentar template, sino texto)
                from .whatsapp_service import enviar_habeas_data
                resultado = enviar_habeas_data(msg_from)
                if resultado.get('success'):
                    return  # Template enviado exitosamente
                
                # Fallback: texto plano
                texto_respuesta = (
                    "👋 *¡Bienvenido a eki!*\n\n"
                    "🚜 Tu plataforma de soluciones educativas por WhatsApp\n\n"
                    "📜 *Protección de Datos Personales*\n"
                    "Antes de comenzar, necesitamos tu autorización para usar "
                    "tus datos de acuerdo con la Ley 1581 de 2012.\n\n"
                    "*¿Aceptas el tratamiento de tus datos?*\n\n"
                    "👉 Escribe *Acepto* o *No acepto*"
                )
            
            # Enviar y cortar
            try:
                from twilio.rest import Client as TwilioClient
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                client_tw = TwilioClient(account_sid, auth_token)
                destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
            except Exception as e:
                logger.error(f"❌ Error enviando habeas data: {e}")
                import traceback; traceback.print_exc()
            return  # CORTAR EJECUCIÓN
        
        # --- BARRERA 2: VALIDACIÓN 2FA (Cédula) ---
        if estado_chat == 'ESPERANDO_CEDULA':
            # Limpiar input del usuario
            cedula_input = re.sub(r'[\s\.\-]', '', msg_body.strip())
            msg_lower_cedula = msg_body.strip().lower()
            
            # Detectar "ayuda" → crear ticket de soporte
            if msg_lower_cedula in ['ayuda', 'help', 'soporte']:
                from .models import SolicitudSoporte
                solicitud = SolicitudSoporte.objects.create(
                    estudiante=estudiante,
                    mensaje_original=f"Ayuda en verificación de cédula - no coincide con registros",
                    keyword_usada='ayuda_cedula',
                    asunto='Problema con verificación de cédula',
                    prioridad='media'
                )
                texto_respuesta = (
                    f"🆘 *Ticket de Soporte #{solicitud.id}*\n\n"
                    f"Hola {estudiante.nombre}, hemos registrado tu solicitud.\n\n"
                    "📝 Un asesor revisará tu caso y te contactará pronto.\n"
                    "🕐 *Tiempo de respuesta:* menos de 24 horas.\n\n"
                    "Si recuerdas tu cédula, puedes intentar de nuevo escribiéndola aquí."
                )
            # Comparar con la cédula sanitizada en BD
            elif cedula_input == estudiante.cedula:
                estudiante.estado_chat = 'CONFIRMANDO_DATOS'
                estudiante.save()
                
                # Enviar confirmación con datos + botones (5 variables)
                org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                from .whatsapp_service import enviar_confirmacion_datos
                resultado = enviar_confirmacion_datos(
                    msg_from,
                    estudiante.nombre,
                    f"{estudiante.tipo_documento} {estudiante.cedula}",
                    org_nombre,
                    edad=estudiante.edad,
                    municipio=estudiante.municipio,
                )
                if resultado.get('success'):
                    return  # Template enviado
                
                # Fallback texto plano
                texto_respuesta = (
                    "✅ *¡Cédula verificada!*\n\n"
                    "Tus datos registrados:\n\n"
                    f"👤 *Nombre:* {estudiante.nombre}\n"
                    f"🆔 *Documento:* {estudiante.tipo_documento} {estudiante.cedula}\n"
                    f"📍 *Municipio:* {estudiante.municipio or 'No registrado'}\n"
                    f"🏢 *Organización:* {org_nombre}\n"
                    f"🎂 *Edad:* {estudiante.edad or 'No registrada'}\n"
                    f"👫 *Género:* {estudiante.get_genero_display() if estudiante.genero else 'No registrado'}\n\n"
                    "*¿Tus datos están correctos?*\n\n"
                    "👉 Escribe *Sí* si todo está bien\n"
                    "👉 Escribe *No* si hay un error"
                )
            else:
                texto_respuesta = (
                    "❌ *Cédula no coincide*\n\n"
                    "El número que ingresaste no coincide con "
                    "nuestros registros.\n\n"
                    "Por favor verifica y escribe tu cédula nuevamente "
                    "(solo números, sin puntos ni espacios).\n\n"
                    "👉 Ejemplo: 1234567890\n\n"
                    "Si crees que hay un error, escribe *ayuda*"
                )
            
            try:
                from twilio.rest import Client as TwilioClient
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                client_tw = TwilioClient(account_sid, auth_token)
                destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
            except Exception as e:
                logger.error(f"❌ Error enviando validación 2FA: {e}")
                import traceback; traceback.print_exc()
            return  # CORTAR EJECUCIÓN
        
        # --- BARRERA 3: CONFIRMACIÓN DE DATOS ---
        if estado_chat == 'CONFIRMANDO_DATOS':
            msg_lower = msg_body.strip().lower()
            keywords_si = ['sí', 'si', 'todo bien', 'correcto', 'bien', 'ok', 'yes', 'confirmo', 'confirmar']
            keywords_modificar = ['modificar', 'no', 'error', 'mal', 'incorrecto', 'hay un error', 'cambiar']
            
            if any(k in msg_lower for k in keywords_si):
                estudiante.estado_chat = 'ACTIVO'
                estudiante.estado_onboarding = 'completado'  # Legacy compat
                estudiante.save()
                
                # Enviar curso directamente (sin menú)
                org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                try:
                    from .models import Curso, ProgresoEstudiante
                    from .response_templates import obtener_video_url
                    org = estudiante.cliente
                    cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre') if org else Curso.objects.filter(activo=True).order_by('orden', 'nombre')
                    curso = cursos.first()
                    if curso:
                        progreso, creado = ProgresoEstudiante.objects.get_or_create(
                            estudiante=estudiante,
                            curso=curso,
                            defaults={'completado': False}
                        )
                        modulo = progreso.modulo_actual
                        if not modulo:
                            modulo = curso.modulos.order_by('numero').first()
                            if modulo:
                                progreso.modulo_actual = modulo
                                progreso.save()
                        if modulo:
                            # Presentación de agentes
                            from .tutor_ia_modulo import generar_presentacion_agentes
                            nombre_tutor = curso.nombre_agente_tutor or 'Gerónimo'
                            nombre_asistente = curso.nombre_agente_asistente or 'María'
                            presentacion = generar_presentacion_agentes(nombre_tutor=nombre_tutor, nombre_asistente=nombre_asistente)
                            
                            video_url = obtener_video_url(modulo)
                            archivos_multimedia = modulo.archivos_multimedia.filter(activo=True)
                            archivos_msg = ""
                            primera_media_url = None
                            if archivos_multimedia.exists():
                                archivos_msg = f"\n\n📁 *{archivos_multimedia.count()} archivo(s) multimedia*"
                                for idx, archivo in enumerate(archivos_multimedia[:3]):
                                    icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                    url = archivo.get_url_para_envio()
                                    if idx == 0 and url and archivo.tipo in ['imagen', 'video'] and not primera_media_url:
                                        primera_media_url = url
                                        archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                    elif url:
                                        archivos_msg += f"\n{icono} {archivo.titulo}"
                            if not archivos_multimedia.exists() and video_url:
                                primera_media_url = video_url
                            
                            msg_bienvenida = (
                                f"✅ *¡Datos confirmados, {estudiante.nombre}!*\n\n"
                                f"Bienvenido al programa de *{org_nombre}*\n\n"
                                f"{presentacion}\n\n"
                                f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
                                f"{modulo.descripcion}\n\n"
                                f"{modulo.contenido}{archivos_msg}\n\n\n"
                                f"Cuando termines, escribe: *\"listo\"*"
                            )
                            if primera_media_url:
                                msg_bienvenida += f"\n\n[MEDIA:{primera_media_url}]"
                            texto_respuesta = msg_bienvenida
                        else:
                            texto_respuesta = f"✅ *¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nEl curso aún no tiene módulos configurados. Te notificaremos cuando estén listos."
                    else:
                        texto_respuesta = f"✅ *¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nAún no hay cursos disponibles. Te notificaremos cuando estén listos."
                except Exception as e:
                    logger.error(f"❌ Error enviando curso directo: {e}")
                    import traceback; traceback.print_exc()
                    texto_respuesta = f"✅ *¡Datos confirmados!* Bienvenido al programa de *{org_nombre}*.\n\nEscribe *menú* para ver las opciones disponibles."
                
                # MENÚ OCULTO (no eliminado del código):
                # from .whatsapp_service import enviar_menu_principal
                # resultado = enviar_menu_principal(msg_from, estudiante.nombre)
                # if resultado.get('success'):
                #     return
            elif any(k in msg_lower for k in keywords_modificar):
                # Botón "Modificar" presionado → permitir auto-corrección
                # NOTA: Cédula/documento NO se puede cambiar aquí → genera ticket de soporte
                texto_respuesta = (
                    "📝 *Corrección de Datos*\n\n"
                    "Puedes corregir cualquiera de tus datos.\n\n"
                    "Escribe el campo que deseas cambiar seguido del nuevo valor:\n\n"
                    "1️⃣ *nombre:* Tu nombre completo\n"
                    "2️⃣ *municipio:* Tu municipio\n"
                    "3️⃣ *departamento:* Tu departamento\n"
                    "4️⃣ *documento:* Envía ticket de soporte\n"
                    "5️⃣ *edad:* Tu edad\n"
                    "6️⃣ *genero:* M, F, Otro, NR\n\n"
                    "📝 _Ejemplos:_\n"
                    "_nombre: María García López_\n"
                    "_municipio: Bogotá_\n"
                    "_edad: 35_\n"
                    "_genero: F_\n\n"
                    "📝 _O todo junto (una por línea):_\n"
                    "_nombre: María García_\n"
                    "_municipio: Bogotá_\n"
                    "_edad: 35_\n\n"
                    "👉 Escribe *3* para reintentar cédula\n"
                    "👉 Escribe *menú* si todo ya está bien"
                )
                # Guardar estado para manejar la respuesta
                estudiante.estado_chat = 'ESPERANDO_CORRECCION_DATOS'
                estudiante.save()
            else:
                # Re-enviar la plantilla de confirmación (tiene botones Confirmar/Modificar)
                from .whatsapp_service import enviar_confirmacion_datos
                org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                resultado_reenvio = enviar_confirmacion_datos(
                    msg_from,
                    estudiante.nombre,
                    f"{estudiante.tipo_documento} {estudiante.cedula}",
                    org_nombre,
                    edad=estudiante.edad,
                    municipio=estudiante.municipio,
                )
                if resultado_reenvio.get('success'):
                    return  # Template reenviado, no necesita texto
                texto_respuesta = (
                    "Por favor revisa tus datos y toca *Confirmar* o *Modificar* en la plantilla."
                )
            
            try:
                from twilio.rest import Client as TwilioClient
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                client_tw = TwilioClient(account_sid, auth_token)
                destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
            except Exception as e:
                logger.error(f"❌ Error enviando confirmación: {e}")
                import traceback; traceback.print_exc()
            return  # CORTAR EJECUCIÓN
        
        # --- BARRERA 3B: AUTO-CORRECCIÓN DE DATOS ---
        if estado_chat in ('ESPERANDO_AYUDA_MODIFICAR', 'ESPERANDO_CORRECCION_DATOS'):
            msg_lower = msg_body.strip().lower()
            
            if msg_lower in ['3', 'reintentar', 'verificación', 'verificacion', 'cédula', 'cedula']:
                # Reintentar verificación de cédula
                estudiante.estado_chat = 'ESPERANDO_CEDULA'
                estudiante.save()
                texto_respuesta = (
                    "🔄 *Reintentando verificación*\n\n"
                    "Por favor escribe tu *número de cédula* "
                    "(solo números, sin puntos ni espacios).\n\n"
                    "👉 Ejemplo: 1234567890"
                )
            elif msg_lower in ['menu', 'menú']:
                estudiante.estado_chat = 'ACTIVO'
                estudiante.estado_onboarding = 'completado'
                estudiante.save()
                # Menú oculto — enviar curso directamente
                # from .whatsapp_service import enviar_menu_principal
                # resultado = enviar_menu_principal(msg_from, estudiante.nombre)
                # if resultado.get('success'):
                #     return
                texto_respuesta = (
                    f"✅ *¡Datos actualizados, {estudiante.nombre}!*\n\n"
                    "Escribe *mis cursos* para continuar con tu curso."
                )
            else:
                # Intentar parsear los datos corregidos
                # NUEVO: Soporte para corrección campo por campo (campo: valor)
                cambios_realizados = []
                lineas = [l.strip() for l in msg_body.split('\n') if l.strip()]
                campo_valor_detectado = False
                
                GENEROS_MAP = {
                    'm': 'M', 'f': 'F', 'o': 'O', 'nr': 'NR',
                    'masculino': 'M', 'femenino': 'F', 'otro': 'O', 'no reporta': 'NR',
                    'hombre': 'M', 'mujer': 'F',
                }
                TIPOS_DOC = {'cc': 'CC', 'ti': 'TI', 'ce': 'CE', 'pp': 'PP'}
                
                for linea in lineas:
                    if ':' in linea:
                        campo, _, valor = linea.partition(':')
                        campo = campo.strip().lower()
                        valor = valor.strip()
                        
                        if not valor:
                            continue
                        
                        if campo == 'nombre':
                            estudiante.nombre = valor.title()
                            cambios_realizados.append(f"👤 Nombre → {estudiante.nombre}")
                            campo_valor_detectado = True
                        elif campo == 'municipio':
                            estudiante.municipio = valor.title()
                            cambios_realizados.append(f"📍 Municipio → {estudiante.municipio}")
                            campo_valor_detectado = True
                        elif campo == 'departamento':
                            estudiante.departamento = valor.title()
                            cambios_realizados.append(f"🗺️ Departamento → {estudiante.departamento}")
                            campo_valor_detectado = True
                        elif campo in ('edad', 'años', 'anos'):
                            try:
                                edad_val = int(re.sub(r'\D', '', valor))
                                if 1 <= edad_val <= 120:
                                    estudiante.edad = edad_val
                                    cambios_realizados.append(f"🎂 Edad → {edad_val}")
                                    campo_valor_detectado = True
                            except (ValueError, TypeError):
                                pass
                        elif campo in ('genero', 'género', 'sexo'):
                            genero = GENEROS_MAP.get(valor.lower(), '')
                            if genero:
                                estudiante.genero = genero
                                cambios_realizados.append(f"👫 Género → {estudiante.get_genero_display()}")
                                campo_valor_detectado = True
                        elif campo in ('documento', 'doc', 'cedula', 'cédula'):
                            # Crear ticket de soporte para cambio de cédula
                            from .models import SolicitudSoporte
                            SolicitudSoporte.objects.create(
                                estudiante=estudiante,
                                mensaje_original=f"Solicitud de cambio de documento: {valor}",
                                keyword_usada='modificar_documento',
                                asunto='Cambio de cédula/documento',
                                prioridad='media'
                            )
                            cambios_realizados.append(
                                "🆔 *Documento:* Se creó un ticket de soporte.\n"
                                "Un asesor revisará tu solicitud y te contactará pronto.\n"
                                "📧 *Ticket registrado correctamente.*"
                            )
                            campo_valor_detectado = True
                
                if campo_valor_detectado and cambios_realizados:
                    estudiante.estado_chat = 'CONFIRMANDO_DATOS'
                    estudiante.save()
                    
                    logger.info(f"✅ Datos corregidos campo por campo: {', '.join(cambios_realizados)}")
                    
                    org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                    from .whatsapp_service import enviar_confirmacion_datos
                    resultado_envio = enviar_confirmacion_datos(
                        msg_from,
                        estudiante.nombre,
                        f"{estudiante.tipo_documento} {estudiante.cedula}",
                        org_nombre
                    )
                    if resultado_envio.get('success'):
                        return
                    
                    texto_respuesta = (
                        "✅ *¡Datos actualizados!*\n\n"
                        "Cambios realizados:\n"
                        + '\n'.join(cambios_realizados) + "\n\n"
                        f"👤 *Nombre:* {estudiante.nombre}\n"
                        f"🆔 *Documento:* {estudiante.tipo_documento} {estudiante.cedula}\n"
                        f"📍 *Municipio:* {estudiante.municipio or 'No registrado'}\n"
                        f"🗺️ *Departamento:* {estudiante.departamento or 'No registrado'}\n"
                        f"🎂 *Edad:* {estudiante.edad or 'No registrada'}\n"
                        f"👫 *Género:* {estudiante.get_genero_display() if estudiante.genero else 'No registrado'}\n"
                        f"🏢 *Organización:* {org_nombre}\n\n"
                        "*¿Tus datos están correctos?*\n\n"
                        "👉 Escribe *Sí* si todo está bien\n"
                        "👉 Escribe *No* si hay un error"
                    )
                else:
                    # Fallback: intentar parseo legacy (4 líneas: nombre, municipio, tipo_doc, cedula)
                    from .security_handler import _parsear_datos_registro
                    resultado = _parsear_datos_registro(msg_body, estudiante)
                    if resultado:
                        nombre, municipio, tipo_doc, cedula = resultado
                        estudiante.nombre = nombre
                        estudiante.municipio = municipio
                        estudiante.tipo_documento = tipo_doc
                        estudiante.cedula = cedula
                        estudiante.estado_chat = 'CONFIRMANDO_DATOS'
                        estudiante.save()
                        
                        logger.info(f"✅ Datos auto-corregidos (legacy): {nombre}, {municipio}, {tipo_doc} {cedula}")
                        
                        org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                        from .whatsapp_service import enviar_confirmacion_datos
                        resultado_envio = enviar_confirmacion_datos(
                            msg_from,
                            nombre,
                            f"{tipo_doc} {cedula}",
                            org_nombre
                        )
                        if resultado_envio.get('success'):
                            return
                        
                        texto_respuesta = (
                            "✅ *¡Datos actualizados!*\n\n"
                            f"👤 *Nombre:* {nombre}\n"
                            f"📍 *Municipio:* {municipio}\n"
                            f"🆔 *Documento:* {tipo_doc} {cedula}\n"
                            f"🏢 *Organización:* {org_nombre}\n\n"
                            "*¿Tus datos están correctos?*\n\n"
                            "👉 Escribe *Sí* si todo está bien\n"
                            "👉 Escribe *No* si hay un error"
                        )
                    else:
                        texto_respuesta = (
                            "❌ No pude entender tus datos.\n\n"
                            "Escribe el campo seguido del valor:\n\n"
                            "📝 _Ejemplos:_\n"
                            "_nombre: María García_\n"
                            "_municipio: Bogotá_\n"
                            "_edad: 35_\n"
                            "_genero: F_\n"
                            "_documento: CC 52456789_\n\n"
                            "👉 Escribe *3* para reintentar cédula\n"
                            "👉 Escribe *menú* si ya está bien"
                        )
            
            try:
                from twilio.rest import Client as TwilioClient
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                client_tw = TwilioClient(account_sid, auth_token)
                destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
            except Exception as e:
                logger.error(f"❌ Error enviando ayuda modificar: {e}")
                import traceback; traceback.print_exc()
            return
        
        # ============================================================
        # ESTUDIANTE ACTIVO - Procesar acciones del menú y flujo normal
        # ============================================================
        # Detectar acciones del menú principal (tanto ACTIVO como completado)
        if estado_chat == 'ACTIVO' or estudiante.estado_onboarding == 'completado':
            msg_lower = msg_body.strip().lower()
            logger.info(f"📍 ACTIVO handler: msg='{msg_lower}', onboarding={estudiante.estado_onboarding}")
            
            # PRIORIDAD: Si está seleccionando curso, NO interceptar números
            if estudiante.estado_onboarding == 'esperando_seleccion_curso':
                if msg_lower in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.contexto_temporal = None
                    estudiante.save()
                    from .response_templates import get_response_for_intent
                    texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
                else:
                    # Extraer número del curso: soporta "tomar 1", "1", "tomar1"
                    import re as re_curso
                    indice = None
                    match_tomar = re_curso.match(r'^tomar\s*(\d+)$', msg_lower)
                    if match_tomar:
                        indice = int(match_tomar.group(1))
                    elif msg_body.strip().isdigit():
                        indice = int(msg_body.strip())
                    
                    if indice is not None:
                        from .selector_curso import continuar_curso_seleccionado
                        estudiante.estado_onboarding = 'completado'
                        estudiante.contexto_temporal = None
                        estudiante.save()
                        texto_respuesta = continuar_curso_seleccionado(estudiante.id, indice, msg_body)
                        logger.info(f"✅ Curso seleccionado: {indice}")
                    else:
                        # No es número ni menú → resetear y procesar normalmente
                        estudiante.estado_onboarding = 'completado'
                        estudiante.contexto_temporal = None
                        estudiante.save()
                        from .intent_detector import detect_intent
                        from .response_templates import get_response_for_intent
                        intent = detect_intent(msg_body)
                        if intent != 'desconocido':
                            texto_respuesta = get_response_for_intent(intent, estudiante.nombre, estudiante_id=estudiante.id, mensaje_original=msg_body)
                        else:
                            texto_respuesta = "No entendí tu selección. Escribe *tomar 1* para escoger un curso o *menú* para volver."
                # — Enviar respuesta de selección de curso y CORTAR —
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    # Check for multi-message or media markers
                    if texto_respuesta.startswith('[MULTI_MSG]'):
                        partes = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                        for parte in partes:
                            if not parte.strip():
                                continue
                            import re as re_multi
                            parte_texto = parte.strip()
                            parte_media = None
                            media_m = re_multi.search(r'\[MEDIA:(.*?)\]', parte_texto)
                            if media_m:
                                parte_media = media_m.group(1).strip()
                                parte_texto = parte_texto.replace(media_m.group(0), '').strip()
                            mp = {'body': parte_texto, 'from_': str(twilio_number).strip(), 'to': str(destino).strip()}
                            if parte_media:
                                mp['media_url'] = [parte_media]
                            try:
                                client_tw.messages.create(**mp)
                            except Exception:
                                mp.pop('media_url', None)
                                client_tw.messages.create(**mp)
                            import time; time.sleep(0.5)
                    else:
                        media_url_sel = None
                        import re as re_sel
                        media_m = re_sel.search(r'\[MEDIA:(.*?)\]', texto_respuesta)
                        if media_m:
                            media_url_sel = media_m.group(1).strip()
                            texto_respuesta = texto_respuesta.replace(media_m.group(0), '').strip()
                        mp = {'body': texto_respuesta, 'from_': str(twilio_number).strip(), 'to': str(destino).strip()}
                        if media_url_sel:
                            mp['media_url'] = [media_url_sel]
                        try:
                            client_tw.messages.create(**mp)
                        except Exception:
                            mp.pop('media_url', None)
                            client_tw.messages.create(**mp)
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta[:500], tipo='SENT')
                except Exception as e:
                    logger.error(f"❌ Error enviando selección curso: {e}")
                return  # CORTAR EJECUCIÓN
            
            # Detectar "Mis cursos" (botón o texto)
            elif msg_lower in ['1', 'mis cursos', 'cursos', '📚 mis cursos']:
                estudiante.estado_onboarding = 'esperando_seleccion_curso'
                estudiante.save()
                from .whatsapp_service import enviar_lista_cursos
                enviar_lista_cursos(msg_from, estudiante)
                return
            
            # Detectar "Mis puntos" (botón o texto)
            elif msg_lower in ['2', 'mis puntos', 'puntos', '🏆 mis puntos']:
                from .whatsapp_service import enviar_gamificacion_visual
                enviar_gamificacion_visual(msg_from, estudiante)
                return
            
            # Detectar "Necesito ayuda" / PQRS / Soporte (todo unificado)
            elif msg_lower in ['3', 'necesito ayuda', 'ayuda', '🙋‍♂️ necesito ayuda', 'pqrs', 'soporte', 'queja', 'reclamo', 'solicitud']:
                from .security_handler import procesar_solicitud_soporte
                respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'menu_ayuda')
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    client_tw.messages.create(body=respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=respuesta, tipo='SENT')
                except Exception:
                    pass
                return
            
            # Detectar "corregir datos" / "me equivoqué" → permitir auto-corrección incluso ya activo
            elif msg_lower in ['4', 'corregir datos', 'corregir mis datos', 'cambiar datos', 'cambiar mis datos',
                               'me equivoqué', 'me equivoque', 'editar datos', 'modificar datos',
                               'datos incorrectos', 'mis datos', 'actualizar datos']:
                texto_respuesta = (
                    "📝 *Corrección de Datos*\n\n"
                    "Puedes corregir cualquiera de tus datos.\n\n"
                    "Escribe el campo que deseas cambiar seguido del nuevo valor:\n\n"
                    "1️⃣ *nombre:* Tu nombre completo\n"
                    "2️⃣ *municipio:* Tu municipio\n"
                    "3️⃣ *departamento:* Tu departamento\n"
                    "4️⃣ *documento:* Tipo y número (CC, TI, CE, PP)\n"
                    "5️⃣ *edad:* Tu edad\n"
                    "6️⃣ *genero:* M, F, Otro, NR\n\n"
                    "📝 _Ejemplos:_\n"
                    "_nombre: María García López_\n"
                    "_municipio: Bogotá_\n"
                    "_edad: 35_\n"
                    "_documento: CC 52456789_\n"
                    "_genero: F_\n\n"
                    "📝 _O todo junto (una por línea):_\n"
                    "_nombre: María García_\n"
                    "_municipio: Bogotá_\n\n"
                    "👉 Escribe *menú* cuando termines"
                )
                estudiante.estado_chat = 'ESPERANDO_CORRECCION_DATOS'
                estudiante.save()
                try:
                    from twilio.rest import Client as TwilioClient
                    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                    twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                    client_tw = TwilioClient(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                    client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
                    WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
                except Exception as e:
                    logger.error(f"❌ Error enviando corrección datos: {e}")
                return
            
            # Detectar "menú" - enviar lista de cursos directamente (menú oculto)
            elif msg_lower in ['menu', 'menú', 'inicio', 'hola']:
                org_nombre = estudiante.cliente.nombre if estudiante.cliente else 'eki'
                # Menú oculto — redirigir a lista de cursos
                # from .whatsapp_service import enviar_menu_principal
                # resultado = enviar_menu_principal(msg_from, estudiante.nombre)
                # if resultado.get('success'):
                #     return
                estudiante.estado_onboarding = 'esperando_seleccion_curso'
                estudiante.save()
                from .whatsapp_service import enviar_lista_cursos
                enviar_lista_cursos(msg_from, estudiante)
                return
        
        # ============================================================
        # FLUJO EXISTENTE: Procesamiento normal (IA tutors, módulos, etc.)
        # ============================================================
        
        # 3. 🛡️ PRIORIDAD 1: Verificar seguridad (Habeas Data) - Legacy
        from .security_handler import verificar_seguridad_completa
        bloqueado, respuesta_seguridad, estudiante = verificar_seguridad_completa(estudiante, msg_body, telefono_limpio)
        print(f"🛡️ Seguridad: bloqueado={bloqueado} | estudiante={estudiante} | estado={getattr(estudiante, 'estado_onboarding', 'N/A')}", flush=True)
        
        # Default safety - will be overwritten by any branch below
        texto_respuesta = "Escribe *menú* para ver las opciones disponibles."
        
        if bloqueado:
            print(f"🛡️ Bloqueado por seguridad/habeas data", flush=True)
            texto_respuesta = respuesta_seguridad
        else:
            # 3.5a PRIORIDAD: Si está respondiendo al TUTOR IA
            if estudiante.estado_onboarding == 'esperando_respuesta_tutor_ia':
                from .gamificacion import PerfilGamificacion
                print(f"🎓 Evaluando respuesta del Profesor Gerónimo")
                ctx = estudiante.contexto_temporal or {}
                modulo_id = ctx.get('modulo_id')
                pregunta_tutor = ctx.get('pregunta_tutor', '')
                intentos = ctx.get('intentos_tutor', 0)
                
                # Detectar si el usuario quiere omitir el tutor
                msg_lower = msg_body.strip().lower()
                palabras_skip = ['listo', 'continuar', 'saltar', 'omitir', 'siguiente', 'pasar', 'menu', 'menú']
                
                if any(p in msg_lower for p in palabras_skip):
                    # Usuario quiere seguir sin responder al tutor
                    estudiante.contexto_temporal = None
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    print(f"⏭️ Profesor Gerónimo omitido por usuario")
                    
                    # Si dijo "menu", mostrar el menú principal
                    if msg_lower in ['menu', 'menú']:
                        from .response_templates import get_response_for_intent
                        texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
                    elif msg_lower in ['continuar', 'listo', 'siguiente', 'avanzar', 'pasar']:
                        # Enviar siguiente módulo directamente sin ack
                        from .models import ProgresoEstudiante, Modulo
                        try:
                            progreso_id = ctx.get('progreso_id')
                            progreso = ProgresoEstudiante.objects.get(id=progreso_id) if progreso_id else None
                            if progreso and progreso.modulo_actual:
                                from .response_templates import obtener_video_url
                                mod = progreso.modulo_actual
                                video_url = obtener_video_url(mod)
                                archivos_multimedia = mod.archivos_multimedia.filter(activo=True)
                                archivos_msg = ""
                                primera_media_url = None
                                if archivos_multimedia.exists():
                                    archivos_msg = f"\n\n📁 *{archivos_multimedia.count()} archivo(s) multimedia*"
                                    for idx, archivo in enumerate(archivos_multimedia[:3]):
                                        icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                        url = archivo.get_url_para_envio()
                                        if idx == 0 and url and archivo.tipo in ['imagen', 'video'] and not primera_media_url:
                                            primera_media_url = url
                                if not archivos_multimedia.exists() and video_url:
                                    primera_media_url = video_url
                                texto_respuesta = (
                                    f"📖 *Módulo {mod.numero}: {mod.titulo}*\n\n"
                                    f"{mod.descripcion}\n\n"
                                    f"{mod.contenido}{archivos_msg}\n\n\n"
                                    f"Cuando termines, escribe: *\"listo\"*"
                                )
                                if primera_media_url:
                                    texto_respuesta += f"\n\n[MEDIA:{primera_media_url}]"
                            else:
                                texto_respuesta = "Escribe *\"listo\"* cuando termines el módulo."
                        except Exception:
                            texto_respuesta = "Escribe *\"listo\"* cuando termines el módulo."
                    else:
                        texto_respuesta = "Escribe *\"listo\"* cuando termines el módulo."
                else:
                    from .tutor_ia_modulo import evaluar_respuesta_modulo
                    from .models import Modulo
                    
                    try:
                        modulo = Modulo.objects.get(id=modulo_id) if modulo_id else None
                    except Modulo.DoesNotExist:
                        modulo = None
                    
                    if modulo:
                        aprobado, feedback = evaluar_respuesta_modulo(
                            modulo, msg_body, pregunta_tutor,
                            estudiante_nombre=estudiante.nombre or "Estudiante"
                        )
                        
                        if aprobado:
                            # Dar bonus por respuesta correcta
                            perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                            perfil.agregar_puntos(10, "Respuesta correcta - Profesor Gerónimo")
                            estudiante.contexto_temporal = None
                            estudiante.estado_onboarding = 'completado'
                            estudiante.save()
                            texto_respuesta = f"{feedback}\n\n💰 *+10 puntos bonus* por tu respuesta 💪\n\nCuando termines el módulo, escribe: *\"listo\"*"
                        else:
                            intentos += 1
                            if intentos >= 2:
                                # Auto-avanzar después de 2 intentos fallidos
                                estudiante.contexto_temporal = None
                                estudiante.estado_onboarding = 'completado'
                                estudiante.save()
                                texto_respuesta = f"{feedback}\n\n✅ *¡Buen esfuerzo!* Sigue estudiando el módulo.\n\nCuando termines, escribe: *\"listo\"*"
                            else:
                                # Permitir reintento (máx 2)
                                ctx['intentos_tutor'] = intentos
                                estudiante.contexto_temporal = ctx
                                estudiante.save()
                                texto_respuesta = f"{feedback}\n\n💬 _Intenta de nuevo o escribe *\"continuar\"* para seguir._"
                    else:
                        estudiante.contexto_temporal = None
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save()
                        texto_respuesta = "✅ ¡Gracias por tu respuesta! Escribe *\"listo\"* para continuar."
            
            # 3.5a2 PRIORIDAD: Si está respondiendo a la REVISIÓN DE PROGRESO
            elif estudiante.estado_onboarding == 'esperando_respuesta_progreso':
                from .gamificacion import PerfilGamificacion
                print(f"�‍🏫 Evaluando respuesta de María (Revisión de Progreso)")
                ctx = estudiante.contexto_temporal or {}
                pregunta_tutor = ctx.get('pregunta_tutor', '')
                modulos_info = ctx.get('modulos_info', '')
                intentos = ctx.get('intentos_tutor', 0)
                
                # Detectar si el usuario quiere omitir
                msg_lower = msg_body.strip().lower()
                palabras_skip = ['listo', 'continuar', 'saltar', 'omitir', 'siguiente', 'pasar', 'menu', 'menú']
                
                if any(p in msg_lower for p in palabras_skip):
                    estudiante.contexto_temporal = None
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    print(f"⏭️ María (revisión progreso) omitida por usuario")
                    
                    if msg_lower in ['menu', 'menú']:
                        from .response_templates import get_response_for_intent
                        texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
                    elif msg_lower in ['continuar', 'listo', 'siguiente', 'avanzar', 'pasar']:
                        # Enviar siguiente módulo directamente sin ack
                        from .models import ProgresoEstudiante
                        try:
                            progreso_id = ctx.get('progreso_id')
                            progreso = ProgresoEstudiante.objects.get(id=progreso_id) if progreso_id else None
                            if progreso and progreso.modulo_actual:
                                from .response_templates import obtener_video_url
                                mod = progreso.modulo_actual
                                video_url = obtener_video_url(mod)
                                archivos_multimedia = mod.archivos_multimedia.filter(activo=True)
                                archivos_msg = ""
                                primera_media_url = None
                                if archivos_multimedia.exists():
                                    archivos_msg = f"\n\n📁 *{archivos_multimedia.count()} archivo(s) multimedia*"
                                    for idx, archivo in enumerate(archivos_multimedia[:3]):
                                        icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                        url = archivo.get_url_para_envio()
                                        if idx == 0 and url and archivo.tipo in ['imagen', 'video'] and not primera_media_url:
                                            primera_media_url = url
                                if not archivos_multimedia.exists() and video_url:
                                    primera_media_url = video_url
                                texto_respuesta = (
                                    f"📖 *Módulo {mod.numero}: {mod.titulo}*\n\n"
                                    f"{mod.descripcion}\n\n"
                                    f"{mod.contenido}{archivos_msg}\n\n\n"
                                    f"Cuando termines, escribe: *\"listo\"*"
                                )
                                if primera_media_url:
                                    texto_respuesta += f"\n\n[MEDIA:{primera_media_url}]"
                            else:
                                texto_respuesta = "Escribe *\"listo\"* cuando termines el módulo."
                        except Exception:
                            texto_respuesta = "Escribe *\"listo\"* cuando termines el módulo."
                    else:
                        texto_respuesta = "Escribe *\"listo\"* cuando termines el módulo."
                else:
                    from .tutor_ia_modulo import evaluar_respuesta_progreso
                    
                    resuelta, feedback = evaluar_respuesta_progreso(
                        modulos_info, msg_body, pregunta_tutor,
                        estudiante_nombre=estudiante.nombre or "Estudiante"
                    )
                    
                    if resuelta:
                        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
                        perfil.agregar_puntos(5, "Revisión de progreso - María")
                        estudiante.contexto_temporal = None
                        estudiante.estado_onboarding = 'completado'
                        estudiante.save()
                        texto_respuesta = f"{feedback}\n\n💰 *+5 puntos* por tu reflexión 💪\n\nCuando termines el módulo, escribe: *\"listo\"*"
                    else:
                        intentos += 1
                        if intentos >= 2:
                            estudiante.contexto_temporal = None
                            estudiante.estado_onboarding = 'completado'
                            estudiante.save()
                            texto_respuesta = f"{feedback}\n\n✅ *¡Buena reflexión!* Sigue con el módulo.\n\nCuando termines, escribe: *\"listo\"*"
                        else:
                            ctx['intentos_tutor'] = intentos
                            estudiante.contexto_temporal = ctx
                            estudiante.save()
                            texto_respuesta = f"{feedback}\n\n💬 _Cuéntame más o escribe *\"continuar\"* para seguir._"

            # 3.5b PRIORIDAD: Si está respondiendo pregunta de módulo (examen clásico)
            elif estudiante.estado_onboarding == 'esperando_respuesta_modulo':
                # Si el usuario dice "menu", salir del examen y mostrar menú
                msg_lower_exam = msg_body.strip().lower()
                if msg_lower_exam in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.save()
                    from .response_templates import get_response_for_intent
                    texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
                else:
                    # Validar respuesta a pregunta de módulo
                    from .pregunta_handler import validar_respuesta, procesar_respuesta_abierta_ia
                    print(f"📝 Validando respuesta a pregunta de módulo")
                    
                    # Verificar si la pregunta es abierta (IA) o de opciones
                    ctx = estudiante.contexto_temporal or {}
                    es_pregunta_ia = ctx.get('tipo') == 'pregunta_tutor_ia'
                    
                    # Fallback: verificar ultima_pregunta_data si contexto no tiene tipo IA
                    if not es_pregunta_ia:
                        pregunta_data = None
                        if hasattr(estudiante, 'ultima_pregunta_data') and estudiante.ultima_pregunta_data:
                            import ast
                            try:
                                pregunta_data = ast.literal_eval(estudiante.ultima_pregunta_data)
                            except Exception:
                                pregunta_data = None
                        if pregunta_data and (not pregunta_data.get('opciones')):
                            es_pregunta_ia = True
                    
                    if es_pregunta_ia:
                        # Pregunta IA abierta — evaluar con IA
                        es_correcta, mensaje_respuesta = procesar_respuesta_abierta_ia(estudiante, msg_body)
                        modulo_completado = None
                    else:
                        es_correcta, mensaje_respuesta, modulo_completado = validar_respuesta(estudiante, msg_body)

                    # Obtener progreso para avanzar al siguiente módulo
                    if modulo_completado or es_pregunta_ia:
                        from .helpers_examenes import puede_avanzar_modulo
                        
                        if modulo_completado:
                            progreso = modulo_completado.progreso
                            modulo_actual = modulo_completado.modulo
                        else:
                            # Para preguntas IA abierta, obtener progreso desde contexto
                            from .models import ProgresoEstudiante, Modulo
                            modulo_id = ctx.get('modulo_id')
                            progreso_id = ctx.get('progreso_id')
                            try:
                                modulo_actual = Modulo.objects.get(id=modulo_id) if modulo_id else None
                                progreso = ProgresoEstudiante.objects.get(id=progreso_id) if progreso_id else None
                            except Exception:
                                modulo_actual = None
                                progreso = None
                            
                            if progreso and modulo_actual:
                                # Crear ModuloCompletado para la pregunta IA abierta
                                ModuloCompletado.objects.get_or_create(
                                    progreso=progreso,
                                    modulo=modulo_actual
                                )
                        
                        _skip_avance = False
                        if not (progreso and modulo_actual):
                            texto_respuesta = mensaje_respuesta
                            _skip_avance = True
                        
                        if not _skip_avance:
                            # VERIFICAR EXAMEN OBLIGATORIO ANTES DE AVANZAR
                            puede_avanzar, mensaje_examen, detalles = puede_avanzar_modulo(estudiante, modulo_actual)
                        
                            if not puede_avanzar:
                                # NO puede avanzar - examen obligatorio no aprobado
                                mensaje_respuesta += f"""


🔒 *Examen Obligatorio*

{mensaje_examen}

Para continuar al siguiente módulo debes aprobar el examen de este módulo.

Escribe *"examen"* cuando estés listo para intentarlo."""
                            
                                texto_respuesta = mensaje_respuesta
                                # Fall through to Twilio API send
                        
                            else:
                                # Buscar siguiente módulo
                                siguiente_modulo = progreso.curso.modulos.filter(
                                    numero__gt=modulo_actual.numero
                                ).order_by('numero').first()
                            
                                if siguiente_modulo:
                                    # Actualizar progreso al siguiente módulo
                                    progreso.modulo_actual = siguiente_modulo
                                    progreso.save()
                                
                                    # Resetear preguntas IA para nuevo módulo
                                    estudiante.preguntas_ia_restantes = 3
                                    estudiante.save()
                                
                                    porcentaje = progreso.porcentaje_avance()
                                    from .response_templates import obtener_video_url
                                    video_url = obtener_video_url(siguiente_modulo)
                                
                                    # Verificar si tiene archivos multimedia
                                    archivos_multimedia = siguiente_modulo.archivos_multimedia.filter(activo=True)
                                    print(f"🔍 Archivos multimedia para módulo {siguiente_modulo.titulo}: {archivos_multimedia.count()}")
                                    archivos_msg = ""
                                    primera_media_url = None
                                
                                    if archivos_multimedia.exists():
                                        print(f"✅ Encontrados {archivos_multimedia.count()} archivos multimedia")
                                        archivos_msg = f"\n\n📁 *{archivos_multimedia.count()} archivo(s) multimedia*"
                                        for idx, archivo in enumerate(archivos_multimedia[:3]):
                                            icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                            url = archivo.get_url_para_envio()
                                            if url:
                                                print(f"📎 URL para envío: {url}")
                                            else:
                                                print(f"⚠️ Archivo sin URL disponible para envío")
                                            if idx == 0 and url and archivo.tipo in ['imagen', 'video'] and not primera_media_url:
                                                primera_media_url = url
                                                print(f"🖼️ Primera media detectada: {archivo.tipo} - {url}")
                                                archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                            elif url:
                                                archivos_msg += f"\n{icono} {archivo.titulo}"
                                            else:
                                                archivos_msg += f"\n{icono} {archivo.titulo}"

                                    # Refuerzo: si NO hay archivos multimedia pero hay video_url, igual agregarlo como media
                                    if not archivos_multimedia.exists() and video_url:
                                        print(f"🎥 Refuerzo: agregando video_url como media: {video_url}")
                                        primera_media_url = video_url
                                
                                    # Mensaje 1: Resultado del examen (mensaje_respuesta ya tiene la info)
                                    msg_completado = mensaje_respuesta
                                
                                    # Mensaje 2: Siguiente módulo (separado)
                                    msg_modulo = f"""

Progreso del curso: {porcentaje}%

📖 *Módulo {siguiente_modulo.numero}: {siguiente_modulo.titulo}*

{siguiente_modulo.descripcion}

{siguiente_modulo.contenido}{archivos_msg}


Cuando termines, escribe: *"listo"*"""
                                
                                    if primera_media_url:
                                        msg_modulo += f"\n\n[MEDIA:{primera_media_url}]"
                                        print(f"🖼️ Multimedia agregada al mensaje: {primera_media_url}")
                                
                                    if siguiente_modulo.examen_obligatorio:
                                        msg_modulo += f"\n\n⚠️ *Este módulo tiene examen obligatorio ({siguiente_modulo.puntaje_minimo_aprobacion}% para aprobar)*"
                                
                                    # === AGENTES: Tutor (impares) / Asistente (módulo 4 solamente) ===
                                    tutor_msg = None
                                    maria_msg = None
                                    nombre_tutor = progreso.curso.nombre_agente_tutor or 'Gerónimo'
                                    nombre_asistente = progreso.curso.nombre_agente_asistente or 'María'
                                
                                    # Profesor (Tutor): enseñanza complementaria (módulos impares: 1,3,5,7,9)
                                    if modulo_actual.numero % 2 == 1:
                                        try:
                                            from .tutor_ia_modulo import generar_enseñanza_modulo
                                            enseñanza = generar_enseñanza_modulo(
                                                modulo_actual,
                                                estudiante_nombre=estudiante.nombre or "Estudiante"
                                            )
                                            if enseñanza:
                                                tutor_msg = f"🎓 *{nombre_tutor}*\n\n{enseñanza}\n\n💬 _Escríbeme o envía un audio con tu respuesta. Si decides seguir con el módulo, en el audio o texto di *continuar*_"
                                                print(f"🎓 {nombre_tutor} activado después de módulo {modulo_actual.numero}", flush=True)
                                        except Exception as e:
                                            import logging
                                            logging.getLogger(__name__).warning(f"⚠️ {nombre_tutor} falló: {e}")
                                
                                    # Asistente: revisión de progreso SOLO en módulo 4
                                    if modulo_actual.numero == 4:
                                        try:
                                            from .tutor_ia_modulo import generar_revision_progreso
                                            modulos_completados_qs = progreso.modulos_completados.all().order_by('modulo__numero')
                                            modulos_obj = [mc.modulo for mc in modulos_completados_qs]
                                            revision = generar_revision_progreso(
                                                modulo_actual,
                                                modulos_obj,
                                                progreso.curso.nombre,
                                                estudiante_nombre=estudiante.nombre or "Estudiante"
                                            )
                                            if revision:
                                                maria_msg = f"👩‍🏫 *{nombre_asistente} — Tu Asistente*\n\n{revision}\n\n💬 _Escríbeme o envía un audio con tu respuesta. Si decides seguir con el módulo, en el audio o texto di *continuar*_"
                                                print(f"👩‍🏫 {nombre_asistente} activada después de módulo {modulo_actual.numero}", flush=True)
                                        except Exception as e:
                                            import logging
                                            logging.getLogger(__name__).warning(f"⚠️ {nombre_asistente} falló: {e}")
                                
                                    # Establecer estado para el PRIMER agente que responda (Gerónimo tiene prioridad)
                                    if tutor_msg:
                                        estudiante.contexto_temporal = {
                                            'tipo': 'tutor_ia_modulo',
                                            'modulo_id': modulo_actual.id,
                                            'pregunta_tutor': enseñanza,
                                            'progreso_id': progreso.id,
                                            'intentos_tutor': 0,
                                        }
                                        estudiante.estado_onboarding = 'esperando_respuesta_tutor_ia'
                                        estudiante.save()
                                    elif maria_msg:
                                        modulos_info_str = ", ".join([m.titulo for m in modulos_obj])
                                        estudiante.contexto_temporal = {
                                            'tipo': 'revision_progreso',
                                            'modulo_id': modulo_actual.id,
                                            'pregunta_tutor': revision,
                                            'progreso_id': progreso.id,
                                            'modulos_info': modulos_info_str,
                                            'intentos_tutor': 0,
                                        }
                                        estudiante.estado_onboarding = 'esperando_respuesta_progreso'
                                        estudiante.save()
                                    else:
                                        estudiante.estado_onboarding = 'completado'
                                        estudiante.save()
                                
                                    # Construir respuesta multi-mensaje
                                    partes = [msg_completado, msg_modulo]
                                    if tutor_msg:
                                        partes.append(tutor_msg)
                                    if maria_msg:
                                        partes.append(maria_msg)
                                    texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes)
                            
                                else:
                                    # Completó todos los módulos
                                    progreso.completado = True
                                    progreso.fecha_completado = timezone.now()
                                    progreso.save()
                                
                                    estudiante.estado_onboarding = 'completado'
                                    estudiante.save()
                                
                                    msg_final = mensaje_respuesta + f"""


🎓 *¡FELICITACIONES!*

Has completado el curso: *{progreso.curso.nombre}*

🏆 Certificado disponible en tu perfil

*¿Qué deseas hacer ahora?*

1️⃣ Ver otros cursos
2️⃣ Ver mi progreso
3️⃣ Menú principal"""
                                
                                    # Asistente: Resumen completo del curso
                                    nombre_asistente_fin = progreso.curso.nombre_agente_asistente or 'María'
                                    msg_resumen = None
                                    try:
                                        from .tutor_ia_modulo import generar_resumen_curso_completo
                                        modulos_completados_qs = progreso.modulos_completados.all().order_by('modulo__numero')
                                        modulos_obj = [mc.modulo for mc in modulos_completados_qs]
                                        resumen_maria = generar_resumen_curso_completo(
                                            progreso.curso.nombre,
                                            modulos_obj,
                                            estudiante_nombre=estudiante.nombre or "Estudiante"
                                        )
                                        if resumen_maria:
                                            msg_resumen = f"👩‍🏫 *{nombre_asistente_fin} — Resumen del Curso*\n\n{resumen_maria}"
                                            print(f"👩‍🏫 {nombre_asistente_fin} resumen del curso activada", flush=True)
                                    except Exception as e:
                                        import logging
                                        logging.getLogger(__name__).warning(f"⚠️ María resumen falló: {e}")
                                
                                    # Imagen de certificado — generar con nombre del estudiante
                                    msg_cert_img = ""
                                    try:
                                        from .certificado_service import crear_certificado_automatico
                                        cert = crear_certificado_automatico(estudiante, progreso.curso)
                                        if cert and cert.archivo_imagen:
                                            # Usar URL pública directa (AWS_DEFAULT_ACL=public-read)
                                            cert_url = cert.archivo_imagen.url
                                            msg_cert_img = f"🎓 *¡Tu certificado!*\n\n[MEDIA:{cert_url}]"
                                            logger.info(f"Certificado imagen URL pública: {cert_url[:80]}...")
                                        elif cert and cert.archivo_pdf:
                                            cert_url = cert.archivo_pdf.url
                                            msg_cert_img = f"🎓 *¡Tu certificado!*\n📄 Descárgalo aquí: {cert_url}"
                                            logger.info(f"Certificado PDF URL pública: {cert_url[:80]}...")
                                        else:
                                            msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                                            logger.warning(f"Certificado creado pero sin archivo para {estudiante.nombre}")
                                    except Exception as e:
                                        logger.error(f"Error generando certificado: {e}")
                                        msg_cert_img = "🎓 Tu certificado se está generando. Te lo enviaremos pronto."
                                
                                    # Construir multi-mensaje
                                    partes = []
                                    if msg_resumen:
                                        partes.append(msg_resumen)
                                    partes.append(msg_final)
                                    partes.append(msg_cert_img)
                                    texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes)
                    
                    if not texto_respuesta:
                        texto_respuesta = mensaje_respuesta
                    print(f"✅ Respuesta validada: {'Correcta' if es_correcta else 'Incorrecta'}")
            
            # 3.5c PRIORIDAD: Si está seleccionando un curso de la lista
            elif estudiante.estado_onboarding == 'esperando_seleccion_curso':
                msg_sel = msg_body.strip().lower()
                if msg_sel in ['menu', 'menú']:
                    estudiante.estado_onboarding = 'completado'
                    estudiante.contexto_temporal = None
                    estudiante.save()
                    from .response_templates import get_response_for_intent
                    texto_respuesta = get_response_for_intent('saludo', estudiante.nombre, estudiante_id=estudiante.id)
                elif msg_body.strip().isdigit():
                    indice = int(msg_body.strip())
                    from .selector_curso import continuar_curso_seleccionado
                    estudiante.estado_onboarding = 'completado'
                    estudiante.contexto_temporal = None
                    estudiante.save()
                    texto_respuesta = continuar_curso_seleccionado(estudiante.id, indice, msg_body)
                    print(f"✅ Curso seleccionado: {indice}")
                else:
                    # Si no es número ni menu, resetear estado y procesar normalmente
                    estudiante.estado_onboarding = 'completado'
                    estudiante.contexto_temporal = None
                    estudiante.save()
                    from .intent_detector import detect_intent
                    from .response_templates import get_response_for_intent
                    intent = detect_intent(msg_body)
                    if intent != 'desconocido':
                        texto_respuesta = get_response_for_intent(intent, estudiante.nombre, estudiante_id=estudiante.id, mensaje_original=msg_body)
                    else:
                        texto_respuesta = "No entendí tu selección. Escribe *menú* para ver las opciones."
            
            # 4. Detectar intent y usar templates primero
            else:
                from .intent_detector import detect_intent
                from .response_templates import get_response_for_intent
                
                intent = detect_intent(msg_body)
                print(f"🎯 Intent detectado: {intent}")
            
                # Intent especial: corregir datos → redirigir al flujo de corrección
                if intent == 'corregir_datos':
                    estudiante.estado_chat = 'ESPERANDO_CORRECCION_DATOS'
                    estudiante.save()
                    texto_respuesta = (
                        "📝 *Corrección de Datos*\n\n"
                        "Puedes corregir cualquiera de tus datos.\n\n"
                        "Escribe el campo que deseas cambiar seguido del nuevo valor:\n\n"
                        "1️⃣ *nombre:* Tu nombre completo\n"
                        "2️⃣ *municipio:* Tu municipio\n"
                        "3️⃣ *departamento:* Tu departamento\n"
                        "4️⃣ *documento:* Tipo y número (CC, TI, CE, PP)\n"
                        "5️⃣ *edad:* Tu edad\n"
                        "6️⃣ *genero:* M, F, Otro, NR\n\n"
                        "📝 _Ejemplos:_\n"
                        "_nombre: María García López_\n"
                        "_municipio: Bogotá_\n"
                        "_edad: 35_\n\n"
                        "👉 Escribe *menú* cuando termines"
                    )
                # Si hay un intent conocido, usar template
                elif intent != 'desconocido':
                    texto_respuesta = get_response_for_intent(
                        intent, 
                        estudiante.nombre,
                        estudiante_id=estudiante.id,
                        mensaje_original=msg_body
                    )
                    print(f"✅ Respuesta desde template: {texto_respuesta[:50]}...")
                else:
                    # Solo si no hay intent, usar IA para preguntas sobre agricultura
                    # 🛑 ANTI-ABUSO IA: Verificar preguntas restantes
                    print(f"🤖 Usando IA para pregunta sobre agricultura")
                    if estudiante.preguntas_ia_restantes <= 0:
                        # Freno de mano: IA pausada
                        texto_respuesta = (
                            "⚠️ *Has agotado tus preguntas libres a la IA para este módulo.*\n\n"
                            "Para desbloquear más preguntas, necesitas responder "
                            "la pregunta de evaluación del módulo actual.\n\n"
                            "📝 Escribe *\"listo\"* para continuar con tu módulo\n"
                            "📚 Escribe *\"mis cursos\"* para ver los cursos disponibles"
                        )
                    else:
                        try:
                            from .ai_assistant import responder_con_ia
                            texto_respuesta = responder_con_ia(msg_body, telefono_limpio)
                            # Restar pregunta usada
                            estudiante.preguntas_ia_restantes = max(0, estudiante.preguntas_ia_restantes - 1)
                            estudiante.save()
                            restantes = estudiante.preguntas_ia_restantes
                            if restantes > 0:
                                texto_respuesta += f"\n\n💡 _Te quedan {restantes} preguntas libres a la IA en este módulo._"
                            else:
                                texto_respuesta += "\n\n⚠️ _Esta fue tu última pregunta libre. Responde la evaluación del módulo para desbloquear más._"
                            print(f"✅ IA generó respuesta: {texto_respuesta[:50]}...")
                        except Exception as e:
                            print(f"❌ Error IA: {e}, usando respuesta genérica")
                            texto_respuesta = "Disculpa, tengo problemas técnicos. Escribe 'menú' para ver las opciones."
        
        # 3. Enviar respuesta via Twilio
        print(f"📤 ENVIANDO RESPUESTA: '{texto_respuesta[:80]}...' (len={len(texto_respuesta)})", flush=True)
        # Detectar si hay media_url en la respuesta (marcado con [MEDIA:url])
        media_url_to_send = None
        if '[MEDIA:' in texto_respuesta:
            import re
            media_match = re.search(r'\[MEDIA:(.*?)\]', texto_respuesta)
            if media_match:
                media_url_to_send = media_match.group(1)
                texto_respuesta = texto_respuesta.replace(media_match.group(0), '').strip()
                print(f"🖼️ Media URL detectada: {media_url_to_send}")
        
        try:
            from twilio.rest import Client
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
            twilio_number = str(twilio_number).strip()
            print(f"DEBUG TWILIO FROM (views.py): '{twilio_number}'")
            
            if not account_sid or not auth_token:
                print("❌ Credenciales Twilio faltantes")
                return
            
            client = Client(account_sid, auth_token)

            # Usar el teléfono original (con +) para enviar por Twilio
            destino_formateado = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
            destino_formateado = str(destino_formateado).strip()
            
            # Check if response is a multi-message (marked with [MULTI_MSG])
            if texto_respuesta.startswith('[MULTI_MSG]'):
                # Extract and send multiple messages
                partes = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                
                for idx, parte in enumerate(partes):
                    if not parte.strip():
                        continue
                    
                    parte_texto = parte.strip()
                    parte_media = None
                    
                    # Extraer [MEDIA:url] de esta parte
                    if '[MEDIA:' in parte_texto:
                        import re
                        media_match_p = re.search(r'\[MEDIA:(.*?)\]', parte_texto)
                        if media_match_p:
                            parte_media = media_match_p.group(1).strip()
                            parte_texto = parte_texto.replace(media_match_p.group(0), '').strip()
                            print(f"🖼️ Media en parte {idx+1}: {parte_media}")
                    
                    msg_params = {
                        'body': parte_texto,
                        'from_': twilio_number,
                        'to': destino_formateado
                    }
                    if parte_media:
                        msg_params['media_url'] = [parte_media]
                    
                    try:
                        mensaje = client.messages.create(**msg_params)
                    except Exception as media_err:
                        # Error 63019 = Media download failed — retry without media
                        err_str = str(media_err)
                        if '63019' in err_str and parte_media:
                            print(f"⚠️ Error 63019 en parte {idx+1}, reenviando sin media...")
                            msg_params.pop('media_url', None)
                            msg_params['body'] += f"\n\n📎 Video: {parte_media}"
                            mensaje = client.messages.create(**msg_params)
                        else:
                            raise
                    
                    print(f"✅ Mensaje {idx+1}/{len(partes)} enviado via Twilio: {mensaje.sid}")
                    
                    # Guardar log de respuesta con teléfono limpio
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=parte_texto,
                        mensaje_id=mensaje.sid,
                        tipo='SENT'
                    )
                    print(f"✅ Guardado SENT")
                    
                    # Small delay between messages to avoid rate limiting
                    import time
                    time.sleep(0.5)
            else:
                # Single message (original behavior)
                message_params = {
                    'body': texto_respuesta,
                    'from_': twilio_number,
                    'to': destino_formateado
                }
                
                # Agregar media_url si existe
                if media_url_to_send:
                    clean_media_url = str(media_url_to_send).strip()
                    message_params['media_url'] = [clean_media_url]
                    print(f"🖼️ Enviando mensaje con multimedia: {clean_media_url}")
                
                try:
                    mensaje = client.messages.create(**message_params)
                except Exception as media_err:
                    err_str = str(media_err)
                    if '63019' in err_str and media_url_to_send:
                        print(f"⚠️ Error 63019, reenviando sin media...")
                        message_params.pop('media_url', None)
                        message_params['body'] += f"\n\n📎 Video: {clean_media_url}"
                        mensaje = client.messages.create(**message_params)
                    else:
                        raise
                
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
        
        # ============================================================
        # SAFETY NET: Siempre enviar ALGO al usuario, nunca quedar mudo
        # ============================================================
        try:
            msg_from_fallback = post_data.get('From', '')
            if msg_from_fallback:
                from twilio.rest import Client
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                twilio_number = str(twilio_number).strip()
                
                if account_sid and auth_token:
                    client = Client(account_sid, auth_token)
                    destino = f'whatsapp:{msg_from_fallback}' if not msg_from_fallback.startswith('whatsapp:') else msg_from_fallback
                    destino = str(destino).strip()
                    client.messages.create(
                        body="⚠️ Tuvimos un problema técnico momentáneo. Por favor escribe *menú* para continuar.",
                        from_=twilio_number,
                        to=destino
                    )
                    print(f"✅ Safety net: mensaje de error enviado a {destino}")
        except Exception as fallback_err:
            print(f"❌ Safety net también falló: {fallback_err}")


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
                        defaults={'nombre': 'Usuario', 'activo': True, 'cedula': f'META_{phone[-10:]}'}
                    )
                    
                    # Verificar seguridad primero
                    from .security_handler import verificar_seguridad_completa
                    bloqueado, respuesta_seguridad, estudiante = verificar_seguridad_completa(estudiante, text, telefono=phone)
                    
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
                    from_=getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806'),
                    to=telefono_whatsapp
                )
            else:
                # Preparar parámetros del mensaje libre
                params = {
                    "to": telefono_whatsapp,
                    "from_": getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806'),
                    "body": mensaje_texto
                }
                
                # Si es mensaje con imagen/video, generar URL firmada y agregar media_url
                if tipo_mensaje == 'imagen' and url_imagen:
                    # Revisar si la URL es de S3 y necesita firma
                    from core.utils import generar_url_firmada_s3_v4
                    import re
                    s3_pattern = r'https://([\w\-]+)\.s3[\w\-\.]*\.amazonaws\.com/(.+)'
                    match = re.match(s3_pattern, url_imagen)
                    if match:
                        bucket_name = match.group(1)
                        object_name = match.group(2)
                        url_firmada = generar_url_firmada_s3_v4(bucket_name, object_name)
                        params["media_url"] = [url_firmada]
                    else:
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
    from django.db.models import Max, Count, Q
    # Obtener estudiantes con mensajes usando anotaciones (evita N+1)
    estudiantes_con_mensajes = []

    # Pre-calcular conteos y últimas fechas con anotaciones
    todos_estudiantes = (
        Estudiante.objects.all()
        .annotate(
            total_whatsapp=Count(
                'mensajes_whatsapp',
                distinct=True,
            ),
            total_envios=Count(
                'enviolog',
                distinct=True,
            ),
            last_whatsapp_fecha=Max('mensajes_whatsapp__fecha'),
            last_envio_fecha=Max('enviolog__fecha_envio'),
        )
        .filter(Q(total_whatsapp__gt=0) | Q(total_envios__gt=0))
    )

    for est in todos_estudiantes:
        try:
            telefono_limpio = est.telefono.replace('+', '').replace(' ', '')
            total_msgs = est.total_whatsapp + est.total_envios

            # Obtener último mensaje (solo 2 queries, no N por estudiante)
            ultimo_whatsapp = None
            ultimo_envio = None
            if est.last_whatsapp_fecha:
                ultimo_whatsapp = WhatsappLog.objects.filter(
                    telefono=telefono_limpio,
                    fecha=est.last_whatsapp_fecha
                ).first()
            if est.last_envio_fecha:
                ultimo_envio = EnvioLog.objects.filter(
                    estudiante=est,
                    fecha_envio=est.last_envio_fecha
                ).select_related('campana').first()

            # Determinar cuál es más reciente
            ultima_fecha = None
            ultimo_mensaje = None

            if ultimo_whatsapp and ultimo_envio:
                fecha_whatsapp = ultimo_whatsapp.fecha
                fecha_envio = ultimo_envio.fecha_envio
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
            est.total_mensajes = total_msgs
            estudiantes_con_mensajes.append(est)
        except Exception as e:
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
                    'tipo': 'recibido' if msg.tipo == 'INCOMING' else 'enviado'
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
                'url_proxy': archivo.get_url_para_envio(),
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


def stream_media(request):
    """Proxy simple para servir archivos multimedia almacenados (oculta la URL S3).

    Parámetros: ?path=<ruta_relativa_en_storage>
    Ej: /media/stream/?path=modulos/2026/02/video.mp4
    """
    path = request.GET.get('path')
    if not path:
        return HttpResponseBadRequest('Falta parámetro path')

    # Normalizar y evitar traversal
    path = path.lstrip('/')
    if '..' in path:
        return HttpResponseBadRequest('Ruta inválida')

    try:
        f = default_storage.open(path, 'rb')
        content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        return FileResponse(f, content_type=content_type)
    except Exception:
        return HttpResponse(status=404)


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
            modelo_ia = request.POST.get('modelo_ia', 'gpt-4o-mini')
            
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
    modelo_usado = request.session.get('modelo_usado', 'gpt-4o-mini')
    
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
