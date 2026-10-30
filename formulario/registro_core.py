"""Registra en core lo que antes core importaba de esta app. Fase H3."""
from core.puentes import registrar

from formulario.agent import manejar_mensaje_formulario as _manejar_mensaje_formulario
registrar('manejar_mensaje_formulario', _manejar_mensaje_formulario)
from formulario.flow_gei import MARCA_FLOW as _MARCA_FLOW
registrar('MARCA_FLOW', _MARCA_FLOW)
from formulario.gei_flujos import BLOQUES_GEI as _BLOQUES_GEI
registrar('BLOQUES_GEI', _BLOQUES_GEI)
from formulario.hooks import intentar_iniciar_formulario_al_completar_modulo as _intentar_iniciar_formulario_al_completar_modulo
registrar('intentar_iniciar_formulario_al_completar_modulo', _intentar_iniciar_formulario_al_completar_modulo)
from formulario.models import CAMPOS_GEI_7 as _CAMPOS_GEI_7
registrar('CAMPOS_GEI_7', _CAMPOS_GEI_7)
from formulario.models import FichaGEI as _FichaGEI
registrar('FichaGEI', _FichaGEI)
from formulario.models import FlujoPregunta as _FlujoPregunta
registrar('FlujoPregunta', _FlujoPregunta)
from formulario.models import SesionFormulario as _SesionFormulario
registrar('SesionFormulario', _SesionFormulario)
from formulario.models import TipoFormulario as _TipoFormulario
registrar('TipoFormulario', _TipoFormulario)
from formulario.routing import debe_usar_agente_formulario as _debe_usar_agente_formulario
registrar('debe_usar_agente_formulario', _debe_usar_agente_formulario)
