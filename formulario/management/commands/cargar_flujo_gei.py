"""Carga flujos GEI por bloque (contexto M4 / balance M5).

Uso:
    python manage.py cargar_flujo_gei <curso_id> <modulo_id> --bloque contexto --reset
    python manage.py cargar_flujo_gei <curso_id> <modulo_id> --bloque balance --reset
    python manage.py cargar_flujo_gei <curso_id> <modulo_id> --cliente_id <ID> --bloque contexto --reset
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from formulario.gei_flujos import BLOQUES_GEI


class Command(BaseCommand):
    help = (
        "Crea/actualiza TipoFormulario GEI para un bloque: "
        "contexto (7 pasos, módulo 4) o balance (6 pasos, módulo 5)."
    )

    def add_arguments(self, parser):
        parser.add_argument("curso_id", type=int, help="ID del curso")
        parser.add_argument(
            "modulo_id",
            type=int,
            help="ID del módulo disparador (4=contexto, 5=balance)",
        )
        parser.add_argument(
            "--bloque",
            choices=("contexto", "balance"),
            required=True,
            help="contexto = 7 pasos base; balance = combustible, residuos y bosque",
        )
        parser.add_argument(
            "--cliente_id",
            type=int,
            default=None,
            help="ID de Cliente. Si se omite, formulario global (cliente=None).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra los pasos existentes del formulario y los recrea.",
        )

    def handle(self, *args, **opts):
        bloque = opts["bloque"]
        meta = BLOQUES_GEI[bloque]
        pasos = meta["pasos"]

        try:
            from formulario.models import FlujoPregunta, TipoFormulario
        except Exception as exc:
            raise CommandError(f"No se pudo importar formulario.models: {exc}")

        nombres_tabla = set(connection.introspection.table_names())
        if "formulario_tipoformulario" not in nombres_tabla:
            raise CommandError(
                "La tabla 'formulario_tipoformulario' no existe. "
                "Ejecuta: python manage.py migrate formulario"
            )

        try:
            from core.models import Cliente, Curso, Modulo
        except Exception as exc:
            raise CommandError(f"No se pudo importar core.models: {exc}")

        curso_id = int(opts["curso_id"])
        modulo_id = int(opts["modulo_id"])
        cliente_id = opts.get("cliente_id")
        reset = bool(opts.get("reset"))

        curso = Curso.objects.filter(id=curso_id).first()
        if not curso:
            raise CommandError(f"No existe Curso id={curso_id}")
        modulo = Modulo.objects.filter(id=modulo_id, curso_id=curso.id).first()
        if not modulo:
            raise CommandError(f"No existe Modulo id={modulo_id} para Curso id={curso_id}")
        cliente = None
        if cliente_id is not None:
            cliente = Cliente.objects.filter(id=int(cliente_id)).first()
            if not cliente:
                raise CommandError(f"No existe Cliente id={cliente_id}")

        scope = (
            f"bloque={bloque} curso={curso.id} modulo={modulo.id} "
            f"cliente={cliente.id if cliente else 'GLOBAL'}"
        )
        nombre_tf = (
            f"Ficha GEI {meta['nombre_suffix']} — {curso.nombre} — M{modulo.numero}"
            if cliente is None
            else (
                f"Ficha GEI {meta['nombre_suffix']} — {curso.nombre} — "
                f"M{modulo.numero} — {cliente.nombre}"
            )
        )

        with transaction.atomic():
            tf, creado = TipoFormulario.objects.get_or_create(
                curso=curso,
                modulo=modulo,
                cliente=cliente,
                defaults={
                    "nombre": nombre_tf,
                    "descripcion": meta["descripcion"],
                    "activo": True,
                },
            )
            if not creado:
                tf.nombre = nombre_tf
                tf.descripcion = meta["descripcion"]
                tf.activo = True
                tf.save()

            if creado:
                self.stdout.write(self.style.SUCCESS(f"[+] TipoFormulario creado | {scope} | id={tf.id}"))
            else:
                self.stdout.write(f"[=] TipoFormulario actualizado | {scope} | id={tf.id}")

            if reset:
                borrados = FlujoPregunta.objects.filter(formulario=tf).count()
                FlujoPregunta.objects.filter(formulario=tf).delete()
                self.stdout.write(self.style.WARNING(f"[reset] eliminados {borrados} pasos previos"))

            existentes = {fp.orden: fp for fp in FlujoPregunta.objects.filter(formulario=tf)}
            for paso in pasos:
                fp = existentes.get(paso["orden"])
                if fp:
                    actualizado = False
                    for k, v in paso.items():
                        if k == "orden":
                            continue
                        if getattr(fp, k) != v:
                            setattr(fp, k, v)
                            actualizado = True
                    if actualizado:
                        fp.save()
                        self.stdout.write(f"  [~] paso {paso['orden']} ({paso['campo_destino']})")
                    else:
                        self.stdout.write(f"  [=] paso {paso['orden']} ({paso['campo_destino']})")
                else:
                    FlujoPregunta.objects.create(formulario=tf, **paso)
                    self.stdout.write(self.style.SUCCESS(
                        f"  [+] paso {paso['orden']} ({paso['campo_destino']})"
                    ))

        total = FlujoPregunta.objects.filter(formulario=tf).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nListo. TipoFormulario id={tf.id} bloque={bloque} → {total} pasos."
        ))
        if total != len(pasos):
            self.stdout.write(self.style.WARNING(
                f"⚠ Esperaban {len(pasos)} pasos, hay {total}. Usa --reset."
            ))
