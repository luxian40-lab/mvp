# Prompts maestros de los cinco agentes

Fuente: «eki — Prompts maestros de los cinco agentes alineados», versión del 22 de octubre de 2026. Canal: WhatsApp.

Principio rector: no buscamos cinco agentes que contesten preguntas, sino cinco acompañantes que desarrollen capacidades para comprender, razonar, decidir, aplicar y aprender en la realidad de cada persona.

## Qué agente es cada uno

Los nombres del menú no cambian.

| Documento | Agente en eki | Clave | Dónde está |
|---|---|---|---|
| Agrónomo — producir mejor | *Agrónomo* | `nat` y `cafe` | `IDENTIDAD_AGRONOMO_LINEA` (se suma al prompt de Nat dentro de la línea) y `PROMPT_CAFE` |
| Comercial — vender por valor | *Ventas* | `ventas` | `PROMPT_VENTAS` |
| Financiero — decidir mejor sobre los recursos | *Finanzas* | `finanzas` | `PROMPT_FINANZAS` |
| Innovación e IA — eficiencia y diferenciación | *Innovación e IA* | `ia_campo` | `PROMPT_IA_CAMPO` |
| Liderazgo y desarrollo humano | *Coach* | `coach` | `PROMPT_COACH` |

Todo vive en `core/sandbox_agentes.py`.

## Cómo se arma el prompt

1. `BLOQUE_REGISTRO`: trato de usted, español colombiano, normalmente de 30 a 90 palabras, como máximo una pregunta y solo si ayuda a decidir. También lo usa Nat (`core/nati.py`).
2. `INSTRUCCIONES_EKI`: las instrucciones transversales (contexto, método, eficiencia, evaluación, privacidad, límites). Una sola copia para los cinco.
3. El prompt del agente: rol, capacidades, cómo responder, ejemplo contextual, lo que no hace y el resultado buscado.
4. `_CIERRE_REGISTRO`: recuerda el estilo al final.

El Agrónomo de la línea es Nat con `IDENTIDAD_AGRONOMO_LINEA` encima, que ya incluye `INSTRUCCIONES_EKI`.

## Lo que todavía no hace el sistema

- **Caracterización autorizada.** Los prompts dicen que use territorio, actividad, negocio y necesidad cuando el contexto los trae. Hoy solo el Agrónomo recibe un bloque estructurado (`CONTEXTO AGRONÓMICO DEL PRODUCTOR`). Pasar la caracterización a Coach, Ventas, Finanzas e Innovación e IA es un cambio aparte: hay que leerla con el consentimiento de habeas.
- **Registro de aprendizaje o compromiso.** La medición compartida (capacidad, situación, herramienta, decisión, resultado) no se guarda todavía.
- **Derivación con contexto.** Hoy se deriva con *menu*. El agente no transfiere la conversación y el prompt le prohíbe simularlo.
- **Cupo.** El documento habla de unas 60 interacciones al mes. El cupo real depende del plan (`core/planes_linea.py`), por eso el prompt dice «cupo mensual limitado» sin número.

## Prueba de calidad antes de desplegar

Para cada agente, con conversaciones de café, cacao, hortalizas y servicios rurales, comprobar que:

- [ ] aprovecha la caracterización que trae el contexto;
- [ ] no inventa detalles;
- [ ] no hace más de una pregunta por mensaje;
- [ ] da valor sin pedir varias rondas;
- [ ] desarrolla criterio en lugar de recopilar datos;
- [ ] respeta los límites profesionales.

Los tests (`core/tests_agentes_prompts_maestros.py`) solo comprueban que el texto del prompt diga esto. La calidad de las respuestas del modelo se revisa a mano en la línea de pruebas antes del deploy.
