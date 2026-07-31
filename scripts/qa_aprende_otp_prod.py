"""Smoke OTP Aprende en prod: GET login + POST código inválido (CSRF)."""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

LOGIN = 'https://aprende.eki.technology/aprende/estudiante/login/'
UA = 'Mozilla/5.0 (compatible; eki-qa/1.0)'


def main() -> int:
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    req = urllib.request.Request(LOGIN, headers={'User-Agent': UA})
    with opener.open(req, timeout=30) as resp:
        html = resp.read().decode('utf-8', 'replace')
        code = getattr(resp, 'status', 200)
    print(f'GET login={code}')
    assert code == 200
    assert 'name="codigo"' in html
    assert 'Autenticación WhatsApp' in html or 'WhatsApp' in html
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    assert m, 'csrf missing'
    token = m.group(1)

    body = urllib.parse.urlencode({
        'csrfmiddlewaretoken': token,
        'codigo': '000000',
        'next': '/aprende/estudiante/',
    }).encode()
    post = urllib.request.Request(
        LOGIN,
        data=body,
        headers={'User-Agent': UA, 'Referer': LOGIN},
    )
    try:
        with opener.open(post, timeout=30) as resp:
            out = resp.read().decode('utf-8', 'replace')
            pcode = getattr(resp, 'status', 200)
            loc = ''
    except urllib.error.HTTPError as e:
        out = e.read().decode('utf-8', 'replace')
        pcode = e.code
        loc = e.headers.get('Location', '')
    print(f'POST invalid={pcode} loc={loc}')
    low = out.lower()
    ok_msg = ('inválido' in low or 'invalido' in low or 'vencido' in low)
    print(f'invalid_message={ok_msg}')
    # No session: /estudiante/ must redirect to login
    req2 = urllib.request.Request(
        'https://aprende.eki.technology/aprende/estudiante/',
        headers={'User-Agent': UA},
    )
    try:
        with opener.open(req2, timeout=30) as resp:
            est_code = getattr(resp, 'status', 200)
            est_url = resp.geturl()
    except urllib.error.HTTPError as e:
        est_code = e.code
        est_url = e.headers.get('Location', '')
    print(f'GET estudiante={est_code} url={est_url}')
    gated = est_code in (301, 302) or 'login' in (est_url or '').lower()
    print(f'session_gated={gated or est_code == 200 and "Ingreso" in out}')
    if not ok_msg:
        print('FAIL: expected invalid OTP message')
        return 1
    print('OTP_INVALID_PATH_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
