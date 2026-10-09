"""Editor de plantillas Meta: texto, imagen o carrusel. No es el formulario largo."""
from __future__ import annotations

from django.core.exceptions import ValidationError

from core.models_campana_meta import PlantillaMeta, TarjetaPlantillaMeta

TIPOS_EDITOR = ('TEXTO', 'IMAGEN', 'CARRUSEL')

TARJETAS_TIPO = (
    ('TEXTO', 'Texto', 'Un aviso o un reenganche. Un mensaje y, si hace falta, un botón.'),
    ('IMAGEN', 'Imagen', 'El diploma. El mensaje lleva nombre, curso y código. La foto va al enviar.'),
    ('CARRUSEL', 'Carrusel', 'Los cursos. Un texto y al menos dos tarjetas.'),
)


def _txt(datos, clave: str) -> str:
    return (datos.get(clave) or '').strip()


def tarjetas_desde_post(datos) -> list[dict]:
    try:
        total = int(datos.get('card_count') or 0)
    except (TypeError, ValueError):
        total = 0
    filas = []
    for i in range(max(0, min(total, 10))):
        titulo = _txt(datos, f'card_titulo_{i}')
        cuerpo = _txt(datos, f'card_cuerpo_{i}')
        imagen = _txt(datos, f'card_imagen_{i}')
        if not titulo and not cuerpo and not imagen:
            continue
        filas.append({
            'titulo': titulo[:200],
            'cuerpo': cuerpo[:160],
            'imagen_url': imagen[:1000],
            'boton_ver_texto': (_txt(datos, f'card_ver_{i}') or 'Ver curso')[:20],
            'boton_info_texto': (_txt(datos, f'card_info_{i}') or 'Más información')[:20],
        })
    return filas


def guardar_editor(datos, tipo: str, plantilla: PlantillaMeta | None = None) -> tuple[PlantillaMeta | None, list[str]]:
    """Guarda el borrador. No llama a Meta."""
    tipo = (tipo or '').upper()
    if tipo not in TIPOS_EDITOR:
        return None, ['Ese tipo no está en el editor.']
    nombre = _txt(datos, 'nombre_interno')
    cuerpo = _txt(datos, 'cuerpo')
    errores = []
    if not nombre:
        errores.append('Escribe el nombre.')
    if not cuerpo:
        errores.append('Escribe el mensaje.')
    if errores:
        return None, errores

    if plantilla is None:
        plantilla = PlantillaMeta(idioma='es', categoria='UTILITY', estado='BORRADOR')
    plantilla.nombre_interno = nombre[:120]
    plantilla.tipo = tipo
    plantilla.cuerpo = cuerpo
    plantilla.ejemplos_cuerpo = _txt(datos, 'ejemplos_cuerpo')[:500]
    plantilla.idioma = 'es'
    if not plantilla.categoria:
        plantilla.categoria = 'UTILITY'
    boton = _txt(datos, 'boton_texto')
    if tipo == 'TEXTO' and boton:
        plantilla.boton_1_tipo = 'QUICK_REPLY'
        plantilla.boton_1_texto = boton[:25]
    elif tipo == 'TEXTO':
        plantilla.boton_1_tipo = ''
        plantilla.boton_1_texto = ''

    try:
        plantilla.full_clean()
    except ValidationError as exc:
        mensajes = []
        for lista in exc.message_dict.values():
            mensajes.extend(lista)
        return None, mensajes or ['Revisa el mensaje.']

    plantilla.save()
    if tipo == 'CARRUSEL':
        filas = tarjetas_desde_post(datos)
        if len(filas) < 2:
            return plantilla, ['El carrusel necesita al menos dos tarjetas con título, texto y foto https.']
        if any(not f['titulo'] or not f['cuerpo'] or not f['imagen_url'].startswith('https://') for f in filas):
            return plantilla, ['Cada tarjeta necesita título, texto y una foto https.']
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
