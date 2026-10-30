"""Registra en core lo que antes core importaba de esta app. Fase H3."""
from core.puentes import registrar

from portal.agente_retencion import responder_agente_retencion as _responder_agente_retencion
registrar('responder_agente_retencion', _responder_agente_retencion)
from portal.branding import contexto_identidad_org as _contexto_identidad_org
registrar('contexto_identidad_org', _contexto_identidad_org)
from portal.capabilities import modulos_portal as _modulos_portal
registrar('modulos_portal', _modulos_portal)
from portal.cobertura_geo import resumen_cobertura_geografica as _resumen_cobertura_geografica
registrar('resumen_cobertura_geografica', _resumen_cobertura_geografica)
from portal.curso_flujo_service import embudo_posicion_hoy_por_curso as _embudo_posicion_hoy_por_curso
registrar('embudo_posicion_hoy_por_curso', _embudo_posicion_hoy_por_curso)
from portal.empleabilidad_metricas import resumen_empleabilidad_portal as _resumen_empleabilidad_portal
registrar('resumen_empleabilidad_portal', _resumen_empleabilidad_portal)
from portal.forms import ClientePortalAdminForm as _ClientePortalAdminForm
registrar('ClientePortalAdminForm', _ClientePortalAdminForm)
from portal.forms import PORTAL_PRODUCTO_CHOICES as _PORTAL_PRODUCTO_CHOICES
registrar('PORTAL_PRODUCTO_CHOICES', _PORTAL_PRODUCTO_CHOICES)
from portal.forms import texto_formato_whatsapp as _texto_formato_whatsapp
registrar('texto_formato_whatsapp', _texto_formato_whatsapp)
from portal.forms_usuarios import CrearUsuarioPortalForm as _CrearUsuarioPortalForm
registrar('CrearUsuarioPortalForm', _CrearUsuarioPortalForm)
from portal.geo_catalogo import UbicacionResuelta as _UbicacionResuelta
registrar('UbicacionResuelta', _UbicacionResuelta)
from portal.geo_catalogo import _divipola_por_clave as __divipola_por_clave
registrar('_divipola_por_clave', __divipola_por_clave)
from portal.geo_catalogo import aplicar_ubicacion_dane as _aplicar_ubicacion_dane
registrar('aplicar_ubicacion_dane', _aplicar_ubicacion_dane)
from portal.geo_catalogo import resolver_ubicacion as _resolver_ubicacion
registrar('resolver_ubicacion', _resolver_ubicacion)
from portal.geo_catalogo import ruta_geojson_municipios as _ruta_geojson_municipios
registrar('ruta_geojson_municipios', _ruta_geojson_municipios)
from portal.models import PortalUsuario as _PortalUsuario
registrar('PortalUsuario', _PortalUsuario)
from portal.nat_service import checklist_preparacion_nat as _checklist_preparacion_nat
registrar('checklist_preparacion_nat', _checklist_preparacion_nat)
from portal.provision import cupos_restantes as _cupos_restantes
registrar('cupos_restantes', _cupos_restantes)
from portal.provision import cupos_totales as _cupos_totales
registrar('cupos_totales', _cupos_totales)
from portal.provision import cupos_usados as _cupos_usados
registrar('cupos_usados', _cupos_usados)
from portal.provision import provisionar_usuario_portal as _provisionar_usuario_portal
registrar('provisionar_usuario_portal', _provisionar_usuario_portal)
from portal.rag_curso_service import crear_documento_curso as _crear_documento_curso
registrar('crear_documento_curso', _crear_documento_curso)
from portal.rag_curso_service import encolar_indexacion_rag_curso as _encolar_indexacion_rag_curso
registrar('encolar_indexacion_rag_curso', _encolar_indexacion_rag_curso)
from portal.retencion_service import analitica_retencion_portal as _analitica_retencion_portal
registrar('analitica_retencion_portal', _analitica_retencion_portal)
