from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from core.models import DocumentoRAGComercial


class Command(BaseCommand):
    help = "Carga masiva de documentos al RAG comercial desde una carpeta local"

    def add_arguments(self, parser):
        parser.add_argument("--ruta", required=True, help="Carpeta con archivos (.pdf, .docx, .txt)")
        parser.add_argument("--canal", default="bot_comercial", help="Canal RAG (bot_comercial o agro_nexo)")
        parser.add_argument("--cliente-id", type=int, default=0, help="ID cliente (0 = general)")
        parser.add_argument("--tipo", default="general", help="Tipo de documento (producto, precio, informe_tecnico, faq, politica, promo, general)")
        parser.add_argument("--indexar", action="store_true", help="Indexar inmediatamente al cargar")

    def handle(self, *args, **options):
        base = Path(options["ruta"]).expanduser().resolve()
        canal = (options["canal"] or "bot_comercial").strip()
        cliente_id = int(options.get("cliente_id") or 0)
        tipo = (options["tipo"] or "general").strip()
        indexar = bool(options.get("indexar"))

        tipos_validos = {k for k, _ in DocumentoRAGComercial.TIPO_CHOICES}
        if tipo not in tipos_validos:
            raise CommandError(f"Tipo inválido: {tipo}. Usa uno de: {', '.join(sorted(tipos_validos))}")

        if not base.exists() or not base.is_dir():
            raise CommandError(f"Ruta no válida: {base}")

        permitidos = {".pdf", ".docx", ".txt"}
        archivos = [p for p in sorted(base.iterdir()) if p.is_file() and p.suffix.lower() in permitidos]
        if not archivos:
            raise CommandError("No se encontraron archivos .pdf/.docx/.txt en la carpeta")

        creados = 0
        omitidos = 0
        indexados = 0

        for ruta_archivo in archivos:
            nombre_doc = ruta_archivo.stem[:200]
            existente = DocumentoRAGComercial.objects.filter(
                cliente_id=(cliente_id or None),
                canal=canal,
                nombre=nombre_doc,
            ).first()
            if existente:
                omitidos += 1
                self.stdout.write(self.style.WARNING(f"[SKIP] Ya existe: {nombre_doc}"))
                continue

            doc = DocumentoRAGComercial(
                cliente_id=(cliente_id or None),
                canal=canal,
                nombre=nombre_doc,
                tipo=tipo,
                estado="pendiente",
            )
            with ruta_archivo.open("rb") as fh:
                doc.archivo.save(ruta_archivo.name, File(fh), save=False)
            doc.save()
            creados += 1
            self.stdout.write(self.style.SUCCESS(f"[OK] Cargado: {nombre_doc}"))

            if indexar:
                chunks = doc.indexar()
                if chunks > 0:
                    indexados += 1
                    self.stdout.write(self.style.SUCCESS(f"    -> Indexado ({chunks} chunks)"))
                else:
                    self.stdout.write(self.style.WARNING("    -> No indexado (revisar logs/estado)"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Resumen: creados={creados}, omitidos={omitidos}, indexados={indexados}"
            )
        )
