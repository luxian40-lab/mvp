"""Inventario de señales territoriales ya presentes en la plataforma (visión Mes 1)."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.db.models import Count, Q


class Command(BaseCommand):
    help = (
        'Inventario de señales territoriales (municipio, coords, telemetría). '
        'Salida texto o --json.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', help='Imprimir JSON.')
        parser.add_argument(
            '--cliente-id',
            type=int,
            default=None,
            help='Limitar conteos de estudiantes a un Cliente.',
        )

    def handle(self, *args, **options):
        from core.models import (
            AliadoEmpleabilidad,
            ContextoAgroSession,
            Estudiante,
            EstudianteEventoAprendizaje,
            MisionEmpleabilidad,
        )

        cliente_id = options['cliente_id']
        est = Estudiante.objects.all()
        if cliente_id:
            est = est.filter(cliente_id=cliente_id)

        total = est.count()
        con_muni = est.exclude(municipio='').exclude(municipio__isnull=True).count()
        con_depto = est.exclude(departamento='').exclude(departamento__isnull=True).count()
        con_detalle = est.exclude(ubicacion_detalle='').exclude(ubicacion_detalle__isnull=True).count()
        con_tid = est.exclude(territory_id='').exclude(territory_id__isnull=True).count()
        con_texto = est.filter(Q(municipio__gt='') | Q(departamento__gt='')).count()

        # Resolución en vivo (muestra cobertura potencial sin escribir)
        from portal.geo_catalogo import resolver_ubicacion

        mapeados = 0
        ambiguos = 0
        for e in est.only('municipio', 'departamento').iterator(chunk_size=500):
            if not (e.municipio or e.departamento):
                continue
            u = resolver_ubicacion(e.municipio or '', e.departamento or '')
            if u.territory_id:
                mapeados += 1
            elif u.nivel == 'departamento':
                ambiguos += 1

        pct_tid = round(100.0 * con_tid / total, 1) if total else 0.0
        pct_potencial = round(100.0 * mapeados / total, 1) if total else 0.0
        pct_con_texto = round(100.0 * con_texto / total, 1) if total else 0.0

        agro = ContextoAgroSession.objects.all()
        agro_muni = agro.exclude(municipio='').count()
        agro_vereda = agro.exclude(vereda='').count()
        agro_coords = agro.filter(latitud__isnull=False, longitud__isnull=False).count()

        misiones = MisionEmpleabilidad.objects.all()
        misiones_coords = misiones.filter(latitud__isnull=False, longitud__isnull=False).count()
        aliados = AliadoEmpleabilidad.objects.all()
        aliados_coords = aliados.filter(latitud__isnull=False, longitud__isnull=False).count()

        eventos = (
            EstudianteEventoAprendizaje.objects.values('tipo')
            .annotate(n=Count('id'))
            .order_by('-n')
        )
        eventos_por_tipo = {row['tipo']: row['n'] for row in eventos}

        report = {
            'estudiantes': {
                'total': total,
                'con_municipio_texto': con_muni,
                'con_departamento_texto': con_depto,
                'con_ubicacion_texto': con_texto,
                'con_ubicacion_detalle': con_detalle,
                'con_territory_id': con_tid,
                'pct_territory_id': pct_tid,
                'resolucion_potencial_divipola': mapeados,
                'pct_resolucion_potencial': pct_potencial,
                'solo_departamento_sin_mpio': ambiguos,
                'pct_con_ubicacion_texto': pct_con_texto,
            },
            'nat_contexto_agro': {
                'total_sesiones': agro.count(),
                'con_municipio': agro_muni,
                'con_vereda': agro_vereda,
                'con_lat_lon': agro_coords,
            },
            'empleabilidad': {
                'misiones_total': misiones.count(),
                'misiones_con_coords': misiones_coords,
                'aliados_total': aliados.count(),
                'aliados_con_coords': aliados_coords,
            },
            'telemetria_aprendizaje': {
                'total_eventos': sum(eventos_por_tipo.values()),
                'por_tipo': eventos_por_tipo,
            },
            'catalogo': {
                'divipola_municipios': self._divipola_count(),
            },
        }

        if options['json']:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        e = report['estudiantes']
        self.stdout.write(self.style.SUCCESS('=== Inventario señales territoriales ==='))
        self.stdout.write(f"Estudiantes total: {e['total']}")
        self.stdout.write(
            f"  Con municipio/depto texto: {e['con_ubicacion_texto']} ({e['pct_con_ubicacion_texto']}%)"
        )
        self.stdout.write(f"  Con territory_id: {e['con_territory_id']} ({e['pct_territory_id']}%)")
        self.stdout.write(
            f"  Resolución potencial DIVIPOLA: {e['resolucion_potencial_divipola']} "
            f"({e['pct_resolucion_potencial']}%)"
        )
        self.stdout.write(f"  Solo departamento (sin código mpio): {e['solo_departamento_sin_mpio']}")
        a = report['nat_contexto_agro']
        self.stdout.write(
            f"Nat/agro: sesiones={a['total_sesiones']} municipio={a['con_municipio']} "
            f"vereda={a['con_vereda']} coords={a['con_lat_lon']}"
        )
        em = report['empleabilidad']
        self.stdout.write(
            f"Empleabilidad: misiones coords={em['misiones_con_coords']}/{em['misiones_total']} "
            f"aliados coords={em['aliados_con_coords']}/{em['aliados_total']}"
        )
        t = report['telemetria_aprendizaje']
        self.stdout.write(f"Telemetría aprendizaje: {t['total_eventos']} eventos")
        for tipo, n in sorted(t['por_tipo'].items(), key=lambda x: -x[1])[:12]:
            self.stdout.write(f"  - {tipo}: {n}")
        self.stdout.write(f"Catálogo DIVIPOLA embebido: {report['catalogo']['divipola_municipios']} municipios")

    def _divipola_count(self) -> int:
        from portal.geo_catalogo import _divipola_por_clave

        return len(_divipola_por_clave())
