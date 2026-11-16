"""Contrato de producto — constructor oficial (bloque 5).

Vocabulario (mapeo a modelos vivos):

- Curso → ``Curso``
- Módulo → ``Modulo``
- Bloque de entrega (un Continuemos) → ``SeccionModulo``
- Mensaje → ``PasoModulo``

Reglas:

1. Guardar contenido nunca publica ni envía WhatsApp.
2. Un Continuemos entrega un bloque (uno o más mensajes del mismo bloque).
3. Un módulo simple puede tener un único bloque.
4. El Builder legado no gana funciones nuevas; esta superficie es la oficial nueva.
5. Con ``EKI_CONSTRUCTOR_CURSOS`` apagado las mutaciones no escriben.
"""

CURSO_MODULO_BLOQUE_MENSAJE = True
GUARDAR_NO_PUBLICA = True
CONTINUEMOS_ENTREGA_UN_BLOQUE = True
BUILDER_LEGADO_SIN_FEATURES_NUEVAS = True
