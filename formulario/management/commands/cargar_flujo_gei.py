"""Carga el flujo GEI estándar de 7 pasos para un curso/módulo dado.

Uso:
    python manage.py cargar_flujo_gei <curso_id> <modulo_id>
    python manage.py cargar_flujo_gei <curso_id> <modulo_id> --cliente_id <ID>
    python manage.py cargar_flujo_gei <curso_id> <modulo_id> --reset

- Si `--cliente_id` se pasa, el TipoFormulario queda asociado a ese cliente
  (gana frente al global si ambos existen — ver `formulario/hooks.py`).
- Sin `--cliente_id`, queda como TipoFormulario "global" (cliente=None) que
  aplica a cualquier estudiante cuyo cliente no tenga uno específico.
- `--reset` borra `FlujoPregunta` existente del formulario y recrea los 7 pasos.

Los 7 pasos coinciden con `formulario.models.CAMPOS_GEI_7`. El parser LLM se
activa en los pasos numéricos clave (área, fertilizante, energía, producción).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


PASOS_GEI = [
    {
        "orden": 1,
        "campo_destino": "nombre_finca",
        "pregunta_texto": (
            "¡Hola! Para ayudarle a calcular su huella de carbono y emisiones, "
            "le voy a hacer 7 preguntas cortas sobre su finca. ¿Cómo se llama "
            "su finca o cómo le dice usted al lote donde produce?"
        ),
        "tipo_dato": "text",
        "rango_min": None,
        "rango_max": None,
        "unidad_parseo": "",
        "es_opcional": False,
        "usar_llm_parseo": False,
        "texto_reintento": (
            "No le entendí. Cuénteme nomás el nombre de la finca o lote, "
            "puede ser corto. Si no tiene nombre, escriba 'sin nombre'."
        ),
    },
    {
        "orden": 2,
        "campo_destino": "area_ha",
        "pregunta_texto": (
            "¿Cuántas hectáreas tiene la finca o el lote donde está sembrando? "
            "Si me dice en cuadras o fanegadas también le entiendo (1 fanegada ≈ 0.64 ha)."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 10000.0,
        "unidad_parseo": "ha",
        "es_opcional": False,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Disculpe, no logré sacar el número. Mándeme solo la cantidad, "
            "por ejemplo: 2.5 ha, 5 hectáreas, o 3 fanegadas."
        ),
    },
    {
        "orden": 3,
        "campo_destino": "num_plantas",
        "pregunta_texto": (
            "Aproximadamente, ¿cuántas plantas tiene sembradas en total? "
            "No tiene que ser exacto, una cifra cercana basta."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 1_000_000.0,
        "unidad_parseo": "plantas",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Mándeme solo el número aproximado de plantas (ej. 3000). "
            "Si no lo sabe, escriba OMITIR y seguimos."
        ),
    },
    {
        "orden": 4,
        "campo_destino": "fertilizante_kg",
        "pregunta_texto": (
            "¿Cuántos kilos de fertilizante usa al año en esa finca? "
            "Si lo mide en bultos, también me sirve (un bulto suele ser 50 kg)."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 100_000.0,
        "unidad_parseo": "kg",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Cuénteme solo la cantidad al año, por ejemplo: 200 kg, 4 bultos, "
            "10 sacos. Si no usa fertilizante, escriba 0. Si no sabe, escriba OMITIR."
        ),
    },
    {
        "orden": 5,
        "campo_destino": "concentracion_n_pct",
        "pregunta_texto": (
            "¿Sabe el porcentaje de Nitrógeno (N) del fertilizante? "
            "Sale en el bulto, normalmente como '15-15-15' o '46-0-0'. "
            "Mándeme solo el primer número, o escriba OMITIR si no lo sabe."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 100.0,
        "unidad_parseo": "%",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Mándeme solo un número entre 0 y 100 (porcentaje de N en el fertilizante), "
            "o escriba OMITIR si no lo sabe."
        ),
    },
    {
        "orden": 6,
        "campo_destino": "produccion_kg",
        "pregunta_texto": (
            "¿Aproximadamente cuántos kilos produjo el año pasado en esta finca? "
            "Si lo mide en arrobas (1 arroba ≈ 12.5 kg), bultos o cargas, también me sirve."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 10_000_000.0,
        "unidad_parseo": "kg",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Cuénteme solo la cantidad producida en el último año. Ej: 1500 kg, "
            "120 arrobas, 30 bultos. Si no la recuerda, escriba OMITIR."
        ),
    },
    {
        "orden": 7,
        "campo_destino": "energia_kwh",
        "pregunta_texto": (
            "Última pregunta: ¿más o menos cuántos kWh de energía eléctrica gasta al mes "
            "en la finca? Lo encuentra en el recibo. Si no usa luz en el lote, escriba 0."
        ),
        "tipo_dato": "float",
        "rango_min": 0.0,
        "rango_max": 1_000_000.0,
        "unidad_parseo": "kWh",
        "es_opcional": True,
        "usar_llm_parseo": True,
        "texto_reintento": (
            "Mándeme solo la cantidad, ej: 80 kWh, 100 kilovatios, "
            "o 0 si no usa energía. Si no sabe, escriba OMITIR."
        ),
    },
]


class Command(BaseCommand):
    help = "Crea/actualiza el TipoFormulario GEI con sus 7 pasos para un (curso, módulo). Opcional por cliente."

    def add_arguments(self, parser):
        parser.add_argument("curso_id", type=int, help="ID del curso")
        parser.add_argument(
            "modulo_id",
            type=int,
            help="ID del módulo disparador (al completar este módulo, se inicia el formulario)",
        )
        parser.add_argument(
            "--cliente_id",
            type=int,
            default=None,
            help="ID de Cliente. Si se omite, el formulario queda global (cliente=None).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra los pasos existentes del formulario y recrea los 7 pasos GEI.",
        )

    def handle(self, *args, **opts):
        try:
            from formulario.models import FlujoPregunta, TipoFormulario
        except Exception as exc:
            raise CommandError(f"No se pudo importar formulario.models: {exc}")

        nombres_tabla = set(connection.introspection.table_names())
        if "formulario_tipoformulario" not in nombres_tabla:
            raise CommandError(
                "La tabla 'formulario_tipoformulario' no existe. "
                "Ejecuta primero: python manage.py migrate formulario"
            )

        try:
            from core.models import Cliente, Curso, Modulo
        except Exception as exc:
            raise CommandError(f"No se pudo importar core.models: {exc}")

        curso_id = int(opts["curso_id"])
        modulo_id = int(opts["modulo_id"])
        cliente_id = opts.get("cliente_id")
        reset = bool(opts.get("reset"))

        curso = Curso.objects.filter(id=curso_id).first()
        if not curso:
            raise CommandError(f"No existe Curso id={curso_id}")
        modulo = Modulo.objects.filter(id=modulo_id, curso_id=curso.id).first()
        if not modulo:
            raise CommandError(
                f"No existe Modulo id={modulo_id} para Curso id={curso_id}"
            )
        cliente = None
        if cliente_id is not None:
            cliente = Cliente.objects.filter(id=int(cliente_id)).first()
            if not cliente:
                raise CommandError(f"No existe Cliente id={cliente_id}")

        scope = (
            f"curso={curso.id} modulo={modulo.id} "
            f"cliente={cliente.id if cliente else 'GLOBAL'}"
        )

        with transaction.atomic():
            tf, creado = TipoFormulario.objects.get_or_create(
                curso=curso,
                modulo=modulo,
                cliente=cliente,
                defaults={
                    "nombre": (
                        f"Ficha GEI — {curso.nombre} — Módulo {modulo.titulo}"
                        if cliente is None
                        else f"Ficha GEI — {curso.nombre} — Módulo {modulo.titulo} — {cliente.nombre}"
                    ),
                    "descripcion": "Recolección de los 7 datos clave para huella de carbono / GEI.",
                    "activo": True,
                },
            )
            if creado:
                self.stdout.write(self.style.SUCCESS(f"[+] TipoFormulario creado | {scope} | id={tf.id}"))
            else:
                self.stdout.write(f"[=] TipoFormulario existente | {scope} | id={tf.id}")

            if reset:
                borrados = FlujoPregunta.objects.filter(formulario=tf).count()
                FlujoPregunta.objects.filter(formulario=tf).delete()
                self.stdout.write(self.style.WARNING(f"[reset] eliminados {borrados} pasos previos"))

            existentes = {fp.orden: fp for fp in FlujoPregunta.objects.filter(formulario=tf)}
            for paso in PASOS_GEI:
                fp = existentes.get(paso["orden"])
                if fp:
                    actualizado = False
                    for k, v in paso.items():
                        if k == "orden":
                            continue
                        if getattr(fp, k) != v:
                            setattr(fp, k, v)
                            actualizado = True
                    if actualizado:
                        fp.save()
                        self.stdout.write(f"  [~] paso {paso['orden']} actualizado ({paso['campo_destino']})")
                    else:
                        self.stdout.write(f"  [=] paso {paso['orden']} sin cambios ({paso['campo_destino']})")
                else:
                    FlujoPregunta.objects.create(formulario=tf, **paso)
                    self.stdout.write(self.style.SUCCESS(
                        f"  [+] paso {paso['orden']} creado ({paso['campo_destino']})"
                    ))

        total = FlujoPregunta.objects.filter(formulario=tf).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nListo. TipoFormulario id={tf.id} ahora tiene {total} pasos."
        ))
        if total != len(PASOS_GEI):
            self.stdout.write(self.style.WARNING(
                f"⚠ Esperaban {len(PASOS_GEI)} pasos, hay {total}. Usa --reset si querés reescribir."
            ))
