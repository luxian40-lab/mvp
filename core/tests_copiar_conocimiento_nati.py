"""Tests copia de conocimiento Nati (Agronexo / general → cliente)."""

from django.core.files.base import ContentFile
from django.test import TestCase

from core.copiar_conocimiento_nati import (
    FuenteConocimientoNoEncontrada,
    copiar_conocimiento_a_cliente,
)
from core.models import BibliotecaConocimiento, Cliente, DocumentoRAGComercial


class CopiarConocimientoNatiTests(TestCase):
    def setUp(self):
        self.agro = Cliente.objects.create(
            nombre='Agronexo Base',
            contacto_principal='A',
            email='agro@test.com',
            telefono='573001000001',
            activo=True,
            portal_productos='nat',
        )
        self.destino = Cliente.objects.create(
            nombre='Cliente Destino Nati',
            contacto_principal='B',
            email='dest@test.com',
            telefono='573001000002',
            activo=True,
            portal_productos='nat',
        )

    def test_copia_biblioteca_y_rag_general(self):
        BibliotecaConocimiento.objects.create(
            cliente=self.agro,
            titulo='Protocolo MIP café',
            slug='protocolo-mip',
            formato='texto',
            texto_contenido='Manejo integrado de plagas en café arabica.',
            estado_publicacion='publicado',
            estado_rag='indexado',
            chunks_indexados=3,
        )
        general = DocumentoRAGComercial(
            cliente=None,
            canal='bot_comercial',
            nombre='manual_general_suelo',
            tipo='informe_tecnico',
            descripcion='Suelos Colombia',
            estado='indexado',
        )
        general.archivo.save('manual.txt', ContentFile(b'Suelo franco arenoso.'), save=False)
        general.save()

        r = copiar_conocimiento_a_cliente(self.destino, encolar_index=False)
        self.assertEqual(r.bib_copiados, 1)
        self.assertEqual(r.rag_copiados, 1)
        self.assertTrue(
            BibliotecaConocimiento.objects.filter(
                cliente=self.destino, titulo='Protocolo MIP café'
            ).exists()
        )
        self.assertTrue(
            DocumentoRAGComercial.objects.filter(
                cliente=self.destino, nombre='manual_general_suelo'
            ).exists()
        )
        # Segunda corrida no duplica
        r2 = copiar_conocimiento_a_cliente(self.destino, encolar_index=False)
        self.assertEqual(r2.bib_copiados, 0)
        self.assertEqual(r2.bib_omitidos, 1)
        self.assertEqual(r2.rag_omitidos, 1)

    def test_sin_fuente_falla(self):
        vacio = Cliente.objects.create(
            nombre='Sin Docs SA',
            contacto_principal='C',
            email='vacio@test.com',
            telefono='573001000003',
            activo=True,
        )
        # Borrar agro docs
        BibliotecaConocimiento.objects.all().delete()
        DocumentoRAGComercial.objects.all().delete()
        with self.assertRaises(FuenteConocimientoNoEncontrada):
            copiar_conocimiento_a_cliente(vacio, origen=self.agro, encolar_index=False)
