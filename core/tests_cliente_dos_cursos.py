"""
Cliente B2B con 2 cursos + un mismo estudiante inscrito en ambos.

Flujo real:
- Un Cliente puede tener N cursos (FK Curso.cliente).
- Un Estudiante tiene un ProgresoEstudiante por curso (unique estudiante+curso).
- WhatsApp B2B: 1 curso → sin menú (listo). 2+ cursos activos → menú numerado.
- Aprende lista todos los progresos en «Mis cursos».
"""

from django.test import Client, TestCase, override_settings

from core.flujo_whatsapp_b2b import armar_menu_seleccion_cursos, tiene_varios_cursos_activos
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent
from core.selector_curso import (
    asegurar_inscripcion_catalogo_cliente,
    continuar_curso_seleccionado,
    cursos_visibles_para_estudiante,
)

_STATIC = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


class ClienteDosCursosMismoEstudianteTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Pruebas',
            contacto_principal='Coord Pruebas',
            email='pruebas@eki.test',
            telefono='573009990001',
            activo=True,
            portal_productos='cursos',
        )
        self.curso_a = Curso.objects.create(
            nombre='Curso A — Fundamentos',
            cliente=self.org,
            activo=True,
            orden=1,
            emoji='📗',
        )
        self.curso_b = Curso.objects.create(
            nombre='Curso B — Avanzado',
            cliente=self.org,
            activo=True,
            orden=2,
            emoji='📘',
        )
        Modulo.objects.create(curso=self.curso_a, numero=1, titulo='M1 A', contenido='hola A')
        Modulo.objects.create(curso=self.curso_b, numero=1, titulo='M1 B', contenido='hola B')

        self.est = Estudiante.objects.create(
            cedula='100200300',
            nombre='Ana Pruebas',
            telefono='573001112233',
            cliente=self.org,
            activo=True,
            estado_onboarding='completado',
        )
        # Misma persona inscrita en los dos cursos del cliente
        self.prog_a = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso_a,
            completado=False,
            modulo_actual=self.curso_a.modulos.first(),
        )
        self.prog_b = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso_b,
            completado=False,
            modulo_actual=self.curso_b.modulos.first(),
        )

    def test_cliente_tiene_dos_cursos_visibles(self):
        cursos = list(cursos_visibles_para_estudiante(self.est))
        self.assertEqual(len(cursos), 2)
        self.assertEqual({c.pk for c in cursos}, {self.curso_a.pk, self.curso_b.pk})

    def test_un_progreso_por_curso_mismo_estudiante(self):
        progresos = ProgresoEstudiante.objects.filter(estudiante=self.est)
        self.assertEqual(progresos.count(), 2)
        with self.assertRaises(Exception):
            ProgresoEstudiante.objects.create(
                estudiante=self.est,
                curso=self.curso_a,
                completado=False,
            )

    def test_whatsapp_b2b_con_dos_cursos_muestra_menu(self):
        self.assertTrue(tiene_varios_cursos_activos(self.est))
        menu = armar_menu_seleccion_cursos(self.est)
        self.assertIn('Curso A', menu)
        self.assertIn('Curso B', menu)
        self.assertIn('número', menu.lower())
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_seleccion_curso')
        self.assertEqual((self.est.contexto_temporal or {}).get('tipo'), 'seleccion_curso')

        # listo / continuar → menú, no auto-elige el más reciente
        resp = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertIn('varios cursos', resp.lower())
        self.assertIn('Curso A', resp)
        self.assertIn('Curso B', resp)

        # elegir 1 → Curso B (orden por fecha_inicio desc: B primero)
        elegido = continuar_curso_seleccionado(self.est.id, 1, '1')
        self.assertIn('Curso B', elegido)
        self.est.refresh_from_db()
        self.assertEqual((self.est.contexto_temporal or {}).get('curso_activo_id'), self.curso_b.pk)

    def test_saludo_b2b_dos_cursos_menu(self):
        msg = get_response_for_intent('saludo', self.est.nombre, estudiante_id=self.est.id)
        self.assertIn('Curso A', msg)
        self.assertIn('Curso B', msg)
        self.assertNotIn('Escribe el número (1, 2 o 3)', msg)

    def test_asegurar_inscripcion_sigue_existiendo_para_un_curso(self):
        """Con un solo progreso incompleto, resolver sigue el más reciente."""
        self.prog_a.completado = True
        self.prog_a.save(update_fields=['completado'])
        self.assertFalse(tiene_varios_cursos_activos(self.est))
        actual = asegurar_inscripcion_catalogo_cliente(self.est)
        self.assertEqual(actual.curso_id, self.curso_b.pk)

    @override_settings(STORAGES=_STATIC, SECURE_SSL_REDIRECT=False)
    def test_aprende_lista_ambos_cursos(self):
        http = Client()
        r = http.post('/aprende/estudiante/login/', {
            'cedula': '100200300',
            'telefono': '3001112233',
        })
        self.assertEqual(r.status_code, 302)
        r2 = http.get('/aprende/estudiante/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Curso A')
        self.assertContains(r2, 'Curso B')
        r_a = http.get(f'/aprende/estudiante/curso/{self.curso_a.pk}/')
        r_b = http.get(f'/aprende/estudiante/curso/{self.curso_b.pk}/')
        self.assertEqual(r_a.status_code, 200)
        self.assertEqual(r_b.status_code, 200)
