"""Diagnóstico: qué pie de foto (caption) acompaña a las imágenes enviadas.

Muestra solo los mensajes salientes que llevaron media, recortados, para ver
si se está colando el título interno del paso o del archivo.
"""
import os

from core.models import PasoModulo, WhatsappLog

CURSO_ID = int(os.environ.get('DIAG_CURSO_ID', '35'))
LIMITE = int(os.environ.get('DIAG_LIMITE', '12'))

print('== ULTIMOS ENVIOS CON MEDIA')
qs = (
    WhatsappLog.objects.filter(tipo='SENT')
    .exclude(paquetes_media__isnull=True)
    .order_by('-fecha')[:LIMITE]
)
for log in qs:
    cuerpo = (log.mensaje or '').strip().replace('\n', ' | ')
    print(f'  [{log.fecha:%d/%m %H:%M}] estado={log.estado} media={str(log.paquetes_media)[:70]!r}')
    print(f'     caption={cuerpo[:200]!r}')

print('\n== PASOS CON MEDIA DEL CURSO (titulo interno vs contenido)')
pasos = (
    PasoModulo.objects.filter(modulo__curso_id=CURSO_ID)
    .exclude(media_url='')
    .exclude(media_url__isnull=True)
    .order_by('modulo__numero', 'orden')
)
for p in pasos:
    contenido = (p.contenido or '').strip()
    print(
        f'  paso {p.id} mod={p.modulo.numero} orden={p.orden} '
        f'titulo={(p.titulo or "")[:40]!r} contenido_len={len(contenido)}'
    )
    if not contenido:
        print('     ^^ SIN TEXTO: el caption sale del titulo interno')
