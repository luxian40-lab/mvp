# Entrada de asesoría — charla, ficha y derivación

29 de octubre de 2026. Flag `EKI_ASESORIA_ENTRADA`, apagado. Con él apagado, asesoría sigue en «¿Qué quiere mejorar hoy?» y el cupo no cambia.

La persona siente una conversación. La IA recibe lo que ella dijo. El prompt de los agentes no se toca.

## Charla

De usted. Una burbuja, una pregunta. Si en la respuesta ya vino el dato siguiente, no se vuelve a preguntar. El lugar del registro no se usa ni se menciona.

1. Saludo con el nombre del registro y cómo está. «Hola, María. ¿Cómo está?» Sin nombre usable, «Hola. ¿Cómo está?» y, si hace falta, «¿Cómo le digo?». Cada entrada a asesoría vuelve a preguntar cómo está.
2. Contexto, con una herramienta por dato. Guarda el texto y salta el que ya quedó. «¿De dónde es?» y «¿A qué se dedica?». «De Armero, cultivo café» llena los dos. Quién es sale del nombre, no de una suposición.
3. Con eso: «Cultivo café, en Armero. ¿Qué duda tiene, o qué le gustaría hacer?»
4. Esa frase se deriva como hoy. El agente la contesta. Ahí sí cuenta una de las 60.

*seguir* en el contexto salta a la duda. *menu* y *agentes* salen igual. La vez siguiente, con la ficha llena, después de cómo está retoma lo que ella contó y pasa a la duda.

La línea de solo curso no entra.

## Cupo y contexto de la IA

`registrar_pregunta_asesor` sigue llamándose solo cuando el agente respondió. Saludo, lugar y dedica no lo llaman ni llaman al modelo.

Con el flag prendido, el bloque que ya leen la derivación y los agentes lleva el nombre, cómo está, el lugar que ella dijo y a qué se dedica. Municipio, departamento y región del registro no entran a ese bloque. Con el flag apagado, el bloque sigue como hoy, región incluida.

El goteo de las tres preguntas sueltas no sale con el flag prendido: la ficha se completa en esta charla.

## Modularidad y escalabilidad

No entra a `_procesar_twilio_webhook_cuerpo`, `resolver_ruta_sandbox` ni `get_response_for_intent`. La charla vive en `core/lineas/principal/entrada_asesoria.py`, fuera del ciclo. `asesores.py` solo envía con el sender que ya existe. La respuesta se atiende en el mismo gancho que la ficha, antes del resolver.

Migración solo de columnas nuevas (`entrada`, `lugar`, `como_esta`, `trato`). Una fila por teléfono. Sin índice nuevo y sin segunda llamada al modelo. El freno de complejidad no sube. Los contratos de las dos líneas siguen verdes.
