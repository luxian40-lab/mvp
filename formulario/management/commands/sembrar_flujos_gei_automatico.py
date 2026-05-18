"""Sembra bloques contexto (M4) y balance (M5) en todos los cursos con formulario GEI activo.

Uso en producción (EB SSH o local con DATABASE_URL de prod):
    python manage.py sembrar_flujos_gei_automatico
    python manage.py sembrar_flujos_gei_automatico --cliente "Preserva"
    python manage.py sembrar_flujos_gei_automatico --dry-run
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from formulario.gei_flujos import BLOQUES_GEI
from formulario.models import FlujoPregunta, TipoFormulario


class Command(BaseCommand):
    help = "Crea/actualiza TipoFormulario GEI contexto (módulo 4) y balance (módulo 5) por curso."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cliente",
            type=str,
            default="",
            help="Filtrar por nombre de cliente (contiene, case-insensitive).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra qué haría, sin escribir en BD.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra pasos existentes antes de recrear cada bloque.",
        )

    def handle(self, *args, **opts):
        from core.models import Curso, Modulo

        cliente_filtro = (opts.get("cliente") or "").strip().lower()
        dry = bool(opts.get("dry_run"))
        reset = bool(opts.get("reset"))

        cursos_qs = Curso.objects.filter(tiene_formulario_gei=True, activo=True).select_related(
            "cliente"
        )
        if cliente_filtro:
            cursos_qs = cursos_qs.filter(cliente__nombre__icontains=cliente_filtro)

        if not cursos_qs.exists():
            self.stdout.write(self.style.WARNING("No hay cursos con tiene_formulario_gei=True."))
            return

        total_tf = 0
        for curso in cursos_qs:
            mod4 = Modulo.objects.filter(curso=curso, numero=4).first()
            mod5 = Modulo.objects.filter(curso=curso, numero=5).first()
            if not mod4 or not mod5:
                self.stdout.write(
                    self.style.WARNING(
                        f"Curso id={curso.id} «{curso.nombre}»: falta módulo 4 o 5 — omitido."
                    )
                )
                continue

            cliente = curso.cliente
            scope = f"curso={curso.id} cliente={getattr(cliente, 'nombre', '—')}"

            for bloque, modulo in (("contexto", mod4), ("balance", mod5)):
                meta = BLOQUES_GEI[bloque]
                pasos = meta["pasos"]
                nombre_tf = (
                    f"Ficha GEI {meta['nombre_suffix']} — {curso.nombre} — M{modulo.numero}"
                    if not cliente
                    else (
                        f"Ficha GEI {meta['nombre_suffix']} — {curso.nombre} — "
                        f"M{modulo.numero} — {cliente.nombre}"
                    )
                )

                if dry:
                    self.stdout.write(f"[dry-run] {scope} bloque={bloque} -> {len(pasos)} pasos")
                    continue

                with transaction.atomic():
                    tf, created = TipoFormulario.objects.get_or_create(
                        curso=curso,
                        modulo=modulo,
                        cliente=cliente,
                        defaults={
                            "nombre": nombre_tf,
                            "descripcion": meta["descripcion"],
                            "activo": True,
                        },
                    )
                    if not created:
                        tf.nombre = nombre_tf
                        tf.descripcion = meta["descripcion"]
                        tf.activo = True
                        tf.save()

                    if reset:
                        FlujoPregunta.objects.filter(formulario=tf).delete()

                    existentes = {
                        fp.orden: fp for fp in FlujoPregunta.objects.filter(formulario=tf)
                    }
                    for paso in pasos:
                        fp = existentes.get(paso["orden"])
                        if fp:
                            for k, v in paso.items():
                                if k != "orden":
                                    setattr(fp, k, v)
                            fp.save()
                        else:
                            FlujoPregunta.objects.create(formulario=tf, **paso)

                    n = FlujoPregunta.objects.filter(formulario=tf).count()
                    tag = "+" if created else "~"
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[{tag}] TF id={tf.id} {scope} bloque={bloque} pasos={n}"
                        )
                    )
                    total_tf += 1

        if dry:
            self.stdout.write(self.style.NOTICE("Dry-run: no se escribió nada."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nListo. {total_tf} formularios actualizados."))
