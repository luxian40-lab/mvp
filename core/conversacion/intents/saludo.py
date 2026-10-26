"""Intent `saludo` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    estudiante_id_menu = kwargs.get('estudiante_id')
    if estudiante_id_menu:
        try:
            from core.models import Estudiante as _EstMenu
            from core.selector_curso import asegurar_inscripcion_catalogo_cliente

            _est = _EstMenu.objects.select_related('cliente').get(id=estudiante_id_menu)
            # B2B: sin menú 1-2-3 global; si tiene 2+ cursos activos, menú de elección
            if _est.cliente_id:
                from core.flujo_whatsapp_b2b import (
                    armar_menu_seleccion_cursos,
                    tiene_varios_cursos_activos,
                )

                org = _est.cliente.nombre if _est.cliente else 'tu organización'
                if tiene_varios_cursos_activos(_est):
                    return armar_menu_seleccion_cursos(
                        _est,
                        prefijo=(
                            f"🌱 Hola {nombre_usuario}, bienvenido al programa de *{org}*.\n\n"
                            "Tienes varios cursos activos:"
                        ),
                    )
                prog = asegurar_inscripcion_catalogo_cliente(_est)
                if prog and prog.curso:
                    cur = prog.curso
                    emoji = (cur.emoji or '📚').strip()
                    return (
                        f"🌱 Hola {nombre_usuario}, bienvenido al programa de *{org}*.\n\n"
                        f"{emoji} Tu curso: *{cur.nombre}*\n\n"
                        "Pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]\n"
                        "Si tienes dudas, escribe *ayuda*."
                    )
                return (
                    f"🌱 Hola {nombre_usuario}, bienvenido a *{org}*.\n\n"
                    "Tu organización aún no tiene cursos activos o siguen en preparación.\n"
                    "Escribe *ayuda* si necesitas soporte."
                )
            _ctxm = dict(_est.contexto_temporal or {})
            _ctxm.pop('curso_activo_id', None)
            _est.contexto_temporal = _ctxm or None
            _est.save(update_fields=['contexto_temporal'])
        except Exception:
            pass
    return f"""🌱 Hola {nombre_usuario}, bienvenido a eki

🚜 *Tu plataforma de soluciones educativas*

Aprende y mejora tus conocimientos con nosotros.


*¿Qué deseas hacer?*

1️⃣ Ver mi progreso
2️⃣ Explorar cursos
3️⃣ Ayuda y soporte

📝 Escribe el número (1, 2 o 3)"""
