# -*- coding: utf-8 -*-
"""Crea el cliente demo Confama + usuario portal + cursos/estudiantes de muestra.

Uso:
  python manage.py seed_confama_demo
  python manage.py seed_confama_demo --password 'Confama2026!'
"""
from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from portal.models import PortalUsuario
from portal.provision import provisionar_usuario_portal


# Municipios realistas (nombre, departamento, clave DIVIPOLA aproximada)
_MUNICIPIOS = [
    ('Medellín', 'Antioquia', '05001'),
    ('Bello', 'Antioquia', '05088'),
    ('Envigado', 'Antioquia', '05266'),
    ('Rionegro', 'Antioquia', '05615'),
    ('Apartadó', 'Antioquia', '05045'),
    ('Cali', 'Valle del Cauca', '76001'),
    ('Palmira', 'Valle del Cauca', '76520'),
    ('Bogotá', 'Cundinamarca', '11001'),
    ('Manizales', 'Caldas', '17001'),
    ('Pereira', 'Risaralda', '66001'),
    ('Armenia', 'Quindío', '63001'),
    ('Cartagena', 'Bolívar', '13001'),
    ('Barranquilla', 'Atlántico', '08001'),
    ('Santa Marta', 'Magdalena', '47001'),
    ('Neiva', 'Huila', '41001'),
    ('Ibagué', 'Tolima', '73001'),
    ('Pasto', 'Nariño', '52001'),
    ('Popayán', 'Cauca', '19001'),
    ('Montería', 'Córdoba', '23001'),
    ('Sincelejo', 'Sucre', '70001'),
]

_CURSOS = [
    {
        'nombre': 'Negocios rurales — Confama',
        'modulos': [
            'Diagnóstico del emprendimiento',
            'Costos y margen',
            'Rendir cuentas entre socios',
            'Mercadeo simple',
        ],
    },
    {
        'nombre': 'Power Skills — liderazgo en campo',
        'modulos': [
            'Comunicación asertiva',
            'Trabajo en equipo',
            'Resolución de conflictos',
        ],
    },
    {
        'nombre': 'Sostenibilidad y buen vivir',
        'modulos': [
            'Cuidado del suelo',
            'Agua y residuos',
            'Buenas prácticas',
        ],
    },
    {
        'nombre': 'Innovación & IA para el agro',
        'modulos': [
            'Datos en el celular',
            'Alertas y clima',
            'Herramientas eki',
        ],
    },
]

_NOMBRES = [
    'Ana María Restrepo', 'Carlos Mejía', 'Diana López', 'Esteban Giraldo',
    'Fabiola Quintero', 'Gabriel Osorio', 'Helena Vargas', 'Iván Cano',
    'Julián Patiño', 'Karen Suárez', 'Luis Fernando Hoyos', 'María Camila Ríos',
    'Natalia Zapata', 'Óscar Bedoya', 'Paula Andrea Vélez', 'Ricardo Muñoz',
    'Sandra Patricia Duque', 'Tomás Cardona', 'Úrsula Gómez', 'Valentina Arango',
    'William Franco', 'Ximena Correa', 'Yolanda Mesa', 'Zoraida Henao',
    'Andrés Felipe Ruiz', 'Beatriz Elena Soto', 'Cristian David Londoño',
    'Daniela Marcela Agudelo', 'Elkin Hernán Pérez', 'Flor Ángela Montoya',
]


class Command(BaseCommand):
    help = 'Cliente Confama demo: usuario portal + cursos + estudiantes con cobertura'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='Confama2026!', help='Password del usuario portal')
        parser.add_argument('--estudiantes', type=int, default=48, help='Cantidad de estudiantes demo')
        parser.add_argument('--reset', action='store_true', help='Borra data Confama previa y recrea')

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password']
        n_est = max(12, int(options['estudiantes']))

        cliente = Cliente.objects.filter(nombre__iexact='Confama').first()
        if cliente and options['reset']:
            self.stdout.write('Reset: borrando data Confama…')
            Estudiante.objects.filter(cliente=cliente).delete()
            Curso.objects.filter(cliente=cliente).delete()
            PortalUsuario.objects.filter(organizacion=cliente).delete()
            User.objects.filter(username__iexact='confama').delete()
            cliente.delete()
            cliente = None

        if not cliente:
            cliente = Cliente.objects.create(
                nombre='Confama',
                contacto_principal='Equipo Confama',
                email='confama-demo@eki.technology',
                telefono='573001000200',
                activo=True,
                portal_productos='cursos',
                portal_subtitulo='Smart Skills Factory · demo',
                cupos_portal=10,
            )
            self.stdout.write(self.style.SUCCESS(f'Cliente Confama id={cliente.pk}'))
        else:
            cliente.portal_productos = 'cursos'
            cliente.portal_subtitulo = cliente.portal_subtitulo or 'Smart Skills Factory · demo'
            cliente.cupos_portal = max(int(cliente.cupos_portal or 0), 10)
            cliente.activo = True
            cliente.save()
            self.stdout.write(f'Cliente Confama existente id={cliente.pk}')

        user = User.objects.filter(username__iexact='confama').first()
        if not user:
            user, pu, pwd = provisionar_usuario_portal(
                cliente=cliente,
                username='confama',
                password=password,
                first_name='Confama',
                last_name='Demo',
                email='confama@eki.technology',
                rol='admin',
                forzar_cambio=False,
            )
            self.stdout.write(self.style.SUCCESS(
                f'Usuario portal confama / {pwd} (rol admin)'
            ))
        else:
            user.set_password(password)
            user.first_name = user.first_name or 'Confama'
            user.is_active = True
            user.is_staff = False
            user.save()
            pu, _ = PortalUsuario.objects.get_or_create(
                user=user,
                defaults={'organizacion': cliente, 'rol': 'admin'},
            )
            if pu.organizacion_id != cliente.pk:
                pu.organizacion = cliente
            pu.rol = 'admin'
            pu.save()
            self.stdout.write(self.style.SUCCESS(
                f'Usuario confama actualizado · password={password}'
            ))

        cursos = []
        for i, spec in enumerate(_CURSOS):
            curso, created = Curso.objects.get_or_create(
                cliente=cliente,
                nombre=spec['nombre'],
                defaults={
                    'activo': True,
                    'orden': i + 1,
                    'descripcion': f'Programa Confama — {spec["nombre"]}',
                },
            )
            if not created:
                curso.activo = True
                curso.orden = i + 1
                curso.save(update_fields=['activo', 'orden'])
            for n, titulo in enumerate(spec['modulos'], start=1):
                Modulo.objects.get_or_create(
                    curso=curso,
                    numero=n,
                    defaults={
                        'titulo': titulo,
                        'descripcion': f'Contenido demo: {titulo}',
                        'contenido': f'Módulo demo Confama — {titulo}.',
                    },
                )
            cursos.append(curso)
            self.stdout.write(f'  Curso: {curso.nombre} ({"nuevo" if created else "ok"})')

        existentes = Estudiante.objects.filter(cliente=cliente).count()
        faltan = max(0, n_est - existentes)
        rng = random.Random(42)
        creados = 0
        for i in range(faltan):
            muni, depto, clave = _MUNICIPIOS[i % len(_MUNICIPIOS)]
            nombre = _NOMBRES[i % len(_NOMBRES)]
            if i >= len(_NOMBRES):
                nombre = f'{nombre} {i}'
            tel = f'57300{1000000 + i:07d}'
            ced = f'100{1000000 + i}'
            est = Estudiante.objects.create(
                cliente=cliente,
                nombre=nombre,
                telefono=tel,
                cedula=ced,
                tipo_documento='CC',
                municipio=muni,
                departamento=depto,
                territory_id=clave,
                activo=True,
                estado_chat='ACTIVO',
                acepto_terminos=True,
            )
            curso = cursos[i % len(cursos)]
            mods = list(Modulo.objects.filter(curso=curso).order_by('numero'))
            completado = (i % 7 == 0)
            mod_act = mods[min(len(mods) - 1, (i % max(1, len(mods))))] if mods else None
            prog = ProgresoEstudiante.objects.create(
                estudiante=est,
                curso=curso,
                modulo_actual=mod_act,
                completado=completado,
                fecha_completado=timezone.now() - timedelta(days=2) if completado else None,
            )
            # fecha_inicio es auto_now_add; ajustamos para que el timeline se vea vivo
            ProgresoEstudiante.objects.filter(pk=prog.pk).update(
                fecha_inicio=timezone.now() - timedelta(days=rng.randint(5, 60)),
                fecha_ultimo_avance=timezone.now() - timedelta(days=rng.randint(0, 14)),
            )
            creados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Estudiantes: {Estudiante.objects.filter(cliente=cliente).count()} '
            f'(+{creados} nuevos)'
        ))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('QA_PASS seed Confama'))
        self.stdout.write('Login portal: usuario=confama')
        self.stdout.write(f'Password: {password}')
        self.stdout.write('URL: /portal/login/')
