"""Aislamiento: un usuario de A no ve marcadores ZZB- de la organización B."""
import io
import re
import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone

from aprende.middleware import APRENDE_EST_SESSION_KEY
from aprende.models import EntregaTarea, TareaCurso
from core.models import (
    BibliotecaConocimiento,
    Campana,
    Cliente,
    Curso,
    Estudiante,
    EventoIA,
    Modulo,
    PasoModulo,
    ProductoCatalogo,
    ProductoComercial,
    ProgresoEstudiante,
    SandboxCanalSesion,
    SeccionModulo,
    SolicitudSoporte,
    WhatsappLog,
)
from core.models_certificados import Certificado
from core.models_extras import GrupoEstudiantes
from formulario.models import FichaGEI
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario

_PARAM = re.compile(r'<(?:[^:>]+:)?([^>]+)>')
_MARCA = 'ZZB-'
_TEL_B = '573990000001'
_CEDULA_B = '9990000001'


def _rutas(patterns):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _rutas(entry.url_patterns)
        elif isinstance(entry, URLPattern):
            yield entry


def _bytes(resp) -> bytes:
    if getattr(resp, 'streaming', False):
        return b''.join(resp.streaming_content)
    return resp.content


def _texto(resp) -> str:
    tipo = (resp.get('Content-Type') or '').lower()
    raw = _bytes(resp)
    if 'spreadsheet' in tipo or raw[:2] == b'PK':
        try:
            import openpyxl

            libro = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            partes = []
            for hoja in libro.worksheets:
                for fila in hoja.iter_rows(values_only=True):
                    partes.append(' '.join('' if c is None else str(c) for c in fila))
            return '\n'.join(partes)
        except Exception:
            return raw.decode('utf-8', errors='replace')
    return raw.decode('utf-8', errors='replace')


@override_settings(
    SECURE_SSL_REDIRECT=False,
    RATE_LIMIT_ENABLED=False,
    INTEGRACION_API_REQUIRE_KEY=True,
    INTEGRACION_API_KEY='iso-key-a',
)
class AislamientoPortalTests(TestCase):
    def setUp(self):
        self.org_a = Cliente.objects.create(
            nombre='Org A',
            contacto_principal='Ana',
            email='iso-a@test.com',
            telefono='573001110001',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
            tipo_proyecto='cursos',
        )
        self.org_b = Cliente.objects.create(
            nombre='ZZB-ORG-001',
            contacto_principal='ZZB-CONTACTO',
            email='iso-b@test.com',
            telefono='573990000001',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
            tipo_proyecto='cursos',
        )
        self.curso_a = Curso.objects.create(
            nombre='Curso A', descripcion='desc a', cliente=self.org_a, activo=True,
        )
        self.curso_b = Curso.objects.create(
            nombre='ZZB-CURSO', descripcion='ZZB-CURSO-DESC', cliente=self.org_b, activo=True,
        )
        self.mod_b = Modulo.objects.create(
            curso=self.curso_b, numero=1, titulo='ZZB-MODULO', descripcion='d', contenido='ZZB-MODULO-TXT',
        )
        self.sec_b = SeccionModulo.objects.create(modulo=self.mod_b, orden=1, titulo='ZZB-SECCION')
        self.paso_b = PasoModulo.objects.create(
            modulo=self.mod_b, seccion=self.sec_b, orden=1, titulo='ZZB-PASO', contenido='ZZB-PASO-TXT',
        )
        self.est_a = Estudiante.objects.create(
            cedula='1000000001', nombre='Ana A', telefono='573001110101', cliente=self.org_a,
        )
        self.est_b = Estudiante.objects.create(
            cedula=_CEDULA_B, nombre='ZZB-NOMBRE-001', telefono=_TEL_B, cliente=self.org_b,
        )
        ProgresoEstudiante.objects.create(estudiante=self.est_a, curso=self.curso_a)
        self.grupo_b = GrupoEstudiantes.objects.create(nombre='ZZB-GRUPO', cliente=self.org_b, activo=True)
        self.grupo_b.estudiantes.add(self.est_b)
        self.campana_b = Campana.objects.create(nombre='ZZB-CAMPANA', cliente=self.org_b)
        self.pqrs_b = SolicitudSoporte.objects.create(
            estudiante=self.est_b, mensaje_original='ZZB-PQRS', estado='pendiente',
        )
        self.ficha_b = FichaGEI.objects.create(
            estudiante=self.est_b, cliente=self.org_b, curso=self.curso_b, nombre_finca='ZZB-FINCA',
        )
        self.biblio_b = BibliotecaConocimiento.objects.create(
            cliente=self.org_b, titulo='ZZB-BIBLIO', texto_contenido='ZZB-BIBLIO-TXT',
        )
        self.catalogo_b = ProductoCatalogo.objects.create(
            cliente=self.org_b, nombre='ZZB-CATALOGO',
        )
        self.precio_b = ProductoComercial.objects.create(
            cliente=self.org_b, nombre='ZZB-PRECIO', sku='ZZB-SKU', precio=1,
        )
        self.cert_b = Certificado.objects.create(
            estudiante=self.est_b,
            curso=self.curso_b,
            calificacion_final=90,
            fecha_inicio=date(2026, 1, 1),
            fecha_completado=date(2026, 3, 1),
            emitido=True,
            fecha_emision=timezone.now(),
            codigo_verificacion='eki-ISO-B-0001',
            organizacion_emisora='ZZB-ORG-001',
            hash_sha256='b' * 64,
        )
        self.tarea_b = TareaCurso.objects.create(
            curso=self.curso_b, modulo=self.mod_b, titulo='ZZB-TAREA', instrucciones='ZZB-TAREA-TXT',
        )
        self.entrega_b = EntregaTarea.objects.create(
            tarea=self.tarea_b,
            estudiante=self.est_b,
            archivo=SimpleUploadedFile('zzb.txt', b'ZZB-ENTREGA'),
            nombre_archivo='ZZB-ENTREGA.txt',
            comentario_estudiante='ZZB-ENTREGA-TXT',
        )
        WhatsappLog.objects.create(
            telefono=_TEL_B, mensaje='ZZB-WA-MSG', tipo='INCOMING', estudiante=self.est_b,
        )
        SandboxCanalSesion.objects.create(telefono=_TEL_B, modo='nat')
        EventoIA.objects.create(
            trace_id=uuid.uuid4(),
            tipo=EventoIA.TIPO_IA_AGENT_TRIGGERED,
            estudiante=self.est_b,
            cliente=self.org_b,
            curso=self.curso_b,
            input_preview='ZZB-NAT-IN',
            output_preview='ZZB-NAT-OUT',
        )
        user_b = User.objects.create_user('iso_b', email='iso-b@test.com', password='pass1234')
        PortalUsuario.objects.create(user=user_b, organizacion=self.org_b, rol='admin')
        self.params_b = {
            'curso_id': self.curso_b.pk,
            'modulo_id': self.mod_b.pk,
            'seccion_id': self.sec_b.pk,
            'paso_id': self.paso_b.pk,
            'estudiante_id': self.est_b.pk,
            'campana_id': self.campana_b.pk,
            'pqrs_id': self.pqrs_b.pk,
            'ficha_id': self.ficha_b.pk,
            'formulario_id': 999000001,
            'item_id': self.biblio_b.pk,
            'run_id': 'ZZB-RUN',
            'tarea_id': self.tarea_b.pk,
            'uidb64': urlsafe_base64_encode(force_bytes(user_b.pk)),
            'token': default_token_generator.make_token(user_b),
        }
        self.users = {}
        for rol in ('admin', 'profesor', 'viewer'):
            user = User.objects.create_user(f'iso_{rol}', password='pass1234')
            PortalUsuario.objects.create(user=user, organizacion=self.org_a, rol=rol)
            self.users[rol] = user

    def _entrar(self, rol):
        http = Client()
        pu = PortalUsuario.objects.get(user=self.users[rol])
        session = http.session
        session[PORTAL_SESSION_KEY] = pu.pk
        session.save()
        return http

    def test_rutas_de_a_no_muestran_marcadores_de_b(self):
        faltan = []
        fugas = []
        for entry in _rutas(get_resolver('portal.urls').url_patterns):
            patron = str(entry.pattern)
            nombres = _PARAM.findall(patron)
            desconocidos = [n for n in nombres if n not in self.params_b]
            if desconocidos:
                faltan.append(f'{entry.name}: {", ".join(desconocidos)}')
                continue
            if not entry.name:
                continue
            kwargs = {n: self.params_b[n] for n in nombres}
            url = reverse(entry.name, kwargs=kwargs)
            for rol in ('admin', 'profesor', 'viewer'):
                http = self._entrar(rol)
                for metodo in ('get', 'post'):
                    resp = getattr(http, metodo)(url)
                    if resp.status_code in (403, 404):
                        continue
                    cuerpo = _texto(resp)
                    if _MARCA in cuerpo:
                        fugas.append(f'{url} {metodo} {rol} {resp.status_code}')
        self.assertFalse(faltan, 'PARAMS_B sin entrada: ' + '; '.join(faltan))
        self.assertFalse(fugas, 'filtra datos de B: ' + '; '.join(fugas[:30]))

    def test_retencion_agente_no_manda_marcadores_de_b_al_llm(self):
        prompts = []

        def _fake_llm(pregunta, ctx):
            prompts.append(f'{pregunta} {ctx}')
            return 'ok-iso'

        http = self._entrar('admin')
        with patch('portal.agente_retencion._llamar_openai', side_effect=_fake_llm):
            resp = http.post(
                '/portal/retencion/agente/',
                data='{"pregunta":"quien abandona"}',
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(prompts)
        self.assertNotIn(_MARCA, prompts[0])
        self.assertNotIn(_MARCA, resp.content.decode('utf-8', errors='replace'))

    def test_aula_profesor_a_no_ve_curso_de_b(self):
        http = self._entrar('profesor')
        for path in (
            f'/aprende/profesor/curso/{self.curso_b.pk}/',
            f'/aprende/profesor/modulo/{self.mod_b.pk}/',
            f'/aprende/profesor/tarea/{self.tarea_b.pk}/entregas/',
        ):
            resp = http.get(path)
            self.assertIn(resp.status_code, (403, 404), path)
            self.assertNotIn(_MARCA, _texto(resp))

    def test_aula_estudiante_a_no_accede_a_modulo_ni_tarea_de_b(self):
        http = Client()
        session = http.session
        session[APRENDE_EST_SESSION_KEY] = self.est_a.pk
        session.save()
        for path in (
            f'/aprende/estudiante/modulo/{self.mod_b.pk}/',
            f'/aprende/estudiante/tarea/{self.tarea_b.pk}/',
            f'/aprende/estudiante/curso/{self.curso_b.pk}/',
        ):
            resp = http.get(path)
            if resp.status_code in (403, 404):
                self.assertNotIn(_MARCA, _texto(resp))
                continue
            self.assertNotEqual(resp.status_code, 200, path)
            self.assertNotIn(_MARCA, _texto(resp))

    def test_lxp_sin_clave_y_con_clave_de_a_no_devuelve_b(self):
        http = Client()
        sin_clave = http.get(f'/api/estudiante/{_TEL_B}/')
        self.assertIn(sin_clave.status_code, (401, 403, 503))
        self.assertNotIn(_MARCA, _texto(sin_clave))
        con_clave = http.get(
            f'/api/estudiante/{_TEL_B}/',
            HTTP_X_API_KEY='iso-key-a',
        )
        cuerpo = _texto(con_clave)
        self.assertNotIn(_MARCA, cuerpo)
        if con_clave.status_code == 200:
            self.assertNotIn('ZZB-NOMBRE-001', cuerpo)

    def test_verificacion_publica_enmascara_documento(self):
        http = Client()
        with patch('core.certificado_service.asegurar_pdf_certificado', return_value=False):
            resp = http.get('/verificar-certificado/eki-ISO-B-0001/')
        cuerpo = _texto(resp)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(_TEL_B, cuerpo)
        self.assertNotIn(_CEDULA_B, cuerpo)
        self.assertIn('****0001', cuerpo)
