# -*- coding: utf-8 -*-
"""Crea el cliente demo Confama + usuario portal + estructura de cursos.

Por defecto NO inventa estudiantes ni progreso (no ensucia métricas).
Para poblar cobertura después: --estudiantes 48

Uso:
  python manage.py seed_confama_demo
  python manage.py seed_confama_demo --password 'Confama2026!'
  python manage.py seed_confama_demo --estudiantes 48
"""
from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.gamificacion import PerfilGamificacion
from core.models import Cliente, Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante, WhatsappLog
from core.models_certificados import Certificado
from core.models_extras import GrupoEstudiantes
from portal.models import PortalUsuario
from portal.provision import provisionar_usuario_portal


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
    help = 'Cliente Confama demo: usuario portal + cursos (estudiantes opcionales)'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='Confama2026!', help='Password del usuario portal')
        parser.add_argument(
            '--estudiantes',
            type=int,
            default=0,
            help='Cantidad de estudiantes demo (0 = no inventar métricas; default)',
        )
        parser.add_argument('--reset', action='store_true', help='Borra data Confama previa y recrea')

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password']
        n_est = max(0, int(options['estudiantes']))

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
                portal_subtitulo='DESARROLLO DE COMPETENCIAS',
                cupos_portal=10,
            )
            self.stdout.write(self.style.SUCCESS(f'Cliente Confama id={cliente.pk}'))
        else:
            cliente.portal_productos = 'cursos'
            sub = (cliente.portal_subtitulo or '').strip()
            if (not sub) or ('smart skills' in sub.lower()):
                cliente.portal_subtitulo = 'DESARROLLO DE COMPETENCIAS'
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
                        'descripcion': f'Módulo: {titulo}',
                        'contenido': '',
                    },
                )
            cursos.append(curso)
            self.stdout.write(f'  Curso: {curso.nombre} ({"nuevo" if created else "ok"})')

        if n_est <= 0:
            self.stdout.write(self.style.WARNING(
                'Sin estudiantes demo (métricas intactas). Usa --estudiantes N cuando quieras poblar.'
            ))
        else:
            grupos_spec = [
                ('Cohorte Medellín 2026', '🏙️'),
                ('Campo Antioquia', '🌿'),
                ('Líderes rurales', '⭐'),
            ]
            grupos = []
            for nombre_g, emoji in grupos_spec:
                g, _ = GrupoEstudiantes.objects.get_or_create(
                    cliente=cliente,
                    nombre=nombre_g,
                    defaults={'emoji': emoji, 'descripcion': f'Grupo demo Confama · {nombre_g}'},
                )
                grupos.append(g)

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
                grupos[i % len(grupos)].estudiantes.add(est)

                curso = cursos[i % len(cursos)]
                mods = list(Modulo.objects.filter(curso=curso).order_by('numero'))
                # Mix: completados / en curso / dormidos / recién inscritos
                bucket = i % 10
                completado = bucket == 0
                dormido = bucket in (1, 2)
                sin_avance = bucket == 3
                n_mods_done = len(mods) if completado else (
                    0 if sin_avance else min(len(mods), 1 + (i % max(1, len(mods))))
                )
                if completado:
                    mod_act = mods[-1] if mods else None
                elif sin_avance:
                    mod_act = mods[0] if mods else None
                else:
                    mod_act = mods[min(len(mods) - 1, n_mods_done)] if mods else None

                dias_inactivo = rng.randint(10, 25) if dormido else rng.randint(0, 5)
                prog = ProgresoEstudiante.objects.create(
                    estudiante=est,
                    curso=curso,
                    modulo_actual=mod_act,
                    completado=completado,
                    fecha_completado=timezone.now() - timedelta(days=2) if completado else None,
                )
                ProgresoEstudiante.objects.filter(pk=prog.pk).update(
                    fecha_inicio=timezone.now() - timedelta(days=rng.randint(10, 75)),
                    fecha_ultimo_avance=(
                        None if sin_avance
                        else timezone.now() - timedelta(days=dias_inactivo)
                    ),
                )
                for m in mods[:n_mods_done]:
                    ModuloCompletado.objects.get_or_create(progreso=prog, modulo=m)

                perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=est)
                perfil.puntos_totales = 15 + (i * 17) % 280
                perfil.save(update_fields=['puntos_totales'])

                if completado:
                    Certificado.objects.get_or_create(
                        estudiante=est,
                        curso=curso,
                        defaults={
                            'calificacion_final': 85 + (i % 15),
                            'fecha_inicio': (timezone.now() - timedelta(days=40)).date(),
                            'fecha_completado': (timezone.now() - timedelta(days=2)).date(),
                            'emitido': True,
                            'fecha_emision': timezone.now() - timedelta(days=1),
                            'organizacion_emisora': 'Confama',
                        },
                    )

                # WhatsApp logs (gráficos + salud WA)
                for d in range(7):
                    n_msg = 1 + ((i + d) % 4)
                    for k in range(n_msg):
                        tipo = 'SENT' if (i + d + k) % 3 else 'INCOMING'
                        estado = rng.choice(['DELIVERED', 'READ', 'DELIVERED', 'READ', 'SENT'])
                        if tipo == 'INCOMING':
                            estado = 'RECEIVED'
                        wl = WhatsappLog(
                            telefono=tel,
                            mensaje=f'Demo Confama · día {d} · {nombre.split()[0]}',
                            mensaje_id=f'confama-demo-{est.pk}-{d}-{k}',
                            estado=estado,
                            tipo=tipo,
                            estudiante=est,
                            es_audio=(k == 0 and d % 3 == 0),
                            agente_usado='nat' if tipo == 'SENT' and k == 0 else '',
                        )
                        wl.save()
                        WhatsappLog.objects.filter(pk=wl.pk).update(
                            fecha=timezone.now() - timedelta(days=d, hours=k)
                        )
                creados += 1

            # Top-up métricas en existentes (idempotente: salta si ya tienen WA)
            self._enriquecer_existentes(cliente, cursos, rng)

            self.stdout.write(self.style.SUCCESS(
                f'Estudiantes: {Estudiante.objects.filter(cliente=cliente).count()} '
                f'(+{creados} nuevos)'
            ))
            self.stdout.write(
                f'WhatsApp logs: {WhatsappLog.objects.filter(estudiante__cliente=cliente).count()} · '
                f'Certificados: {Certificado.objects.filter(estudiante__cliente=cliente).count()}'
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('QA_PASS seed Confama'))
        self.stdout.write('Login portal: usuario=confama')
        self.stdout.write(f'Password: {password}')
        self.stdout.write('URL: /portal/login/')

    def _enriquecer_existentes(self, cliente, cursos, rng):
        """Si ya hay N estudiantes, rellena métricas sin duplicar personas."""
        for i, est in enumerate(Estudiante.objects.filter(cliente=cliente).order_by('id')[:80]):
            if WhatsappLog.objects.filter(estudiante=est).exists():
                continue
            tel = (est.telefono or f'57300{1000000 + i:07d}').strip()
            for d in range(7):
                for k in range(1 + (i + d) % 3):
                    tipo = 'SENT' if (i + d + k) % 2 else 'INCOMING'
                    wl = WhatsappLog(
                        telefono=tel,
                        mensaje=f'Demo Confama top-up {d}',
                        mensaje_id=f'confama-topup-{est.pk}-{d}-{k}',
                        estado='READ' if tipo == 'SENT' else 'RECEIVED',
                        tipo=tipo,
                        estudiante=est,
                    )
                    wl.save()
                    WhatsappLog.objects.filter(pk=wl.pk).update(
                        fecha=timezone.now() - timedelta(days=d, hours=k)
                    )
            PerfilGamificacion.objects.get_or_create(
                estudiante=est,
                defaults={'puntos_totales': 40 + (i * 11) % 200},
            )
            prog = ProgresoEstudiante.objects.filter(estudiante=est).first()
            if prog and not prog.modulos_completados.exists():
                mods = list(Modulo.objects.filter(curso=prog.curso).order_by('numero'))
                for m in mods[: max(1, len(mods) // 2)]:
                    ModuloCompletado.objects.get_or_create(progreso=prog, modulo=m)