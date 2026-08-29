"""Inscribe 573026480629 en 'Tome las riendas…' sin enviar campaña.

Uso (prod o local con DB remota):
  python scripts/_setup_smoke_riendas.py
"""
from __future__ import annotations

import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
# Forzar intento remoto si hay DATABASE_URL
os.environ.setdefault('EKI_USE_REMOTE_DB', '1')
django.setup()

from django.db import connection

from core.inscripcion_curso import inscribir_estudiante_en_curso, resolver_curso_por_nombre
from core.models import Curso, Estudiante, ProgresoEstudiante
from core.utils_telefono import normalizar_telefono

TEL = normalizar_telefono('3026480629')
NOMBRE_CURSO = 'Tome las riendas de su dinero'


def main() -> int:
    print('db=', connection.vendor, connection.settings_dict.get('NAME'))
    print('tel=', TEL)

    curso = resolver_curso_por_nombre(NOMBRE_CURSO)
    if curso is None:
        # Búsqueda flexible
        qs = Curso.objects.filter(nombre__icontains='riendas', activo=True)
        for c in qs[:20]:
            print('candidato', c.id, c.nombre, getattr(c.cliente, 'nombre', None))
        curso = qs.order_by('id').first()
    if curso is None:
        print('ERROR: curso no encontrado')
        return 1

    print('curso', curso.id, curso.nombre, 'cliente', getattr(curso.cliente, 'nombre', None))

    est = Estudiante.objects.filter(telefono=TEL).first()
    if est is None:
        # Crear mínimo para prueba (sin campaña)
        est = Estudiante.objects.create(
            telefono=TEL,
            nombre='Prueba Smoke eki',
            cedula=f'smoke{TEL[-8:]}',
            cliente=curso.cliente,
            activo=True,
            estado_chat='ESPERANDO_HABEAS_DATA',
            acepto_terminos=False,
        )
        print('CREADO estudiante', est.id)
    else:
        updates = []
        if curso.cliente_id and est.cliente_id != curso.cliente_id:
            est.cliente = curso.cliente
            updates.append('cliente')
        if not est.activo:
            est.activo = True
            updates.append('activo')
        # Dejar listo para ver onboarding al escribir (sin campaña)
        if est.estado_chat not in (
            'ESPERANDO_HABEAS_DATA',
            'ESPERANDO_CEDULA',
            'CONFIRMANDO_DATOS',
            'ACTIVO',
        ):
            est.estado_chat = 'ESPERANDO_HABEAS_DATA'
            updates.append('estado_chat')
        if updates:
            est.save(update_fields=updates)
            print('ACTUALIZADO', updates)
        else:
            print('estudiante existente', est.id, est.nombre, 'estado', est.estado_chat)

    prog, creado = inscribir_estudiante_en_curso(est, curso)
    print(
        'progreso',
        prog.id,
        'creado=' + str(creado),
        'modulo',
        getattr(prog.modulo_actual, 'numero', None),
        getattr(prog.modulo_actual, 'titulo', None),
        'completado',
        prog.completado,
    )
    print('NO se envió campaña ni mensaje Twilio.')
    print(
        'Prueba: escribe al WhatsApp educativo de eki desde',
        TEL,
        '→ debería pedir Habeas (si estado=ESPERANDO_HABEAS_DATA) o pedir *listo* si ya ACTIVO.',
    )
    print(
        'estado_chat=',
        est.estado_chat,
        'acepto_terminos=',
        est.acepto_terminos,
        'cliente=',
        getattr(est.cliente, 'nombre', None),
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
