# Entrada de asesoría — charla, ficha y derivación

29 de octubre de 2026. Flag `EKI_ASESORIA_ENTRADA`, apagado. Con él apagado, asesoría sigue en «¿Qué quiere mejorar hoy?» y el cupo no cambia.

La persona siente una conversación. La IA recibe lo que ella dijo. El prompt de los agentes no se toca.

## Charla

De usted. Una burbuja, una pregunta. Si en la respuesta ya vino el dato siguiente, no se vuelve a preguntar. El lugar del registro no se usa ni se menciona.

1. Saludo con el nombre del registro y cómo está. «Hola, María. ¿Cómo está?» Sin nombre usable, «Hola. ¿Cómo está?» y, si hace falta, «¿Cómo le digo?». Cada entrada a asesoría vuelve a preguntar cómo está.
2. Una pregunta abierta: «Cuénteme de usted: de dónde es y a qué se dedica.» Si los dos datos vienen en esa respuesta, incluso «en Subachoque», no se vuelven a pedir. Si falta uno, se pregunta solo ese. No se repite lo que ella acaba de escribir.
3. «¿Cuál es el principal reto que tiene el día de hoy?» Si la respuesta ya distingue el problema, se deriva. Si se queda en «sin plata», `gpt-6-luna` pregunta si no se vende o si entra y no cubre. Tope de tres.
4. Esa frase entra al agente con el contexto, sin la tarjeta de presentación. El mini sigue eligiendo al agente. Ahí sí cuenta una de las 60.

*seguir* salta a la pregunta de qué quiere entender. *menu* y *agentes* salen igual. La vez siguiente, con la ficha llena, después de cómo está pasa a esa pregunta, sin volver a pedir el lugar ni a qué se dedica.

La línea de solo curso no entra.

## Cupo y contexto de la IA

`registrar_pregunta_asesor` sigue llamándose solo cuando el agente respondió. Saludo, lugar y dedica no lo llaman ni llaman al modelo.

Con el flag prendido, el bloque que ya leen la derivación y los agentes lleva el nombre, cómo está, el lugar que ella dijo y a qué se dedica. Municipio, departamento y región del registro no entran a ese bloque. Con el flag apagado, el bloque sigue como hoy, región incluida.

El goteo de las tres preguntas sueltas no sale con el flag prendido: la ficha se completa en esta charla.

## Modularidad y escalabilidad

No entra a `_procesar_twilio_webhook_cuerpo`, `resolver_ruta_sandbox` ni `get_response_for_intent`. La charla vive en `core/lineas/principal/entrada_asesoria.py`, fuera del ciclo. `asesores.py` solo envía con el sender que ya existe. La respuesta se atiende en el mismo gancho que la ficha, antes del resolver.

Migración solo de columnas nuevas (`entrada`, `lugar`, `como_esta`, `trato`). Una fila por teléfono. Sin índice nuevo. Luna solo pregunta; quien elige al agente sigue siendo la derivación de siempre. El freno de complejidad no sube. Los contratos de las dos líneas siguen verdes.
