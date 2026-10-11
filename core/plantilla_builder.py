"""Editor de plantillas Meta: texto, imagen o carrusel. No es el formulario largo."""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.models_campana_meta import (
    PlantillaMeta,
    TarjetaPlantillaMeta,
    sanitizar_nombre_meta,
    variables_en,
)

TIPOS_EDITOR = ('TEXTO', 'IMAGEN', 'CARRUSEL')
ESTADOS_SOLO_LECTURA = ('APPROVED', 'PENDING', 'IN_APPEAL')
ORIGENES = ('estudiante.nombre', 'organizacion.nombre', 'curso.nombre', 'texto_fijo')
IDIOMAS = (('es', 'Español'), ('en', 'English'))
CATEGORIAS_EDITOR = (('UTILITY', 'Utilidad'), ('MARKETING', 'Marketing'))

TARJETAS_TIPO = (
    ('TEXTO', 'Texto', 'Un aviso o un reenganche. Un mensaje y, si hace falta, un botón.'),
    ('IMAGEN', 'Imagen', 'El diploma. El mensaje lleva nombre, curso y código. La foto va al enviar.'),
    ('CARRUSEL', 'Carrusel', 'Los cursos. Un texto y al menos dos tarjetas.'),
)

_SUFIJO_VERSION = re.compile(r'\s+v\d+$')


def _txt(datos, clave: str) -> str:
    return (datos.get(clave) or '').strip()


def editor_solo_lectura(plantilla: PlantillaMeta | None) -> bool:
    return plantilla is not None and plantilla.estado in ESTADOS_SOLO_LECTURA


def _etiqueta(n: int) -> str:
    return '{{' + str(n) + '}}'


def _muestras(texto: str) -> list[str]:
    if not (texto or '').strip():
        return []
    return [parte.strip() for parte in texto.split('|')]


def _variables_de(cuerpo: str, ejemplos: str, origenes) -> list[dict]:
    vistos = []
    for n in variables_en(cuerpo):
        if n not in vistos:
            vistos.append(n)
    muestras = _muestras(ejemplos)
    mapa = origenes if isinstance(origenes, dict) else {}
    filas = []
    for i, n in enumerate(vistos):
        clave = str(mapa.get(str(n)) or 'texto_fijo')
        if clave not in ORIGENES:
            clave = 'texto_fijo'
        filas.append({
            'n': n,
            'etiqueta': _etiqueta(n),
            'ejemplo': muestras[i] if i < len(muestras) else '',
            'origen': clave,
            'fijo': '',
        })
    return filas


def _botones_de(plantilla: PlantillaMeta | None) -> list[dict]:
    if plantilla is None:
        return []
    filas = []
    for n in (1, 2):
        texto = (getattr(plantilla, f'boton_{n}_texto') or '').strip()
        if texto:
            filas.append({'texto': texto})
    return filas


def _tarjetas_de(plantilla: PlantillaMeta | None, tipo: str) -> tuple[list[dict], str, str]:
    filas = []
    if plantilla is not None and plantilla.pk and tipo == 'CARRUSEL':
        for i, tarjeta in enumerate(plantilla.tarjetas.all()):
            filas.append({
                'uid': f'c{i}',
                'titulo': tarjeta.titulo,
                'cuerpo': tarjeta.cuerpo,
                'imagen_url': tarjeta.imagen_url,
            })
    ver = 'Ver curso'
    info = 'Más información'
    if plantilla is not None and plantilla.pk and tipo == 'CARRUSEL':
        primera = plantilla.tarjetas.order_by('orden', 'id').first()
        if primera is not None:
            ver = primera.boton_ver_texto or ver
            info = primera.boton_info_texto or info
    if tipo == 'CARRUSEL' and len(filas) < 2:
        while len(filas) < 2:
            filas.append({
                'uid': f'c{len(filas)}',
                'titulo': '',
                'cuerpo': '',
                'imagen_url': '',
            })
    return filas, ver, info


def armar_inicial(plantilla: PlantillaMeta | None, tipo: str, datos=None, foto_muestra: str = '') -> dict:
    """Estado del formulario. Si hay POST con errores, manda lo que la persona escribió."""
    tipo = (tipo or 'TEXTO').upper()
    if tipo not in TIPOS_EDITOR:
        tipo = 'TEXTO'
    if datos is not None and _txt(datos, 'tipo').upper() in TIPOS_EDITOR:
        tipo = _txt(datos, 'tipo').upper()

    def campo(clave, defecto):
        if datos is not None and clave in datos:
            return datos.get(clave) or ''
        return defecto

    nombre = campo('nombre_interno', plantilla.nombre_interno if plantilla else '')
    cuerpo = campo('cuerpo', plantilla.cuerpo if plantilla else '')
    footer = campo('footer', plantilla.footer if plantilla else '')
    categoria = campo('categoria', plantilla.categoria if plantilla else 'UTILITY')
    if categoria not in ('UTILITY', 'MARKETING'):
        categoria = 'UTILITY'
    idioma = campo('idioma', plantilla.idioma if plantilla else 'es') or 'es'
    ejemplos = plantilla.ejemplos_cuerpo if plantilla else ''
    origenes = plantilla.origen_variables if plantilla is not None and isinstance(plantilla.origen_variables, dict) else {}
    if datos is not None and (_claves_tabla(datos) or 'ejemplos_cuerpo' in datos):
        ejemplos, origenes = _ejemplos_y_origenes(datos, plantilla)
    botones = _botones_de(plantilla)
    if datos is not None and (
        'boton_texto' in datos or 'boton_texto_1' in datos or 'boton_1_texto' in datos or 'boton_2_texto' in datos
    ):
        botones = []
        primero = _txt(datos, 'boton_1_texto') or _txt(datos, 'boton_texto_1') or _txt(datos, 'boton_texto')
        segundo = _txt(datos, 'boton_2_texto') or (_txt(datos, 'boton_texto_2') if 'boton_texto_2' in datos else '')
        if primero:
            botones.append({'texto': primero})
        if segundo:
            botones.append({'texto': segundo})
    tarjetas, ver, info = _tarjetas_de(plantilla, tipo)
    if datos is not None and 'card_count' in datos:
        tarjetas = []
        for i, fila in enumerate(tarjetas_desde_post(datos)):
            tarjetas.append({
                'uid': f'c{i}',
                'titulo': fila['titulo'],
                'cuerpo': fila['cuerpo'],
                'imagen_url': fila['imagen_url'],
            })
        if _txt(datos, 'card_ver'):
            ver = _txt(datos, 'card_ver')
        if _txt(datos, 'card_info'):
            info = _txt(datos, 'card_info')
        while tipo == 'CARRUSEL' and len(tarjetas) < 2:
            tarjetas.append({'uid': f'c{len(tarjetas)}', 'titulo': '', 'cuerpo': '', 'imagen_url': ''})
    variables = _variables_de(cuerpo, ejemplos, origenes)
    return {
        'tipo': tipo,
        'nombre': nombre,
        'categoria': categoria,
        'idioma': idioma,
        'cuerpo': cuerpo,
        'footer': footer,
        'botones': botones,
        'variables': variables,
        'tarjetas': tarjetas,
        'botonVer': ver,
        'botonInfo': info,
        'soloLectura': editor_solo_lectura(plantilla),
        'metaName': (plantilla.meta_name if plantilla is not None else '') or '',
        'metaBloqueado': bool(plantilla is not None and (plantilla.meta_template_id or '').strip()),
        'appId': True,
        'notas': (plantilla.notas if plantilla is not None else '') or '',
        'boton1': (plantilla.boton_1_texto if plantilla is not None else '') or '',
        'boton2': (plantilla.boton_2_texto if plantilla is not None else '') or '',
        'fotoMuestra': foto_muestra,
        'ejemplosPipe': ejemplos,
        'ejemplos': {str(fila['n']): fila['ejemplo'] for fila in variables},
        'origenes': {str(fila['n']): fila['origen'] for fila in variables},
        'idiomas': [{'codigo': c, 'nombre': n} for c, n in IDIOMAS],
        'categorias': [{'codigo': c, 'nombre': n} for c, n in CATEGORIAS_EDITOR],
        'opcionesOrigen': [
            {'codigo': 'estudiante.nombre', 'nombre': 'estudiante.nombre'},
            {'codigo': 'organizacion.nombre', 'nombre': 'organización.nombre'},
            {'codigo': 'curso.nombre', 'nombre': 'curso.nombre'},
            {'codigo': 'texto_fijo', 'nombre': 'texto fijo'},
        ],
    }


def tarjetas_desde_post(datos) -> list[dict]:
    try:
        total = int(datos.get('card_count') or 0)
    except (TypeError, ValueError):
        total = 0
    ver_comun = _txt(datos, 'card_ver')
    info_comun = _txt(datos, 'card_info')
    filas = []
    for i in range(max(0, min(total, 10))):
        titulo = _txt(datos, f'card_titulo_{i}')
        cuerpo = _txt(datos, f'card_cuerpo_{i}')
        imagen = _txt(datos, f'card_imagen_{i}')
        if not titulo and not cuerpo and not imagen:
            continue
        ver = ver_comun or _txt(datos, f'card_ver_{i}') or 'Ver curso'
        info = info_comun or _txt(datos, f'card_info_{i}') or 'Más información'
        filas.append({
            'titulo': titulo[:200],
            'cuerpo': cuerpo[:160],
            'imagen_url': imagen[:1000],
            'boton_ver_texto': ver[:20],
            'boton_info_texto': info[:20],
        })
    return filas


def _claves_tabla(datos) -> bool:
    for clave in datos:
        if clave.startswith(('var_ejemplo_', 'var_origen_', 'ejemplo_', 'origen_')):
            return True
    return False


def _ejemplos_y_origenes(datos, plantilla: PlantillaMeta | None) -> tuple[str, dict]:
    indices = []
    for clave in datos:
        if not clave.startswith(('var_ejemplo_', 'var_origen_', 'ejemplo_', 'origen_')):
            continue
        if clave in ('ejemplos_cuerpo',):
            continue
        try:
            indices.append(int(clave.rsplit('_', 1)[-1]))
        except ValueError:
            continue
    if not indices:
        previo = plantilla.origen_variables if plantilla is not None and isinstance(plantilla.origen_variables, dict) else {}
        return _txt(datos, 'ejemplos_cuerpo')[:500], dict(previo)
    ejemplos = []
    origenes = {}
    for i in range(1, max(indices) + 1):
        ejemplos.append(_txt(datos, f'ejemplo_{i}') or _txt(datos, f'var_ejemplo_{i}'))
        origen = _txt(datos, f'origen_{i}') or _txt(datos, f'var_origen_{i}') or 'texto_fijo'
        if origen not in ORIGENES:
            origen = 'texto_fijo'
        origenes[str(i)] = origen
    return '|'.join(ejemplos)[:500], origenes


def _aplicar_botones(plantilla: PlantillaMeta, datos) -> None:
    if 'boton_texto_1' not in datos and 'boton_texto' not in datos and 'boton_texto_2' not in datos:
        return
    textos = []
    if 'boton_texto_1' in datos or 'boton_texto' in datos:
        textos.append(_txt(datos, 'boton_texto_1') or _txt(datos, 'boton_texto'))
    if 'boton_texto_2' in datos:
        textos.append(_txt(datos, 'boton_texto_2'))
    while len(textos) < 2:
        textos.append('')
    for n, texto in enumerate(textos[:2], start=1):
        if texto:
            setattr(plantilla, f'boton_{n}_tipo', 'QUICK_REPLY')
            setattr(plantilla, f'boton_{n}_texto', texto[:25])
        else:
            setattr(plantilla, f'boton_{n}_tipo', '')
            setattr(plantilla, f'boton_{n}_texto', '')


def guardar_editor(datos, tipo: str, plantilla: PlantillaMeta | None = None) -> tuple[PlantillaMeta | None, list[str]]:
    """Guarda el borrador. No llama a Meta."""
    tipo = (tipo or '').upper()
    if _txt(datos, 'tipo').upper() in TIPOS_EDITOR:
        tipo = _txt(datos, 'tipo').upper()
    if tipo not in TIPOS_EDITOR:
        return None, ['Ese tipo no está en el editor.']
    if editor_solo_lectura(plantilla):
        return None, ['Esta plantilla está en revisión o aprobada. Duplícala para cambiarla.']
    nombre = _txt(datos, 'nombre_interno')
    cuerpo = _txt(datos, 'cuerpo')
    errores = []
    if not nombre:
        errores.append('Escribe el nombre.')
    if not cuerpo:
        errores.append('Escribe el mensaje.')
    tecnico = sanitizar_nombre_meta(nombre)
    if nombre and not tecnico:
        errores.append('El nombre técnico quedó vacío. Usa letras o números.')
    if errores:
        return None, errores

    if plantilla is None:
        plantilla = PlantillaMeta(idioma='es', categoria='UTILITY', estado='BORRADOR')
    plantilla.nombre_interno = nombre[:120]
    plantilla.meta_name = tecnico
    plantilla.tipo = tipo
    plantilla.cuerpo = cuerpo
    if _claves_tabla(datos) or 'ejemplos_cuerpo' in datos:
        ejemplos, origenes = _ejemplos_y_origenes(datos, plantilla)
        plantilla.ejemplos_cuerpo = ejemplos
        plantilla.origen_variables = origenes
    if 'footer' in datos:
        plantilla.footer = _txt(datos, 'footer')[:60]
    if _txt(datos, 'categoria') in ('UTILITY', 'MARKETING'):
        plantilla.categoria = _txt(datos, 'categoria')
    elif not plantilla.categoria:
        plantilla.categoria = 'UTILITY'
    if _txt(datos, 'idioma'):
        plantilla.idioma = _txt(datos, 'idioma')[:10]
    elif not plantilla.idioma:
        plantilla.idioma = 'es'
    _aplicar_botones(plantilla, datos)

    try:
        plantilla.full_clean()
    except ValidationError as exc:
        mensajes = []
        if hasattr(exc, 'message_dict'):
            for lista in exc.message_dict.values():
                mensajes.extend(lista)
        return None, mensajes or ['Revisa el mensaje.']

    try:
        plantilla.save()
    except IntegrityError:
        return None, ['Ya hay una plantilla con ese nombre técnico en este idioma. Duplícala como v2.']
    if tipo == 'CARRUSEL':
        filas = tarjetas_desde_post(datos)
        if len(filas) < 2:
            return plantilla, ['El carrusel necesita al menos dos tarjetas con título, texto y foto https.']
        if any(not f['titulo'] or not f['cuerpo'] or not f['imagen_url'].startswith('https://') for f in filas):
            return plantilla, ['Cada tarjeta necesita título, texto y una foto https.']
        with transaction.atomic():
            plantilla.tarjetas.all().delete()
            for orden, fila in enumerate(filas):
                TarjetaPlantillaMeta.objects.create(
                    plantilla=plantilla,
                    orden=orden,
                    titulo=fila['titulo'],
                    cuerpo=fila['cuerpo'],
                    imagen_url=fila['imagen_url'],
                    boton_ver_id=f'ver_{orden}'[:64],
                    boton_ver_texto=fila['boton_ver_texto'],
                    boton_info_id=f'info_{orden}'[:64],
                    boton_info_texto=fila['boton_info_texto'],
                )
    return plantilla, []


def _visible_libre(nombre: str, idioma: str) -> str:
    raiz = _SUFIJO_VERSION.sub('', (nombre or 'Plantilla').strip()) or 'Plantilla'
    for n in range(2, 50):
        visible = f'{raiz} v{n}'[:120]
        tecnico = sanitizar_nombre_meta(visible)
        if tecnico and not PlantillaMeta.objects.filter(meta_name=tecnico, idioma=idioma).exists():
            return visible
    return f'{raiz} v49'[:120]


def duplicar_plantilla(origen: PlantillaMeta) -> PlantillaMeta:
    """Borrador nuevo. El nombre visible lleva v2 y el técnico queda con _v2."""
    visible = _visible_libre(origen.nombre_interno, origen.idioma)
    copia = PlantillaMeta(
        nombre_interno=visible,
        meta_name=sanitizar_nombre_meta(visible),
        idioma=origen.idioma or 'es',
        categoria=origen.categoria if origen.categoria in ('UTILITY', 'MARKETING') else 'UTILITY',
        header_texto=origen.header_texto,
        header_ejemplo=origen.header_ejemplo,
        cuerpo=origen.cuerpo,
        ejemplos_cuerpo=origen.ejemplos_cuerpo,
        origen_variables=dict(origen.origen_variables or {}) if isinstance(origen.origen_variables, dict) else {},
        footer=origen.footer,
        tipo=origen.tipo if origen.tipo in TIPOS_EDITOR else 'TEXTO',
        boton_1_tipo=origen.boton_1_tipo,
        boton_1_texto=origen.boton_1_texto,
        boton_1_url=origen.boton_1_url,
        boton_1_ejemplo=origen.boton_1_ejemplo,
        boton_2_tipo=origen.boton_2_tipo,
        boton_2_texto=origen.boton_2_texto,
        boton_2_url=origen.boton_2_url,
        boton_2_ejemplo=origen.boton_2_ejemplo,
        estado='BORRADOR',
        activa=True,
    )
    copia.save()
    if copia.tipo == 'CARRUSEL':
        for tarjeta in origen.tarjetas.all():
            TarjetaPlantillaMeta.objects.create(
                plantilla=copia,
                orden=tarjeta.orden,
                titulo=tarjeta.titulo,
                cuerpo=tarjeta.cuerpo,
                imagen_url=tarjeta.imagen_url,
                boton_ver_id=tarjeta.boton_ver_id,
                boton_ver_texto=tarjeta.boton_ver_texto,
                boton_info_id=tarjeta.boton_info_id,
                boton_info_texto=tarjeta.boton_info_texto,
                info_url=tarjeta.info_url,
            )
    return copia
