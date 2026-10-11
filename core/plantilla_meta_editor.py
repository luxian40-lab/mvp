"""Asistente de plantillas. Guarda borrador y, si se pide, usa el alta que ya existe."""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError

from core.models_campana_meta import (
    TIPOS_PLANTILLA,
    PlantillaMeta,
    TarjetaPlantillaMeta,
    ejemplos_lista,
    sanitizar_nombre_meta,
    variables_en,
)
from core.plantilla_meta_reglas import errores_de_alta, numeros_de_variables

SOLO_LECTURA = frozenset({'APPROVED', 'PENDING', 'IN_APPEAL'})
_ORIGENES = frozenset({
    'estudiante.nombre',
    'organizacion.nombre',
    'curso.nombre',
    'texto_fijo',
})


def app_id_listo() -> bool:
    return bool((getattr(settings, 'WHATSAPP_APP_ID', None) or '').strip())


def _txt(datos, clave: str) -> str:
    return (datos.get(clave) or '').strip()


def tarjetas_desde_datos(datos) -> list[dict]:
    if isinstance(datos.get('tarjetas'), list):
        return datos['tarjetas']
    try:
        total = int(datos.get('card_count') or 0)
    except (TypeError, ValueError):
        total = 0
    filas = []
    for i in range(max(0, min(total, 10))):
        filas.append({
            'titulo': _txt(datos, f'card_titulo_{i}')[:200],
            'cuerpo': _txt(datos, f'card_cuerpo_{i}')[:160],
            'imagen_url': _txt(datos, f'card_imagen_{i}')[:1000],
            'boton_ver_texto': (_txt(datos, f'card_ver_{i}') or 'Ver curso')[:20],
            'boton_info_texto': (_txt(datos, f'card_info_{i}') or 'Más información')[:20],
        })
    return filas


def _claves(datos):
    if hasattr(datos, 'keys'):
        return list(datos.keys())
    return []


def ejemplos_desde_datos(datos) -> tuple[str, dict, list]:
    ejemplos = {}
    origenes = {}
    for clave in _claves(datos):
        if clave.startswith('var_ejemplo_') or clave.startswith('ejemplo_'):
            num = clave.rsplit('_', 1)[-1]
            if num.isdigit() and (clave.startswith('var_ejemplo_') or num not in ejemplos):
                ejemplos[num] = _txt(datos, clave)
        if clave.startswith('var_origen_') or (clave.startswith('origen_') and clave[7:].isdigit()):
            num = clave.rsplit('_', 1)[-1]
            if num.isdigit():
                origenes[num] = _txt(datos, clave)
    if not ejemplos:
        nums = _txt(datos, 'variable_nums')
        if nums:
            for parte in nums.split(','):
                clave = parte.strip()
                if not clave.isdigit():
                    continue
                ejemplos[clave] = _txt(datos, f'ejemplo_{clave}')
                origen = _txt(datos, f'origen_{clave}')
                if origen:
                    origenes[clave] = origen
        else:
            partes = ejemplos_lista(datos.get('ejemplos_cuerpo') or '')
            for i, valor in enumerate(partes, start=1):
                ejemplos[str(i)] = valor
    orden = sorted(ejemplos, key=lambda n: int(n))
    filas = []
    for clave in orden:
        origen = origenes.get(clave) or 'fijo'
        if origen == 'texto_fijo':
            origen = 'fijo'
        filas.append({
            'origen': origen,
            'fijo': ejemplos[clave] if origen == 'fijo' else '',
        })
    return '|'.join(ejemplos[n] for n in orden), origenes, filas


def _datos_reglas(datos) -> dict:
    ejemplos, origenes, filas_origen = ejemplos_desde_datos(datos)
    tarjetas = tarjetas_desde_datos(datos)
    salida = {
        'nombre_interno': _txt(datos, 'nombre_interno'),
        'meta_name': _txt(datos, 'meta_name'),
        'cuerpo': datos.get('cuerpo') or '',
        'footer': datos.get('footer') or '',
        'header_texto': datos.get('header_texto') or '',
        'tipo': (_txt(datos, 'tipo') or 'TEXTO').upper(),
        'ejemplos_cuerpo': ejemplos,
        'ejemplos_por_variable': ejemplos,
        'origenes_cuerpo': filas_origen,
        'tarjetas': tarjetas,
        'boton_1_tipo': _txt(datos, 'boton_1_tipo'),
        'boton_1_texto': _txt(datos, 'boton_1_texto') or _txt(datos, 'boton_texto') or _txt(datos, 'boton_texto_1'),
        'boton_1_url': datos.get('boton_1_url') or '',
        'boton_2_tipo': _txt(datos, 'boton_2_tipo'),
        'boton_2_texto': _txt(datos, 'boton_2_texto'),
        'boton_2_url': datos.get('boton_2_url') or '',
    }
    salida['_origenes'] = origenes
    return salida


def guardar_asistente(datos, plantilla: PlantillaMeta | None, *, enviar: bool) -> tuple[PlantillaMeta | None, list[str]]:
    """Guarda el borrador. Si enviar, llama a crear_plantilla_en_meta sin cambiar esa función."""
    normal = _datos_reglas(datos)
    tipo = normal['tipo']
    if tipo not in {codigo for codigo, _nombre in TIPOS_PLANTILLA}:
        return None, ['Ese formato no está entre los que ofrece Meta.']
    if enviar and tipo in ('IMAGEN', 'CARRUSEL') and not app_id_listo():
        return None, [
            'Para imagen y carrusel hace falta WHATSAPP_APP_ID. Texto sigue disponible.',
        ]
    if plantilla is not None and plantilla.pk and plantilla.estado in SOLO_LECTURA:
        return plantilla, [
            f'Esta plantilla está en {plantilla.get_estado_display()} y se abre solo para lectura. '
            'Duplíquela si necesita otro nombre técnico.',
        ]
    meta_posteado = normal['meta_name']
    ya_en_meta = plantilla is not None and plantilla.pk and (plantilla.meta_template_id or '').strip()
    if ya_en_meta:
        normal['meta_name'] = plantilla.meta_name
    elif meta_posteado:
        normal['meta_name'] = meta_posteado
    else:
        normal['meta_name'] = sanitizar_nombre_meta(normal['nombre_interno'])
    errores = errores_de_alta(normal)
    if errores:
        return plantilla, errores

    nueva = plantilla is None or not plantilla.pk
    if nueva:
        plantilla = PlantillaMeta(idioma='es', categoria='UTILITY', estado='BORRADOR', origen='LOCAL')
    plantilla.nombre_interno = normal['nombre_interno'][:120]
    if nueva or not (plantilla.meta_template_id or '').strip():
        plantilla.meta_name = normal['meta_name']
    plantilla.tipo = tipo
    plantilla.cuerpo = normal['cuerpo']
    if 'footer' in datos:
        plantilla.footer = (datos.get('footer') or '')[:60]
    if 'media_url' in datos and tipo in ('IMAGEN', 'VIDEO'):
        plantilla.media_url = (datos.get('media_url') or '').strip()[:1000]
    if normal['ejemplos_cuerpo'] or 'ejemplos_cuerpo' in datos or normal['origenes_cuerpo']:
        plantilla.ejemplos_cuerpo = normal['ejemplos_cuerpo'][:500]
    plantilla.origen_variables = normal['_origenes']
    plantilla.idioma = (_txt(datos, 'idioma') or plantilla.idioma or 'es')[:10]
    categoria = (_txt(datos, 'categoria') or plantilla.categoria or 'UTILITY').upper()
    if categoria in ('MARKETING', 'UTILITY'):
        plantilla.categoria = categoria
    if 'notas' in datos:
        plantilla.notas = datos.get('notas') or ''
    texto_1 = normal['boton_1_texto']
    if texto_1 or 'boton_1_texto' in datos or 'boton_texto' in datos or 'boton_texto_1' in datos:
        plantilla.boton_1_texto = texto_1[:25]
        plantilla.boton_1_tipo = (normal['boton_1_tipo'] or ('QUICK_REPLY' if texto_1 else ''))[:20]
    if 'boton_2_texto' in datos or normal['boton_2_texto']:
        plantilla.boton_2_texto = normal['boton_2_texto'][:25]
        plantilla.boton_2_tipo = normal['boton_2_tipo'][:20]
    if tipo == 'CARRUSEL':
        plantilla.boton_1_tipo = ''
        plantilla.boton_1_texto = ''
        plantilla.boton_2_tipo = ''
        plantilla.boton_2_texto = ''
    try:
        plantilla.full_clean()
    except ValidationError as exc:
        salida = []
        for lista in (exc.message_dict or {}).values():
            salida.extend(lista)
        return (plantilla if plantilla.pk else None), salida or ['Revise el mensaje.']
    plantilla.save()
    if tipo == 'CARRUSEL':
        _guardar_tarjetas(plantilla, normal['tarjetas'])
    if enviar:
        from core.meta_waba import crear_plantilla_en_meta

        resultado = crear_plantilla_en_meta(plantilla)
        if not resultado.get('success'):
            return plantilla, [resultado.get('message') or 'Meta no recibió la plantilla.']
    return plantilla, []


def _guardar_tarjetas(plantilla: PlantillaMeta, filas: list[dict]) -> None:
    plantilla.tarjetas.all().delete()
    for orden, fila in enumerate(filas):
        TarjetaPlantillaMeta.objects.create(
            plantilla=plantilla,
            orden=orden,
            titulo=(fila.get('titulo') or '')[:200],
            cuerpo=(fila.get('cuerpo') or '')[:160],
            imagen_url=(fila.get('imagen_url') or '')[:1000],
            boton_ver_id=f'ver_{orden}'[:64],
            boton_ver_texto=(fila.get('boton_ver_texto') or 'Ver curso')[:20],
            boton_info_id=f'info_{orden}'[:64],
            boton_info_texto=(fila.get('boton_info_texto') or 'Más información')[:20],
        )


def nombre_copia(meta_name: str, idioma: str) -> str:
    base = sanitizar_nombre_meta(meta_name) or 'plantilla'
    n = 2
    candidato = f'{base}_v{n}'[:512]
    while PlantillaMeta.objects.filter(meta_name=candidato, idioma=idioma).exists():
        n += 1
        candidato = f'{base}_v{n}'[:512]
    return candidato


def es_bienvenida(plantilla: PlantillaMeta) -> bool:
    tecnico = (plantilla.meta_name or '').lower()
    visible = (plantilla.nombre_interno or '').lower()
    return tecnico.startswith('eki_bienvenida') or 'bienvenida' in visible


def _token_mapeo(numero: int, origen: str, ejemplo: str, bienvenida: bool) -> str:
    if origen == 'estudiante.nombre' or (bienvenida and numero == 1 and not origen):
        return 'nombre'
    if origen == 'estudiante.telefono':
        return 'telefono'
    if origen == 'organizacion.nombre' or (bienvenida and numero == 2 and not origen):
        return 'organizacion'
    if origen == 'curso.nombre' or (bienvenida and numero == 3 and not origen):
        return 'curso'
    return (ejemplo or f'texto {numero}').replace('|', ' ')


def sugerir_mapeo(plantilla: PlantillaMeta) -> dict:
    """Arma el mapeo de CampanaMeta. nombre y telefono los resuelve el envío actual."""
    origenes = plantilla.origen_variables if isinstance(plantilla.origen_variables, dict) else {}
    ejemplos = ejemplos_lista(plantilla.ejemplos_cuerpo)
    bienvenida = es_bienvenida(plantilla)

    def serie(numeros: list[int]) -> str:
        partes = []
        for numero in numeros:
            ejemplo = ejemplos[numero - 1] if 0 < numero <= len(ejemplos) else ''
            origen = str(origenes.get(str(numero)) or '')
            partes.append(_token_mapeo(numero, origen, ejemplo, bienvenida))
        return '|'.join(partes)

    cuerpo = serie(sorted(set(variables_en(plantilla.cuerpo))))
    header = serie(sorted(set(variables_en(plantilla.header_texto))))
    boton_nums = sorted(set(
        variables_en(plantilla.boton_1_url) + variables_en(plantilla.boton_2_url)
    ))
    aviso = ''
    tokens = [p for p in f'{cuerpo}|{header}'.split('|') if p]
    if any(token not in ('nombre', 'telefono') for token in tokens):
        aviso = (
            'El envío sustituye nombre y telefono. '
            'Organización, curso y el resto salen como texto fijo.'
        )
    return {
        'mapeo_body': cuerpo,
        'mapeo_header': header,
        'mapeo_boton': serie(boton_nums),
        'aviso': aviso,
    }


def lineas_disponibles() -> list[tuple[str, str]]:
    principal = (getattr(settings, 'WHATSAPP_PHONE_ID', None) or '').strip()
    segunda = (getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID_2', None) or '').strip()
    opciones = []
    if principal:
        opciones.append((principal, 'Línea principal'))
    if segunda and segunda != principal:
        opciones.append((segunda, 'Línea 2'))
    return opciones


def valores_de_prueba(plantilla: PlantillaMeta, datos) -> dict:
    """Mapeos literales para enviar_prueba_meta. No cambia esa función."""
    cuerpo = [ _txt(datos, f'var_{n}') for n in sorted(set(variables_en(plantilla.cuerpo))) ]
    header = [ _txt(datos, f'var_h_{n}') for n in sorted(set(variables_en(plantilla.header_texto))) ]
    botones = [
        _txt(datos, f'var_b_{n}')
        for n in sorted(set(variables_en(plantilla.boton_1_url) + variables_en(plantilla.boton_2_url)))
    ]
    return {
        'mapeo_body': '|'.join(cuerpo),
        'mapeo_header': '|'.join(header),
        'mapeo_boton': '|'.join(botones),
    }


def variables_para_formulario(plantilla: PlantillaMeta | None) -> list[dict]:
    if plantilla is None:
        return []
    origenes = plantilla.origen_variables if isinstance(plantilla.origen_variables, dict) else {}
    ejemplos = ejemplos_lista(plantilla.ejemplos_cuerpo)
    numeros = numeros_de_variables(plantilla.cuerpo, plantilla.header_texto, plantilla.boton_1_url, plantilla.boton_2_url)
    filas = []
    for numero in numeros:
        filas.append({
            'n': numero,
            'ejemplo': ejemplos[numero - 1] if 0 < numero <= len(ejemplos) else '',
            'origen': origenes.get(str(numero)) or 'texto_fijo',
        })
    return filas
