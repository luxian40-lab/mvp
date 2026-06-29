from __future__ import annotations

import unicodedata

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import SolicitudSoporte

KEYWORDS_MENU = {"menu", "menú", "inicio"}
KEYWORDS_CORRECCION = {
    "corregir datos",
    "corregir",
    "modificar datos",
    "modificar",
    "cambiar datos",
    "editar datos",
    "actualizar datos",
}

CAMPOS_CORREGIBLES = {
    "1": ("nombre", "nombre completo"),
    "2": ("municipio", "municipio"),
    "3": ("cedula", "numero de cedula"),
}


def normalizar_texto(texto: str) -> str:
    texto = (texto or "").strip().lower()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(texto.split())


def es_keyword_menu(texto_norm: str) -> bool:
    return texto_norm in {"menu", "inicio"}


def es_keyword_correccion(texto_norm: str) -> bool:
    return any(k in texto_norm for k in KEYWORDS_CORRECCION)


def construir_menu_principal_texto(estudiante) -> str:
    from .flujo_whatsapp_b2b import es_estudiante_b2b, texto_ayuda_comandos

    if es_estudiante_b2b(estudiante):
        return texto_ayuda_comandos(estudiante)

    nombre = (getattr(estudiante, "nombre", "") or "estudiante").split()[0]
    return (
        f"Hola {nombre}. Este es su menu principal:\n\n"
        "📚 Continuar mi curso -> escriba *listo*\n"
        "✏️ Corregir mis datos -> escriba *corregir datos*\n"
        "🆘 Hablar con soporte -> escriba *ayuda*"
    )


def estudiante_en_flujo_correccion(estudiante) -> bool:
    ctx = estudiante.contexto_temporal or {}
    return ctx.get("tipo") == "correccion_datos"


def iniciar_flujo_correccion(estudiante) -> str:
    ctx = estudiante.contexto_temporal or {}
    ctx.update({"tipo": "correccion_datos", "estado": "esperando_opcion", "campo": ""})
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=["contexto_temporal"])
    return (
        "✏️ *Correccion de datos*\n\n"
        "Que quiere corregir?\n"
        "1️⃣ Nombre\n"
        "2️⃣ Municipio\n"
        "3️⃣ Numero de cedula\n\n"
        "Escriba el numero de la opcion."
    )


def _limpiar_flujo_correccion(estudiante) -> None:
    ctx = estudiante.contexto_temporal or {}
    if ctx.get("tipo") == "correccion_datos":
        estudiante.contexto_temporal = None
        estudiante.save(update_fields=["contexto_temporal"])


def _registrar_autocorreccion(estudiante, campo: str, valor_anterior: str, valor_nuevo: str) -> None:
    SolicitudSoporte.objects.create(
        estudiante=estudiante,
        mensaje_original=f"[AUTOCORRECCION] Campo '{campo}': '{valor_anterior}' -> '{valor_nuevo}'",
        keyword_usada="autocorreccion",
        asunto=f"Autocorreccion de {campo}",
        categoria="acceso",
        estado="en_atencion",
        prioridad="baja",
        resuelto_por_agente=True,
        atendido_por="Bot WhatsApp",
        fecha_atencion=timezone.now(),
        notas_internas="Cambio aplicado automaticamente por el estudiante via WhatsApp.",
    )


def _notificar_equipo_autocorreccion(estudiante, campo: str, valor_anterior: str, valor_nuevo: str) -> None:
    try:
        asunto = f"Autocorreccion estudiante: {estudiante.nombre}"
        cuerpo = (
            "Se aplico una autocorreccion de datos desde WhatsApp.\n\n"
            f"Estudiante: {estudiante.nombre}\n"
            f"Telefono: {estudiante.telefono}\n"
            f"Campo: {campo}\n"
            f"Anterior: {valor_anterior}\n"
            f"Nuevo: {valor_nuevo}\n"
        )
        send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@eki.com.co"),
            recipient_list=[getattr(settings, "EMAIL_SOPORTE", "comunidad.educativa@eki.com.co")],
            fail_silently=True,
        )
    except Exception:
        # Best effort: no bloquear el flujo principal si falla email
        pass


def procesar_flujo_correccion(estudiante, mensaje: str) -> str:
    ctx = estudiante.contexto_temporal or {}
    estado = ctx.get("estado", "")
    msg = (mensaje or "").strip()
    msg_norm = normalizar_texto(msg)

    if msg_norm in {"cancelar", "salir"}:
        _limpiar_flujo_correccion(estudiante)
        return "Listo. Se cancelo la correccion. Escriba *listo* para retomar su curso."

    if estado == "esperando_opcion":
        opcion = msg
        if opcion not in CAMPOS_CORREGIBLES:
            return "Por favor escriba 1, 2 o 3 para elegir que corregir."
        campo, etiqueta = CAMPOS_CORREGIBLES[opcion]
        ctx.update({"tipo": "correccion_datos", "estado": "esperando_valor", "campo": campo})
        estudiante.contexto_temporal = ctx
        estudiante.save(update_fields=["contexto_temporal"])
        actual = getattr(estudiante, campo, "") or "No registrado"
        return (
            f"📝 Su {etiqueta} actual es: *{actual}*\n"
            f"Escriba su {etiqueta} como debe quedar:"
        )

    if estado == "esperando_valor":
        campo = ctx.get("campo")
        if campo not in {"nombre", "municipio", "cedula"}:
            _limpiar_flujo_correccion(estudiante)
            return "No pude continuar la correccion. Escriba *corregir datos* para empezar de nuevo."

        valor_nuevo = msg.strip()
        if len(valor_nuevo) < 3:
            return "Ese dato parece muy corto. Por favor escribalo completo."

        if campo == "cedula":
            valor_nuevo = "".join(ch for ch in valor_nuevo if ch.isdigit())
            if len(valor_nuevo) < 6:
                return "La cedula no parece valida. Envie solo numeros, sin puntos."

        valor_anterior = getattr(estudiante, campo, "") or ""
        setattr(estudiante, campo, valor_nuevo)
        try:
            estudiante.save(update_fields=[campo])
        except Exception:
            return (
                "No pude guardar ese dato. Si esta corrigiendo cedula, verifique que no este "
                "registrada en otro usuario. Intente de nuevo o escriba *ayuda*."
            )

        _registrar_autocorreccion(estudiante, campo, valor_anterior, valor_nuevo)
        _notificar_equipo_autocorreccion(estudiante, campo, valor_anterior, valor_nuevo)
        _limpiar_flujo_correccion(estudiante)

        nombre_uso = (estudiante.nombre or "estudiante").split()[0]
        return (
            f"✅ Listo, {nombre_uso}.\n"
            "Guardamos el cambio y notificamos al equipo de eki para confirmarlo.\n"
            "Tu curso sigue disponible. Escribe *listo* para retomarlo cuando quieras. 🌱"
        )

    _limpiar_flujo_correccion(estudiante)
    return "No pude continuar la correccion. Escriba *corregir datos* para iniciar."
