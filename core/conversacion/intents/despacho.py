"""Qué módulo responde cada intent de get_response_for_intent.

get_response_for_intent busca aquí después del preámbulo B2B. Cada handler
recibe (intent, nombre_usuario, kwargs) y siempre devuelve el texto.
"""
from core.conversacion.intents import ayuda, cambiar_nombre, confirmar_cambio_nombre, continuar_leccion, iniciar_examen, inscribir_curso, mi_progreso_cursos, numero_invalido, opcion_1, opcion_2, opcion_3, opcion_numerica, progreso, saludo, tareas, ver_cursos, ver_ranking

INTENTS = {
    'ayuda': ayuda.responder,
    'cambiar_nombre': cambiar_nombre.responder,
    'confirmar_cambio_nombre': confirmar_cambio_nombre.responder,
    'continuar_leccion': continuar_leccion.responder,
    'iniciar_examen': iniciar_examen.responder,
    'inscribir_curso': inscribir_curso.responder,
    'mi_progreso_cursos': mi_progreso_cursos.responder,
    'numero_invalido': numero_invalido.responder,
    'opcion_1': opcion_1.responder,
    'opcion_2': opcion_2.responder,
    'opcion_3': opcion_3.responder,
    'opcion_numerica': opcion_numerica.responder,
    'progreso': progreso.responder,
    'saludo': saludo.responder,
    'tareas': tareas.responder,
    'ver_cursos': ver_cursos.responder,
    'ver_ranking': ver_ranking.responder,
}
