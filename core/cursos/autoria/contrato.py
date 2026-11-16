"""Contrato de autoría — bloque 4 / constructor.

1. Un Continuemos entrega un bloque (uno o más mensajes del mismo bloque).
2. Un módulo simple puede tener un único bloque.
3. Publicar crea una versión inmutable; editar después es borrador.
4. La cohorte viva queda fijada a la versión de su inscripción; publicar no la mueve.
5. Course Engine solo produce borradores; nunca publica solo.
6. El Builder legado no gana funciones nuevas; se conserva para rollback.

Con EKI_CURSO_VERSIONES apagado este contrato no cambia la entrega actual
(módulos con publicado_wa y el ensamblado en vivo).
"""

CONTINUEMOS_ENTREGA_UN_BLOQUE = True
PUBLICAR_CREA_VERSION_INMUTABLE = True
COHORTE_FIJA_A_VERSION_DE_INSCRIPCION = True
COURSE_ENGINE_SOLO_BORRADOR = True
