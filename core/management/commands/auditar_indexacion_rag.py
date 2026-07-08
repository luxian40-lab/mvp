"""Diagnóstico de documentos con error o pendiente en biblioteca Nat y RAG comercial."""

from django.core.management.base import BaseCommand

from core.models import BibliotecaConocimiento, DocumentoRAGComercial


class Command(BaseCommand):
    help = 'Lista documentos RAG con error/pendiente y resume causas.'

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, default=0, help='Filtrar por cliente (0=todos)')
        parser.add_argument('--limite', type=int, default=30, help='Máximo ítems a mostrar por tabla')
        parser.add_argument('--reindexar-errores', action='store_true', help='Encolar reindexación de errores')

    def handle(self, *args, **options):
        from core.extractores_documento import _ocr_disponible
        from core.rag_comercial_manager import rag_comercial_manager

        cliente_id = options['cliente_id']
        limite = options['limite']

        self.stdout.write('=== Infraestructura RAG ===')
        self.stdout.write(f'  ChromaDB disponible: {rag_comercial_manager.disponible}')
        self.stdout.write(f'  OCR Tesseract: {_ocr_disponible()}')

        bib_qs = BibliotecaConocimiento.objects.filter(estado_rag__in=('error', 'pendiente'))
        com_qs = DocumentoRAGComercial.objects.filter(estado__in=('error', 'pendiente'))
        if cliente_id:
            bib_qs = bib_qs.filter(cliente_id=cliente_id)
            com_qs = com_qs.filter(cliente_id=cliente_id)

        self.stdout.write(
            f'\n=== Biblioteca Nat: {bib_qs.filter(estado_rag="error").count()} error, '
            f'{bib_qs.filter(estado_rag="pendiente").count()} pendiente ==='
        )
        for item in bib_qs.order_by('-fecha_creacion')[:limite]:
            self.stdout.write(
                f'  id={item.pk} [{item.estado_rag}] «{item.titulo[:60]}» '
                f'| {item.rag_error_detalle[:120] or "(sin detalle)"}'
            )

        self.stdout.write(
            f'\n=== DocumentoRAGComercial: {com_qs.filter(estado="error").count()} error, '
            f'{com_qs.filter(estado="pendiente").count()} pendiente ==='
        )
        for doc in com_qs.order_by('-fecha_subida')[:limite]:
            self.stdout.write(
                f'  id={doc.pk} [{doc.estado}] «{doc.nombre[:60]}» '
                f'| {doc.error_indexacion[:120] or "(sin detalle)"}'
            )

        if options['reindexar_errores']:
            from core.biblioteca_nat_service import reindexar_item

            n = 0
            for item in BibliotecaConocimiento.objects.filter(estado_rag='error'):
                if cliente_id and item.cliente_id != cliente_id:
                    continue
                reindexar_item(item)
                n += 1
            from core.tasks import indexar_documento_rag_por_id

            m = 0
            for doc in DocumentoRAGComercial.objects.filter(estado='error'):
                if cliente_id and doc.cliente_id != cliente_id:
                    continue
                doc.estado = 'pendiente'
                doc.save(update_fields=['estado'])
                indexar_documento_rag_por_id.delay('core', 'DocumentoRAGComercial', doc.pk)
                m += 1
            self.stdout.write(self.style.SUCCESS(f'\nEncolados: {n} biblioteca, {m} comercial'))
