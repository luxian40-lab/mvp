"""QA: emitir OTP en RDS prod y validar login web Aprende (código de 6 dígitos).

Requiere EKI_USE_REMOTE_DB=1 y DATABASE_URL apuntando a RDS (mismo que EB).
No imprime el código completo en logs de éxito (solo últimos 2 dígitos).
"""
from __future__ import annotations

import os
import re
import sys
import urllib.parse
import urllib.request
import http.cookiejar


def main() -> int:
    os.environ.setdefault('EKI_USE_REMOTE_DB', '1')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

    import django
    django.setup()

    from django.conf import settings
    from core.models import Estudiante
    from aprende.acceso_whatsapp import emitir_acceso_desde_whatsapp, verificar_codigo_web
    from aprende.models import CodigoAccesoAprende
    from unittest.mock import patch

    if 'sqlite' in settings.DATABASES['default']['ENGINE']:
        print('FAIL: still on sqlite; set EKI_USE_REMOTE_DB=1 and DATABASE_URL')
        return 2

    tel = (os.environ.get('QA_APRENDE_TEL') or '573026480629').strip()
    est = Estudiante.objects.filter(telefono__endswith=tel[-10:], activo=True).first()
    if not est:
        est = Estudiante.objects.filter(telefono=tel, activo=True).first()
    if not est:
        print(f'FAIL: no estudiante for tel …{tel[-4:]}')
        return 3

    with patch('studio.aprende_bridge.url_handoff_aprende', return_value='https://aprende.eki.technology/aprende/handoff/?t=qa'):
        msg = emitir_acceso_desde_whatsapp(est)
    m = re.search(r'\*(\d{6})\*', msg)
    if not m:
        print('FAIL: no code in emit message')
        return 4
    codigo = m.group(1)
    assert CodigoAccesoAprende.objects.filter(codigo=codigo, estudiante=est).exists()
    print(f'emit_ok est={est.pk} code_tail=**{codigo[-2:]}')

    # Round-trip verificar without consuming for web test: re-emit fresh
    CodigoAccesoAprende.objects.filter(estudiante=est).delete()
    with patch('studio.aprende_bridge.url_handoff_aprende', return_value='https://aprende.eki.technology/aprende/handoff/?t=qa'):
        msg = emitir_acceso_desde_whatsapp(est)
    codigo = re.search(r'\*(\d{6})\*', msg).group(1)

    LOGIN = 'https://aprende.eki.technology/aprende/estudiante/login/'
    UA = 'Mozilla/5.0 (compatible; eki-qa-otp/1.0)'
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    html = opener.open(urllib.request.Request(LOGIN, headers={'User-Agent': UA}), timeout=30).read().decode()
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
    body = urllib.parse.urlencode({
        'csrfmiddlewaretoken': token,
        'codigo': codigo,
        'next': '/aprende/estudiante/',
    }).encode()
    req = urllib.request.Request(LOGIN, data=body, headers={'User-Agent': UA, 'Referer': LOGIN})
    resp = opener.open(req, timeout=30)
    final = resp.geturl()
    print(f'login_final_url={final}')
    ok = '/aprende/estudiante/' in final and 'login' not in final
    # confirm session sees home
    home = opener.open(
        urllib.request.Request('https://aprende.eki.technology/aprende/estudiante/', headers={'User-Agent': UA}),
        timeout=30,
    )
    home_html = home.read().decode('utf-8', 'replace')
    home_url = home.geturl()
    print(f'home_url={home_url}')
    print(f'home_has_continuar={"Continuar" in home_html or "Mis cursos" in home_html or "Hola" in home_html}')
    if not ok:
        # maybe redirect chain ended at login — verify_codigo consumed?
        eid, err = verificar_codigo_web(codigo)
        print(f'reverify_after_post eid={eid} err={err!r}')
        print('FAIL: OTP login did not enter aula')
        return 1
    print('OTP_VALID_PATH_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
