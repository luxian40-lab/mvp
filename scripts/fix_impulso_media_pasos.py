"""Prod Impulso 22: inspecciona 3 alumnas + repara media M10/M11. Escribe PasoModulo."""
from urllib.request import Request, urlopen

from core.models import Estudiante, PasoModulo, ProgresoEstudiante
from core.twilio_media import preparar_url_media_whatsapp

IDS_MEDIA = (251, 254, 257, 260, 261)
IDS_TRES = (1937, 1963, 1964)  # Yuli, Tatiana, Sarita


def _head(url, timeout=8):
    if not url or url.startswith('/'):
        return None, 0, ''
    try:
        req = Request(url, method='HEAD', headers={'User-Agent': 'eki-fix-impulso/1'})
        with urlopen(req, timeout=timeout) as resp:
            ct = (resp.headers.get('Content-Type') or '').split(';')[0].strip()
            n = int(resp.headers.get('Content-Length') or 0)
            return resp.status, n, ct
    except Exception as e:
        return f'ERR:{type(e).__name__}', 0, ''


print('======== 3 PERSONAS IMPULSO ========')
for eid in IDS_TRES:
    e = Estudiante.objects.filter(id=eid).first()
    if not e:
        print(f'  id={eid} NO EXISTE')
        continue
    p = ProgresoEstudiante.objects.filter(estudiante=e, curso_id=22).select_related(
        'modulo_actual'
    ).first()
    print(
        f'  {e.id} {(e.nombre or "")[:28]!r} onb={e.estado_onboarding} '
        f'chat={e.estado_chat} mod={getattr(getattr(p, "modulo_actual", None), "numero", None)} '
        f'last={getattr(p, "fecha_ultimo_avance", None)} ctx_tipo={(e.contexto_temporal or {}).get("tipo")}'
    )

print('\n======== MEDIA ANTES ========')
for pid in IDS_MEDIA:
    p = PasoModulo.objects.filter(id=pid).first()
    if not p:
        print(f'  p{pid} NO EXISTE')
        continue
    url = (p.media_url or '').strip()
    st, n, ct = _head(url)
    print(
        f'  p{pid} activo={p.activo} apto={p.media_wa_apto} tit={(p.titulo or "")[:40]!r} '
        f'head={st} bytes={n} ct={ct!r} url={url[-80:]}'
    )

print('\n======== REPARAR ========')
for pid in IDS_MEDIA:
    p = PasoModulo.objects.filter(id=pid).first()
    if not p or not (p.media_url or '').strip():
        print(f'  p{pid} skip')
        continue
    old = p.media_url
    prepared = preparar_url_media_whatsapp(old)
    if not prepared:
        print(f'  p{pid} NO PREPARABLE')
        continue
    fields = ['media_wa_apto']
    if prepared != old:
        p.media_url = prepared
        fields.append('media_url')
    p.media_wa_apto = True
    p.save(update_fields=fields)
    st, n, ct = _head(p.media_url)
    print(
        f'  p{pid} OK apto={p.media_wa_apto} head={st} bytes={n} ct={ct!r} '
        f'changed_url={prepared != old} url={p.media_url[-80:]}'
    )

print('\n======== FIN ========')
