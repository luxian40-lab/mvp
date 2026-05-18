"""Sembra flujos GEI conectando directo a RDS (requiere DATABASE_URL en .env y red al RDS).

Uso local con VPN o IP RDS en security group:
    python manage.py sembrar_gei_via_rds --reset
"""
from __future__ import annotations

import os

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sembra flujos GEI en la BD apuntada por DATABASE_URL (produccion desde .env)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--cliente", type=str, default="")

    def handle(self, *args, **opts):
        db_url = (os.environ.get("DATABASE_URL") or "").strip()
        if not db_url:
            self.stderr.write("DATABASE_URL no definida en el entorno.")
            return
        from django.conf import settings

        engine = settings.DATABASES["default"]["ENGINE"]
        if "postgresql" not in engine:
            self.stderr.write(
                f"No hay PostgreSQL activo (engine={engine}). "
                "Instale psycopg y asegure que RDS sea alcanzable desde su red."
            )
            return
        args = ["sembrar_flujos_gei_automatico"]
        if opts.get("reset"):
            args.append("--reset")
        if opts.get("cliente"):
            args.extend(["--cliente", opts["cliente"]])
        call_command(*args)
        call_command("crear_cliente_preserva")
        self.stdout.write(self.style.SUCCESS("Flujos GEI sembrados en la BD configurada."))
