"""Simulación QA: estudiante sin clave → OTP → crear clave (tel 3026480629)."""
from __future__ import annotations

import os
import re
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import django

django.setup()

from django.core.cache import cache
from django.test import Client, override_settings

from aprende.acceso_whatsapp import emitir_acceso_desde_whatsapp
from aprende.credencial_service import tiene_clave
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.utils_telefono import normalizar_telefono

TEL = normalizar_telefono(sys.argv[1] if len(sys.argv) > 1 else '3026480629')
print('tel_norm=', TEL)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1', 'aprende.eki.technology'],
)
def run():
    cache.clear()
    org, _ = Cliente.objects.get_or_create(
        telefono='573009990099',
        defaults={
            'nombre': 'QA Aula Clave',
            'contacto_principal': 'QA',
            'email': 'qa-aula@test.local',
            'activo': True,
        },
    )
    est = Estudiante.objects.filter(telefono=TEL).first()
    if not est:
        est = Estudiante.objects.create(
            cedula='QA3026480629',
            nombre='QA Luxia Prueba',
            telefono=TEL,
            cliente=org,
            activo=True,
        )
        print('estudiante_creado id=', est.id)
    else:
        print('estudiante_existente id=', est.id, 'nombre=', est.nombre, 'cedula=', est.cedula)

    # Simular "no hay contraseña"
    from aprende.models import CredencialAprendeEstudiante

    CredencialAprendeEstudiante.objects.filter(estudiante=est).delete()
    print('tiene_clave_antes=', tiene_clave(est))

    curso, _ = Curso.objects.get_or_create(
        nombre='QA Curso Aula',
        cliente=org,
        defaults={'activo': True},
    )
    mod, _ = Modulo.objects.get_or_create(
        curso=curso, numero=1,
        defaults={'titulo': 'M1', 'descripcion': 'd', 'contenido': 'hola'},
    )
    ProgresoEstudiante.objects.get_or_create(
        estudiante=est, curso=curso, defaults={'modulo_actual': mod},
    )

    http = Client()
    msg = emitir_acceso_desde_whatsapp(est)
    print('wa_msg_snip=', msg[:180].replace('\n', ' | '))
    m = re.search(r'\*(\d{6})\*', msg)
    assert m, 'no otp in message'
    codigo = m.group(1)
    print('otp=', codigo)

    r1 = http.post('/aprende/estudiante/login/', {'codigo': codigo, 'accion': 'codigo'})
    print('post_otp status=', r1.status_code, 'loc=', r1.get('Location'))
    assert r1.status_code == 302 and '/clave/' in (r1.get('Location') or '')

    r2 = http.post('/aprende/estudiante/clave/', {
        'password': 'PruebaAula1',
        'password2': 'PruebaAula1',
    })
    print('post_clave status=', r2.status_code, 'loc=', r2.get('Location'))
    assert r2.status_code == 302
    print('tiene_clave_despues=', tiene_clave(est))

    http.get('/aprende/estudiante/logout/')
    r3 = http.post('/aprende/estudiante/login/', {
        'accion': 'clave',
        'documento': est.cedula,
        'password': 'PruebaAula1',
    })
    print('login_clave status=', r3.status_code, 'loc=', r3.get('Location'))
    assert r3.status_code == 302
    r4 = http.get('/aprende/estudiante/')
    print('aula status=', r4.status_code)
    assert r4.status_code == 200
    print('QA_PASS simulación sin-clave → crear → login documento+clave')


if __name__ == '__main__':
    run()
