"""Slice RAG aditivo: packs compañero/Claudia no ciegan docs compartidos ni CE."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.models import Cliente, Curso, DocumentoRAG, Modulo
from core.rag_uso import (
    USO_CLAUDIA,
    USO_COMPANERO,
    USO_TODOS,
    chunk_visible_para_uso,
    filtrar_chunks_por_uso,
    normalizar_uso,
)


class ChunkVisibleParaUsoTests(TestCase):
    def test_sin_uso_ve_todo_incluye_packs(self):
        self.assertTrue(chunk_visible_para_uso({'uso': USO_CLAUDIA}, None))
        self.assertTrue(chunk_visible_para_uso({'uso': USO_COMPANERO}, ''))
        self.assertTrue(chunk_visible_para_uso({'uso': USO_CLAUDIA}, USO_TODOS))

    def test_chunk_viejo_sin_metadata_sigue_visible(self):
        self.assertTrue(chunk_visible_para_uso({}, USO_COMPANERO))
        self.assertTrue(chunk_visible_para_uso({'tipo': 'faq'}, USO_CLAUDIA))
        self.assertTrue(chunk_visible_para_uso({'uso': ''}, USO_COMPANERO))
        self.assertTrue(chunk_visible_para_uso({'uso': USO_TODOS}, USO_CLAUDIA))

    def test_pack_no_se_cuela_en_el_otro_agente(self):
        self.assertFalse(chunk_visible_para_uso({'uso': USO_CLAUDIA}, USO_COMPANERO))
        self.assertFalse(chunk_visible_para_uso({'uso': USO_COMPANERO}, USO_CLAUDIA))

    def test_pack_propio_si_visible(self):
        self.assertTrue(chunk_visible_para_uso({'uso': USO_COMPANERO}, USO_COMPANERO))
        self.assertTrue(chunk_visible_para_uso({'uso': USO_CLAUDIA}, USO_CLAUDIA))

    def test_filtrar_prioriza_visibles_y_respeta_limite(self):
        docs = [
            {'uso': USO_CLAUDIA, 'contenido': 'rubrica'},
            {'uso': USO_TODOS, 'contenido': 'modulo'},
            {'uso': USO_COMPANERO, 'contenido': 'faq'},
            {'uso': USO_TODOS, 'contenido': 'guia'},
        ]
        out = filtrar_chunks_por_uso(docs, USO_COMPANERO, limite=2)
        self.assertEqual([d['contenido'] for d in out], ['modulo', 'faq'])

    def test_course_engine_sin_filtro_conserva_claudia(self):
        docs = [
            {'uso': USO_CLAUDIA, 'contenido': 'rubrica'},
            {'uso': USO_TODOS, 'contenido': 'temario'},
        ]
        out = filtrar_chunks_por_uso(docs, None, limite=10)
        self.assertEqual(len(out), 2)

    def test_alias_dario_y_facilitadora(self):
        self.assertEqual(normalizar_uso('Darío'), USO_COMPANERO)
        self.assertEqual(normalizar_uso('facilitadora'), USO_CLAUDIA)


class DocumentoRAGUsoDefaultTests(TestCase):
    def test_default_es_todos(self):
        curso = Curso.objects.create(nombre='Curso RAG uso')
        doc = DocumentoRAG.objects.create(
            curso=curso,
            nombre='manual_compartido',
            tipo='contenido',
        )
        self.assertEqual(doc.uso_agente, USO_TODOS)

    def test_indexar_pasa_uso_al_manager(self):
        from django.core.files.base import ContentFile

        curso = Curso.objects.create(nombre='Curso RAG uso 2')
        doc = DocumentoRAG(
            curso=curso,
            nombre='faq_companero',
            tipo='faq',
            uso_agente=USO_COMPANERO,
            estado='pendiente',
        )
        doc.archivo.save('faq.txt', ContentFile(b'faq companero'), save=True)
        with patch(
            'core.rag_manager.rag_manager.procesar_documento', return_value=2
        ) as mock_proc:
            n = doc.indexar()
        self.assertEqual(n, 2)
        self.assertEqual(mock_proc.call_args.kwargs.get('uso'), USO_COMPANERO)
        self.assertEqual(mock_proc.call_args.kwargs.get('tipo'), 'faq')


class TutorPideUsoAgenteTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='Org RAG packs',
            contacto_principal='A',
            email='ragpacks@test.co',
            telefono='573001110077',
        )
        self.curso = Curso.objects.create(
            nombre='Innovación rural',
            cliente=self.cli,
            descripcion='Gestión de proyectos.',
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='Cierre',
            contenido='Priorizar iniciativas.',
        )

    @patch('core.tutor_ia_modulo._get_client')
    def test_companero_consulta_pack_companero(self, mock_client):
        from core.tutor_ia_modulo import generar_respuesta_asistente

        mock_client.return_value = MagicMock(
            chat=MagicMock(
                completions=MagicMock(
                    create=MagicMock(
                        return_value=MagicMock(
                            choices=[MagicMock(message=MagicMock(content='Respuesta anclada.'))]
                        )
                    )
                )
            )
        )
        with patch(
            'core.rag_manager.rag_manager.obtener_contexto_para_ia', return_value=''
        ) as mock_rag:
            generar_respuesta_asistente(
                [self.mod],
                'cómo priorizo el proyecto',
                estudiante_nombre='Ana',
                nombre_asistente='Darío',
            )
        self.assertEqual(mock_rag.call_args.kwargs.get('uso'), USO_COMPANERO)

    @patch('core.tutor_ia_modulo._get_client')
    def test_reto_claudia_consulta_pack_claudia(self, mock_client):
        from core.tutor_ia_modulo import generar_reto_facilitador

        mock_client.return_value = MagicMock(
            chat=MagicMock(
                completions=MagicMock(
                    create=MagicMock(
                        return_value=MagicMock(
                            choices=[MagicMock(message=MagicMock(content='Reto breve.'))]
                        )
                    )
                )
            )
        )
        with patch(
            'core.rag_manager.rag_manager.obtener_contexto_para_ia', return_value=''
        ) as mock_rag:
            generar_reto_facilitador(
                [self.mod],
                self.curso.nombre,
                curso=self.curso,
                modulo_checkpoint=self.mod,
            )
        self.assertEqual(mock_rag.call_args.kwargs.get('uso'), USO_CLAUDIA)

    @patch('core.tutor_ia_modulo._get_client')
    def test_evaluacion_claudia_consulta_pack_claudia(self, mock_client):
        from core.tutor_ia_modulo import evaluar_reto_facilitador

        mock_client.return_value = MagicMock(
            chat=MagicMock(
                completions=MagicMock(
                    create=MagicMock(
                        return_value=MagicMock(
                            choices=[MagicMock(message=MagicMock(
                                content='1. Bien. 2. Falta. 3. Puntaje total: 6/10\n'
                                '4. Desglose: Enfoque 2/3 | Fundamentación 2/4 | Claridad 2/3'
                            ))]
                        )
                    )
                )
            )
        )
        with patch(
            'core.rag_manager.rag_manager.obtener_contexto_para_ia', return_value=''
        ) as mock_rag:
            evaluar_reto_facilitador(
                [self.mod],
                'Priorizaría la iniciativa de riego esta semana.',
                '¿Qué haría usted?',
                estudiante_nombre='Ana',
                curso_nombre=self.curso.nombre,
            )
        self.assertEqual(mock_rag.call_args.kwargs.get('uso'), USO_CLAUDIA)
