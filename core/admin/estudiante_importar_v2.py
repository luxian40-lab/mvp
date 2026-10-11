"""Vista previa de la importación que ya existe. No crea otro importador.

El guardado sigue siendo update_or_create por documento, como
EstudianteAdmin.importar_estudiantes_view. El curso solo se acepta si
está en cursos_permitidos.
"""
from __future__ import annotations

import csv
import io

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import redirect, render

from core.documento_identidad import normalizar_numero_documento, normalizar_tipo_documento
from core.import_estudiantes_excel import extraer_fila_estudiante, mapear_columnas_estudiante
from core.utils_telefono import normalizar_telefono, validar_telefono_whatsapp

SESION = 'eki_import_est_v2'
MENSAJE_CURSO = 'el curso no corresponde a la organización'


def tope_filas() -> int:
    try:
        return max(1, int(getattr(settings, 'ADMIN_ESTUDIANTE_IMPORT_MAX', 500) or 500))
    except (TypeError, ValueError):
        return 500


def responder_importacion(admin, request):
    if request.method == 'GET' and request.GET.get('errores') == '1':
        return _csv_errores(request)
    if request.method != 'POST':
        return _pagina(request, None)
    if request.POST.get('paso') == 'confirmar':
        return _confirmar(admin, request)
    archivo = request.FILES.get('archivo_excel')
    if not archivo:
        messages.error(request, 'Debes seleccionar un archivo Excel o CSV.')
        return redirect('admin:core_estudiante_importar')
    try:
        headers, filas = leer_tabla(archivo)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('admin:core_estudiante_importar')
    preview = evaluar_filas(headers, filas)
    request.session[SESION] = {
        'usuario': request.user.pk,
        'filas': preview,
        'bienvenida': False,
    }
    request.session.modified = True
    return _pagina(request, preview)


def leer_tabla(archivo):
    nombre = (getattr(archivo, 'name', '') or '').lower()
    if nombre.endswith('.csv'):
        texto = archivo.read()
        if isinstance(texto, bytes):
            texto = texto.decode('utf-8-sig')
        lector = csv.reader(io.StringIO(texto))
        filas = [tuple(fila) for fila in lector]
    else:
        import openpyxl
        wb = openpyxl.load_workbook(archivo, data_only=True)
        ws = wb.active
        filas = [tuple(fila) for fila in ws.iter_rows(values_only=True)]
    if not filas:
        raise ValueError('El archivo no tiene filas.')
    headers = ['' if celda is None else str(celda) for celda in filas[0]]
    return headers, filas[1:]


def evaluar_filas(headers, filas) -> list[dict]:
    from core.models import Cliente, Estudiante

    colmap = mapear_columnas_estudiante(headers)
    tiene_tipo = bool(headers) and 'tipo' in (headers[0] or '').lower()
    tope = tope_filas()
    vistos_doc = set()
    vistos_tel = set()
    salida = []
    numero = 1
    for row in filas:
        numero += 1
        if not row or all(celda is None or str(celda).strip() == '' for celda in row):
            continue
        if len(salida) >= tope:
            salida.append(_error(numero, f'Supera el máximo de {tope} filas.'))
            continue
        try:
            campos = extraer_fila_estudiante(row, colmap, tiene_tipo)
        except IndexError:
            salida.append(_error(numero, 'Columnas insuficientes.'))
            continue
        tipo = normalizar_tipo_documento(campos['tipo_raw'] or 'CC')
        cedula = normalizar_numero_documento(campos['cedula'])
        nombre = (campos['nombre'] or '').strip()
        tel_raw = campos['telefono_raw']
        curso_nombre = (campos['curso_nombre'] or '').strip()
        org_nombre = (campos['cliente_nombre'] or '').strip()
        errores = []
        if not cedula:
            errores.append('Documento vacío.')
        if not nombre:
            errores.append('Nombre vacío.')
        if not tel_raw:
            errores.append('Teléfono vacío.')
        check = validar_telefono_whatsapp(tel_raw) if tel_raw else None
        telefono = ''
        if check is not None and not check['ok']:
            errores.append(check['mensaje'])
        elif check is not None:
            telefono = check['telefono'] or normalizar_telefono(tel_raw)
        if cedula and cedula in vistos_doc:
            errores.append('Documento repetido en el archivo.')
        if telefono and telefono in vistos_tel:
            errores.append('Teléfono repetido en el archivo.')
        if cedula:
            vistos_doc.add(cedula)
        if telefono:
            vistos_tel.add(telefono)
        organizacion = None
        if org_nombre:
            coincidencias = list(Cliente.objects.filter(nombre__iexact=org_nombre.strip())[:2])
            if not coincidencias:
                errores.append(f'Organización inexistente: {org_nombre}.')
            elif len(coincidencias) > 1:
                errores.append(f'Hay más de una organización llamada {org_nombre}.')
            else:
                organizacion = coincidencias[0]
        curso_id = None
        if curso_nombre and not any('Organización' in e for e in errores):
            curso, error_curso = _curso_de_fila(curso_nombre, organizacion)
            if error_curso:
                errores.append(error_curso)
            elif curso is not None:
                curso_id = curso.pk
        accion = 'crear'
        if cedula and Estudiante.objects.filter(cedula=cedula).exists():
            accion = 'actualizar'
        if telefono and Estudiante.objects.filter(telefono=telefono).exclude(cedula=cedula).exists():
            errores.append('El teléfono ya está en otra persona.')
        salida.append({
            'fila': numero,
            'ok': not errores,
            'errores': errores,
            'accion': accion if not errores else 'error',
            'tipo_documento': tipo,
            'cedula': cedula,
            'nombre': nombre,
            'telefono': telefono,
            'cliente_id': organizacion.pk if organizacion else None,
            'curso_id': curso_id,
            'curso_nombre': curso_nombre,
            'municipio': campos['municipio'],
            'departamento': campos['departamento'],
            'genero_raw': campos['genero_raw'],
            'edad_raw': campos['edad_raw'],
        })
    return salida


def _curso_de_fila(nombre, organizacion):
    from core.cursos_permitidos import cursos_permitidos
    from core.inscripcion_curso import _norm_nombre_curso

    objetivo = _norm_nombre_curso(nombre)
    hits = []
    for curso in cursos_permitidos(organizacion):
        if _norm_nombre_curso(curso.nombre) == objetivo or curso.nombre.lower() == nombre.strip().lower():
            hits.append(curso)
    if len(hits) == 1:
        return hits[0], None
    if len(hits) > 1:
        return None, 'Hay más de un curso con ese nombre.'
    return None, MENSAJE_CURSO


def _error(fila, texto) -> dict:
    return {
        'fila': fila,
        'ok': False,
        'errores': [texto],
        'accion': 'error',
        'tipo_documento': '',
        'cedula': '',
        'nombre': '',
        'telefono': '',
        'cliente_id': None,
        'curso_id': None,
        'curso_nombre': '',
        'municipio': '',
        'departamento': '',
        'genero_raw': '',
        'edad_raw': '',
    }


def _confirmar(admin, request):
    from django.utils import timezone

    from core.admin.estudiante_bienvenida import enviar_bienvenida_alta
    from core.inscripcion_curso import inscribir_estudiante_en_curso
    from core.models import Cliente, Curso, Estudiante

    paquete = request.session.get(SESION) or {}
    if paquete.get('usuario') != request.user.pk:
        messages.error(request, 'La vista previa venció. Sube el archivo otra vez.')
        return redirect('admin:core_estudiante_importar')
    enviar = request.POST.get('enviar_bienvenida') == '1'
    creados = actualizados = inscritos = errores = 0
    avisos = []
    generos = {
        'm': 'M', 'f': 'F', 'o': 'O', 'masculino': 'M', 'femenino': 'F',
        'otro': 'O', 'hombre': 'M', 'mujer': 'F', 'nr': 'NR', 'no reporta': 'NR',
    }
    for fila in paquete.get('filas') or []:
        if not fila.get('ok'):
            errores += 1
            continue
        cliente = Cliente.objects.filter(pk=fila['cliente_id']).first() if fila.get('cliente_id') else None
        curso = Curso.objects.filter(pk=fila['curso_id']).first() if fila.get('curso_id') else None
        if fila.get('curso_nombre') and curso is None:
            errores += 1
            avisos.append(f"Fila {fila['fila']}: {MENSAJE_CURSO}")
            continue
        if curso is not None:
            from core.cursos_permitidos import curso_esta_permitido
            if not curso_esta_permitido(curso, cliente):
                errores += 1
                avisos.append(f"Fila {fila['fila']}: {MENSAJE_CURSO}")
                continue
        genero = generos.get((fila.get('genero_raw') or '').strip().lower(), '') or 'NR'
        edad = None
        if fila.get('edad_raw'):
            digitos = ''.join(ch for ch in str(fila['edad_raw']) if ch.isdigit())
            if digitos:
                edad = int(digitos)
        defaults = {
            'nombre': (fila.get('nombre') or '').strip().title(),
            'telefono': fila['telefono'],
            'municipio': (fila.get('municipio') or '').strip().lower(),
            'departamento': (fila.get('departamento') or '').strip().lower(),
            'genero': genero,
            'edad': edad,
            'tipo_documento': fila['tipo_documento'] or 'CC',
            'estado_onboarding': 'completado',
            'estado_chat': 'ACTIVO',
            'acepto_terminos': True,
            'activo': True,
        }
        if cliente is not None:
            defaults['cliente'] = cliente
        try:
            estudiante, created = Estudiante.objects.update_or_create(
                cedula=fila['cedula'],
                defaults=defaults,
            )
        except IntegrityError:
            errores += 1
            avisos.append(
                f"Fila {fila['fila']}: el teléfono ya está en otra persona."
            )
            continue
        if created:
            creados += 1
            accion = ADDITION
        else:
            actualizados += 1
            accion = CHANGE
        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=ContentType.objects.get_for_model(Estudiante).pk,
            object_id=str(estudiante.pk),
            object_repr=str(estudiante)[:200],
            action_flag=accion,
            change_message=f"Importación Excel {timezone.now():%Y-%m-%d %H:%M}",
        )
        if curso is not None:
            _progreso, nuevo = inscribir_estudiante_en_curso(estudiante, curso)
            if nuevo:
                inscritos += 1
        if enviar and curso is not None:
            resultado = enviar_bienvenida_alta(estudiante, [curso])
            if not resultado['ok']:
                avisos.append(f"Fila {fila['fila']}: bienvenida no enviada. {resultado['motivo']}")
    request.session.pop(SESION, None)
    if creados:
        messages.success(request, f'{creados} estudiante(s) creado(s).')
    if actualizados:
        messages.info(request, f'{actualizados} estudiante(s) actualizado(s).')
    if inscritos:
        messages.success(request, f'{inscritos} inscripción(es) en cursos.')
    if errores:
        messages.warning(request, f'{errores} fila(s) con error, no se importaron.')
    for aviso in avisos[:8]:
        messages.warning(request, aviso)
    return redirect('admin:core_estudiante_changelist')


def _csv_errores(request):
    paquete = request.session.get(SESION) or {}
    if paquete.get('usuario') != request.user.pk:
        return HttpResponse('La vista previa venció.', status=400, content_type='text/plain')
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['fila', 'documento', 'nombre', 'telefono', 'motivo'])
    for fila in paquete.get('filas') or []:
        if fila.get('ok'):
            continue
        writer.writerow([
            fila.get('fila'),
            fila.get('cedula'),
            fila.get('nombre'),
            fila.get('telefono'),
            ' '.join(fila.get('errores') or []),
        ])
    respuesta = HttpResponse(buffer.getvalue(), content_type='text/csv')
    respuesta['Content-Disposition'] = 'attachment; filename="estudiantes_errores.csv"'
    return respuesta


def _pagina(request, preview):
    from core.admin.estudiante_bienvenida import hay_plantilla_bienvenida

    validas = [fila for fila in (preview or []) if fila.get('ok')]
    malas = [fila for fila in (preview or []) if not fila.get('ok')]
    con_curso = [fila for fila in validas if fila.get('curso_id')]
    return render(request, 'admin/importar_estudiantes_v2.html', {
        'title': 'Importar varios desde Excel',
        'preview': preview,
        'validas': validas,
        'malas': malas,
        'n_mensajes': len(con_curso),
        'hay_bienvenida': hay_plantilla_bienvenida(),
        'tope': tope_filas(),
    })
