"""
Seed Cenipalma: org + 2 cursos WhatsApp + curso 10x (modo clases) + grupos + inscripción.

Uso:
  python manage.py setup_cenipalma_piloto --telefono 3026480629
  python manage.py setup_cenipalma_piloto --telefono 3026480629 --asignar-cliente
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Cliente, Curso, Estudiante, Modulo
from core.models_extras import GrupoEstudiantes

CLIENTE_NOMBRE = 'Cenipalma'
CURSO_WA_1 = 'Cenipalma WA — Curso 1'
CURSO_WA_2 = 'Cenipalma WA — Curso 2'
CURSO_10X = 'Cenipalma 10x — clases Aprende'
GRUPO_WA_1 = 'Cenipalma · Cohorte WA 1'
GRUPO_WA_2 = 'Cenipalma · Cohorte WA 2'
GRUPO_10X = 'Cenipalma · 10x Aprende'


def _normalizar_tel(raw: str) -> str:
    digits = ''.join(c for c in (raw or '') if c.isdigit())
    if digits.startswith('57') and len(digits) >= 12:
        return digits
    if len(digits) == 10 and digits.startswith('3'):
        return '57' + digits
    return digits


def _ensure_curso_wa(cliente: Cliente, nombre: str, orden: int) -> tuple[Curso, Modulo]:
    curso, _ = Curso.objects.get_or_create(
        cliente=cliente,
        nombre=nombre,
        defaults={
            'descripcion': f'Curso WhatsApp para {CLIENTE_NOMBRE}. Avance por *listo*.',
            'activo': True,
            'usar_agentes_ia': False,
            'dias_espera_entre_modulos': 0,
            'modo_aula': Curso.MODO_AULA_MODULOS,
            'orden': orden,
        },
    )
    if curso.modo_aula != Curso.MODO_AULA_MODULOS:
        curso.modo_aula = Curso.MODO_AULA_MODULOS
        curso.save(update_fields=['modo_aula'])
    mod, _ = Modulo.objects.get_or_create(
        curso=curso,
        numero=1,
        defaults={
            'titulo': 'Módulo 1 — bienvenida',
            'descripcion': 'Primer módulo del curso WhatsApp.',
            'contenido': 'Bienvenida. Responde *listo* cuando termines.',
            'modo_entrega': 'legacy',
        },
    )
    return curso, mod


def _ensure_curso_10x(cliente: Cliente) -> tuple[Curso, Modulo]:
    curso, _ = Curso.objects.get_or_create(
        cliente=cliente,
        nombre=CURSO_10X,
        defaults={
            'descripcion': (
                'Curso informativo 10x: contenido en Aprende (Clases / Biblioteca). '
                'WhatsApp solo avisos.'
            ),
            'activo': True,
            'usar_agentes_ia': False,
            'dias_espera_entre_modulos': 0,
            'modo_aula': Curso.MODO_AULA_CLASES,
            'usar_gamificacion': False,
            'orden': 10,
        },
    )
    updates = []
    if curso.modo_aula != Curso.MODO_AULA_CLASES:
        curso.modo_aula = Curso.MODO_AULA_CLASES
        updates.append('modo_aula')
    if curso.usar_agentes_ia:
        curso.usar_agentes_ia = False
        updates.append('usar_agentes_ia')
    if curso.usar_gamificacion:
        curso.usar_gamificacion = False
        updates.append('usar_gamificacion')
    if updates:
        curso.save(update_fields=updates)
    mod, _ = Modulo.objects.get_or_create(
        curso=curso,
        numero=1,
        defaults={
            'titulo': 'Clase 1 — bienvenida 10x',
            'descripcion': 'Primera clase del 10x en Aprende.',
            'contenido': 'Bienvenida al 10x. Mira el material en Biblioteca.',
            'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'modo_entrega': 'legacy',
        },
    )
    return curso, mod


def _ensure_grupo(cliente: Cliente, nombre: str, curso: Curso | None = None) -> GrupoEstudiantes:
    g, _ = GrupoEstudiantes.objects.get_or_create(
        cliente=cliente,
        nombre=nombre,
        defaults={
            'emoji': '👥',
            'descripcion': f'Grupo de {CLIENTE_NOMBRE}: {nombre}',
            'activo': True,
        },
    )
    if curso and not g.cursos.filter(pk=curso.pk).exists():
        g.cursos.add(curso)
    return g


class Command(BaseCommand):
    help = 'Seed Cenipalma: 2 cursos WA + 10x clases + 3 grupos + inscripción de prueba.'

    def add_arguments(self, parser):
        parser.add_argument('--telefono', type=str, default='3026480629')
        parser.add_argument(
            '--asignar-cliente',
            action='store_true',
            help='Mueve el estudiante de ese teléfono a la org Cenipalma (teléfono es único).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        tel = _normalizar_tel(options['telefono'])
        if len(tel) < 12:
            raise CommandError(f'Teléfono inválido: {options["telefono"]!r} → {tel!r}')

        cliente, created_c = Cliente.objects.get_or_create(
            nombre=CLIENTE_NOMBRE,
            defaults={
                'nit': '900000CENIP',
                'contacto_principal': 'Cenipalma piloto',
                'email': 'piloto.cenipalma@eki.technology',
                'telefono': tel,
                'activo': True,
                'portal_productos': 'cursos',
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Cliente id={cliente.id} {'creado' if created_c else 'reusado'} · {cliente.nombre}"
            )
        )

        c1, m1 = _ensure_curso_wa(cliente, CURSO_WA_1, orden=1)
        c2, m2 = _ensure_curso_wa(cliente, CURSO_WA_2, orden=2)
        c10, m10 = _ensure_curso_10x(cliente)
        self.stdout.write(
            f"Cursos: WA1={c1.id} (mod {m1.id}) · WA2={c2.id} (mod {m2.id}) · "
            f"10x={c10.id} modo={c10.modo_aula} (clase {m10.id})"
        )

        g1 = _ensure_grupo(cliente, GRUPO_WA_1, c1)
        g2 = _ensure_grupo(cliente, GRUPO_WA_2, c2)
        g10 = _ensure_grupo(cliente, GRUPO_10X, c10)
        self.stdout.write(f"Grupos: {g1.id}/{g1.nombre} · {g2.id}/{g2.nombre} · {g10.id}/{g10.nombre}")

        est = Estudiante.objects.filter(telefono=tel).first()
        if not est:
            est = Estudiante.objects.filter(telefono__endswith=tel[-10:]).first()

        if not est:
            est = Estudiante.objects.create(
                cedula=f'CENI{tel[-8:]}',
                nombre='Piloto Cenipalma',
                telefono=tel,
                cliente=cliente,
                activo=True,
                municipio='Bogotá',
            )
            self.stdout.write(self.style.SUCCESS(f'Estudiante creado id={est.id}'))
        else:
            if options['asignar_cliente'] and est.cliente_id != cliente.id:
                prev = est.cliente_id
                est.cliente = cliente
                est.save(update_fields=['cliente'])
                self.stdout.write(
                    self.style.WARNING(f'Estudiante id={est.id} movido cliente {prev} → {cliente.id}')
                )
            elif est.cliente_id != cliente.id:
                self.stdout.write(
                    self.style.WARNING(
                        f'Estudiante id={est.id} sigue en cliente {est.cliente_id} '
                        f'({getattr(est.cliente, "nombre", "?")}). '
                        'Use --asignar-cliente para reportes B2B bajo Cenipalma.'
                    )
                )
            else:
                self.stdout.write(f'Estudiante reusado id={est.id} en Cenipalma')

        for curso in (c1, c2, c10):
            prog, creado = inscribir_estudiante_en_curso(est, curso)
            self.stdout.write(
                f"  progreso curso={curso.id} prog={prog.id} {'nuevo' if creado else 'existente'}"
            )

        g1.estudiantes.add(est)
        g2.estudiantes.add(est)
        g10.estudiantes.add(est)
        self.stdout.write(self.style.SUCCESS(
            f'OK · tel={tel} en 3 cursos y 3 grupos de {CLIENTE_NOMBRE}. '
            'Analítica: filtrar Organización=Cenipalma.'
        ))
