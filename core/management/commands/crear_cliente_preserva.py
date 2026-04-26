"""Crea o reinicia el entorno de pruebas aislado del cliente Preserva.

Uso:
    python manage.py crear_cliente_preserva           # idempotente, crea/actualiza
    python manage.py crear_cliente_preserva --reset   # borra y recrea desde cero

El command crea:
  - Cliente "Preserva (Test)" con NIT 900000001-0.
  - Curso "[TEST] Balance GEI — Preserva" con tiene_formulario_gei=True y 6 módulos.
  - PreguntaModulo en el módulo 3 (3 preguntas opción múltiple).
  - Curso.preguntas_ejemplo_ia con 5 preguntas IA.
  - TipoFormulario específico Preserva (cliente=Preserva, curso=test, módulo=módulo 4),
    copiando los 7 pasos GEI.
  - 3 estudiantes test (cédulas 1000000001-3, teléfonos 573000000001-3) inscritos en
    el curso vía ProgresoEstudiante.

Los datos test conviven con producción pero quedan filtrables por cliente_id en
admin y panel GEI. Los teléfonos 573000000001-3 no existen en operación real.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    PreguntaModulo,
    ProgresoEstudiante,
)
from formulario.models import FlujoPregunta, TipoFormulario


PRESERVA_CLIENTE = {
    "nombre": "Preserva (Test)",
    "nit": "900000001-0",
    "contacto_principal": "Test Admin",
    "email": "test@preserva.co",
    "telefono": "573000000099",
    "activo": True,
    "notas_internas": "Entorno de pruebas aislado. Generado por crear_cliente_preserva.",
}


CURSO_PRESERVA = {
    "nombre": "[TEST] Balance GEI — Preserva",
    "emoji": "🌿",
    "descripcion": (
        "Aprenda a calcular y entender la huella de carbono de su finca. "
        "Curso introductorio-aplicado para productores agropecuarios colombianos. "
        "Incluye ejercicio de cálculo con sus propios datos. "
        "Otorga certificado de participación."
    ),
    "duracion_semanas": 3,
    "orden": 100,  # último para que no aparezca antes que cursos reales
    "activo": True,
    "tiene_formulario_gei": True,
}


PREGUNTAS_IA_CURSO = [
    "¿Cuál es la principal fuente de emisiones de GEI en su finca y qué podría hacer para reducirla?",
    "Si tuviera que elegir UNA acción para reducir la huella de carbono de su finca este año, ¿cuál sería y por qué?",
    "¿Cómo podría usar el resultado de su balance GEI para negociar un mejor precio por su producto?",
    "Explique con sus palabras qué diferencia hay entre una emisión y una remoción de GEI.",
    "¿Por qué conservar el bosque natural en su finca puede tener valor económico hoy en día?",
]


MODULOS_GEI = [
    {
        "numero": 1,
        "titulo": "El clima está cambiando — y su finca lo siente",
        "descripcion": "Introducción a los GEI y por qué importan al productor colombiano.",
        "contenido": (
            "🌦️ *Módulo 1 — El clima está cambiando*\n\n"
            "¿Ha notado que las lluvias ya no caen igual que antes? ¿Que el verano dura más? "
            "Usted no está equivocado. El clima está cambiando, y la agricultura es uno de los "
            "sectores más afectados.\n\n"
            "*¿Qué son los gases de efecto invernadero (GEI)?*\n"
            "Son gases que se acumulan en la atmósfera y atrapan el calor del sol. Los principales son:\n"
            "🔴 CO₂ — dióxido de carbono (quema de combustibles)\n"
            "🟡 CH₄ — metano (ganado, residuos orgánicos)\n"
            "🟠 N₂O — óxido nitroso (fertilizantes)\n\n"
            "*¿Y la agricultura qué tiene que ver?*\n"
            "En Colombia, el sector agropecuario genera cerca del 30% de las emisiones de GEI. "
            "Pero también puede ser parte de la solución: los árboles y bosques en su finca *capturan* CO₂.\n\n"
            "*¿Por qué le importa esto a los mercados?*\n"
            "Hoy los compradores internacionales — de café, cacao, aguacate, palma — están exigiendo "
            "que los productores demuestren que producen de forma sostenible. Conocer la huella de "
            "carbono de su finca abre puertas a mejores precios y nuevos mercados. 🌍\n\n"
            "Escriba *listo* cuando termine de leer."
        ),
        "examen_obligatorio": False,
    },
    {
        "numero": 2,
        "titulo": "¿Qué es el balance de GEI de su finca?",
        "descripcion": "Concepto de balance, emisiones, remociones y huella de carbono.",
        "contenido": (
            "⚖️ *Módulo 2 — El balance de su finca*\n\n"
            "Imagínese una balanza. De un lado están las *emisiones* — lo que su finca le manda a "
            "la atmósfera. Del otro lado están las *remociones* — lo que sus árboles y bosques "
            "capturan. El balance GEI es esa diferencia.\n\n"
            "*Emisiones:* lo que sale de su finca\n"
            "El uso de fertilizantes, la quema de gasolina, el consumo de luz eléctrica y el manejo "
            "de residuos orgánicos generan GEI.\n\n"
            "*Remociones:* lo que entra (captura)\n"
            "Los árboles de sombra, los sistemas agroforestales y las áreas de bosque natural capturan "
            "CO₂ de la atmósfera. Eso se descuenta de sus emisiones. 🌳\n\n"
            "*¿Qué es la huella de carbono?*\n"
            "Es el resultado del balance expresado en toneladas de CO₂ equivalente por año (tCO₂e/año). "
            "También se puede expresar por hectárea o por kilo de producto cosechado — eso se llama "
            "*intensidad de emisiones*.\n\n"
            "*Ejemplo sencillo:*\n"
            "Si su finca emite 8 tCO₂e/año y sus árboles capturan 3 tCO₂e/año, su balance neto es "
            "5 tCO₂e/año.\n\n"
            "No se preocupe por los números ahora — en el módulo 5 los calculamos juntos con sus "
            "propios datos.\n\n"
            "Escriba *listo* cuando termine."
        ),
        "examen_obligatorio": False,
    },
    {
        "numero": 3,
        "titulo": "¿De dónde vienen las emisiones en su finca?",
        "descripcion": "Fuentes de emisión y remociones en una finca agropecuaria.",
        "contenido": (
            "🏭 *Módulo 3 — Las fuentes de emisión*\n\n"
            "Ahora le explico de dónde salen los GEI en una finca agropecuaria. Estas son las "
            "principales fuentes:\n\n"
            "*1. Fertilizantes nitrogenados 🌱*\n"
            "La urea, el DAP y los abonos con nitrógeno liberan N₂O al suelo cuando se aplican. "
            "Es la fuente más grande en muchos cultivos.\n\n"
            "*2. Combustibles ⛽*\n"
            "La gasolina o diésel que usa en motobombas, tractores, motosierra o transporte "
            "interno genera CO₂.\n\n"
            "*3. Energía eléctrica 💡*\n"
            "La luz que consume en la finca o el beneficiadero también tiene una huella, porque "
            "la electricidad de la red se genera con combustibles fósiles.\n\n"
            "*4. Residuos orgánicos 🍂*\n"
            "La poda, el estiércol y los residuos de cosecha producen metano (CH₄) si se "
            "almacenan en condiciones húmedas o en lagunas.\n\n"
            "*Y del otro lado — las remociones:*\n"
            "🌳 Árboles de sombra y maderables\n"
            "🌿 Sistemas agroforestales\n"
            "🏞️ Áreas de bosque natural en conservación\n\n"
            "*Dato importante:* conservar aunque sea media hectárea de bosque puede compensar "
            "una parte significativa de sus emisiones.\n\n"
            "Escriba *listo* cuando termine. En el siguiente módulo vemos qué datos necesitamos "
            "recoger de su finca."
        ),
        "examen_obligatorio": True,
        "puntaje_minimo_aprobacion": 60,
        "preguntas": [
            {
                "pregunta": "¿Cuál de estos genera más GEI en una finca cafetera?",
                "opcion_a": "Los árboles de sombra",
                "opcion_b": "Los fertilizantes nitrogenados",
                "opcion_c": "El agua de lluvia",
                "opcion_d": "Las cercas vivas",
                "respuesta_correcta": "B",
                "explicacion": (
                    "Los fertilizantes nitrogenados liberan N₂O al suelo al aplicarse, "
                    "siendo la principal fuente de GEI en la mayoría de cultivos."
                ),
            },
            {
                "pregunta": "¿Qué significa que los árboles hacen 'remociones'?",
                "opcion_a": "Que producen más oxígeno",
                "opcion_b": "Que capturan CO₂ de la atmósfera",
                "opcion_c": "Que eliminan plagas",
                "opcion_d": "Que reducen la lluvia",
                "respuesta_correcta": "B",
                "explicacion": "Las remociones son captura neta de CO₂ por la biomasa.",
            },
            {
                "pregunta": "La gasolina que usa en la motobomba genera principalmente:",
                "opcion_a": "N₂O",
                "opcion_b": "CH₄",
                "opcion_c": "CO₂",
                "opcion_d": "Ninguno",
                "respuesta_correcta": "C",
                "explicacion": "La quema de combustibles fósiles libera CO₂.",
            },
        ],
    },
    {
        "numero": 4,
        "titulo": "¿Qué datos necesito y cómo los recojo?",
        "descripcion": "Los 6 datos básicos que necesitamos del productor.",
        "contenido": (
            "📋 *Módulo 4 — Los datos de su finca*\n\n"
            "Para calcular el balance GEI de su finca necesitamos 6 datos básicos. No se preocupe, "
            "son cosas que usted ya sabe o puede averiguar fácilmente.\n\n"
            "*Los 6 datos que necesitamos:*\n\n"
            "*1. Fertilizante nitrogenado* 🌱\n"
            "¿Qué fertilizante usa? ¿Cuántos kilos por planta? ¿Cuántas veces al año?\n"
            'Ejemplo: "Uso urea 46%, 200 gramos por planta, 3 veces al año, tengo 1.000 matas."\n\n'
            "*2. Combustible* ⛽\n"
            "¿Usa gasolina o diésel? ¿Cuánto gasta al mes?\n"
            "Si no sabe los litros, díganos cuánto plata gasta y el precio del galón.\n\n"
            "*3. Energía eléctrica* 💡\n"
            "¿Cuánto paga de luz al mes? ¿O cuántos kWh consume según la factura?\n\n"
            "*4. Residuos orgánicos* 🍂\n"
            "¿Qué hace con la poda? ¿La entierra, hace compostaje, la deja en el suelo?\n\n"
            "*5. Producción anual* ☕\n"
            "¿Cuántos kilos cosechó el año pasado en total?\n\n"
            "*6. Bosque en conservación* 🌳\n"
            "¿Tiene áreas de bosque natural que no cultiva? ¿Cuántas hectáreas?\n\n"
            "*Errores comunes que debemos evitar:*\n"
            "❌ Confundir el área total de la finca con el área productiva\n"
            "❌ Olvidar contar los fertilizantes orgánicos (también cuentan)\n"
            "❌ No saber la concentración de nitrógeno del fertilizante — busque el empaque\n\n"
            "En el siguiente módulo le voy a pedir estos datos para hacer su cálculo personal. "
            "Vaya buscándolos.\n\n"
            "Escriba *listo* cuando esté listo. Después le haré unas preguntas sobre sus datos. 🙌"
        ),
        "examen_obligatorio": False,
        "es_modulo_disparador": True,
    },
    {
        "numero": 5,
        "titulo": "Calculemos la huella de carbono de su finca",
        "descripcion": "Factores de emisión y cálculo personal.",
        "contenido": (
            "🧮 *Módulo 5 — Su cálculo personal*\n\n"
            "¡Este es el módulo más importante! Vamos a usar los datos que ya recopiló para estimar "
            "la huella de carbono de su finca.\n\n"
            "Ya tenemos sus datos guardados. Ahora le mostramos cómo se usan:\n\n"
            "*¿Cómo se calcula?*\n"
            "Cada actividad tiene un *factor de emisión* — un número que convierte sus datos en "
            "CO₂ equivalente:\n\n"
            "🌱 Fertilizante: kg N × 0.01 × 44/28 × 298 → kg CO₂e/año\n"
            "⛽ Combustible: galones × 10.15 → kg CO₂e/año (gasolina)\n"
            "💡 Energía: kWh × 0.126 → kg CO₂e/año (red Colombia)\n"
            "🍂 Residuos: ton × factor según manejo\n"
            "🌳 Bosque: ha × 3.67 → tCO₂e capturadas/año (aprox.)\n\n"
            "*No necesita hacer las cuentas* — el sistema las hace por usted con los datos que nos dio.\n\n"
            "*¿Qué nos dice el resultado?*\n"
            "El sistema le entrega:\n"
            "📊 Emisiones totales en tCO₂e/año\n"
            "📊 Emisiones por fuente (cuál pesa más)\n"
            "📊 Remociones de sus árboles o bosque\n"
            "📊 Balance neto\n"
            "📊 Intensidad: kg CO₂e por kg de producto\n\n"
            "*¿Cómo interpretar su resultado?*\n"
            "Un productor promedio de café en Colombia emite entre 1.5 y 4 kg CO₂e por kg de café. "
            "Si su finca está por debajo de ese rango, ¡va muy bien! Si está por encima, le mostramos "
            "dónde mejorar.\n\n"
            "Escriba *listo* para continuar al último módulo."
        ),
        "examen_obligatorio": False,
    },
    {
        "numero": 6,
        "titulo": "¿Para qué me sirve este resultado?",
        "descripcion": "Aplicaciones de mercado: créditos verdes, primas, certificación.",
        "contenido": (
            "💰 *Módulo 6 — Lo que su huella le puede dar*\n\n"
            "Conocer la huella de carbono de su finca no es solo un ejercicio académico. Es información "
            "que tiene valor real en el mercado de hoy.\n\n"
            "*¿Qué puede hacer con este resultado?*\n\n"
            "*1. Identificar dónde mejorar 🎯*\n"
            "Si la mayor parte de sus emisiones vienen de los fertilizantes, puede revisar dosis y "
            "frecuencia. Pequeños ajustes reducen costos y emisiones al mismo tiempo.\n\n"
            "*2. Acceder a créditos verdes 🏦*\n"
            "Bancolombia, BancoAgrario y otras entidades tienen líneas de crédito con tasas "
            "preferenciales para productores que demuestran prácticas sostenibles.\n\n"
            "*3. Primas de sostenibilidad ☕*\n"
            "Compradores de café, cacao y otros productos pagan entre 10 y 30 USD extra por saco a "
            "productores que pueden certificar su huella de carbono o prácticas ambientales.\n\n"
            "*4. Pagos por servicios ambientales 🌿*\n"
            "Si tiene bosque natural en conservación, puede acceder a programas como el Fondo "
            "Colombia Sostenible o Carbono Neutro que pagan por mantener ese bosque.\n\n"
            "*5. Diferenciación comercial 🏅*\n"
            "Cada vez más compradores en Europa y Norteamérica exigen trazabilidad ambiental. "
            "Su balance GEI es el primer paso para acceder a esos mercados.\n\n"
            "*Próximos pasos:*\n"
            "✅ Guarde su resultado — lo puede pedir al equipo de eki\n"
            "✅ Compare su resultado año a año para ver su progreso\n"
            "✅ Comparta esta información con su organización o cooperativa\n\n"
            "🎓 ¡Felicitaciones! Completó el curso *Balance de Gases de Efecto Invernadero* de eki.\n\n"
            "Escriba *listo* para recibir su certificado."
        ),
        "examen_obligatorio": False,
    },
]


ESTUDIANTES_TEST = [
    {"nombre": "Carlos Ríos Test", "telefono": "573000000001", "cedula": "1000000001"},
    {"nombre": "Luz Castaño Test", "telefono": "573000000002", "cedula": "1000000002"},
    {"nombre": "Pedro Usme Test", "telefono": "573000000003", "cedula": "1000000003"},
]


class Command(BaseCommand):
    help = (
        "Crea o reinicia el entorno de pruebas aislado del cliente Preserva "
        "(cliente, curso GEI, formulario, 3 estudiantes test)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra el entorno Preserva (cliente, curso, fichas, sesiones, estudiantes test) y lo recrea.",
        )

    def handle(self, *args, **opts):
        reset = bool(opts.get("reset"))

        if reset:
            self.stdout.write(self.style.WARNING("⚠️  --reset: borrando entorno Preserva existente..."))
            self._reset()

        with transaction.atomic():
            cliente = self._upsert_cliente()
            curso = self._upsert_curso(cliente)
            modulos_por_numero = self._upsert_modulos(curso)
            modulo_disparador = modulos_por_numero[4]
            self._upsert_preguntas_modulo3(modulos_por_numero[3])
            tipo_form = self._upsert_tipo_formulario(cliente, curso, modulo_disparador)
            self._copiar_pasos_gei(tipo_form)
            estudiantes = self._upsert_estudiantes(cliente)
            self._inscribir_estudiantes(curso, estudiantes)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("✅ Entorno Preserva listo"))
        self.stdout.write(f"   Cliente:        {cliente.nombre} (id={cliente.id})")
        self.stdout.write(f"   Curso:          {curso.nombre} (id={curso.id})")
        self.stdout.write(f"   Módulos:        {len(modulos_por_numero)}")
        self.stdout.write(f"   Módulo dispara: #{modulo_disparador.numero} — {modulo_disparador.titulo}")
        self.stdout.write(f"   TipoFormulario: id={tipo_form.id} (cliente={tipo_form.cliente_id})")
        self.stdout.write(f"   Estudiantes:    {len(estudiantes)}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "⚠️  Para probar: complete el módulo 4 de cualquier estudiante test "
            "(cédulas 1000000001-3, teléfonos 573000000001-3) y el formulario GEI se disparará."
        ))
        self.stdout.write(self.style.SUCCESS("=" * 60))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reset(self):
        cliente = Cliente.objects.filter(nombre=PRESERVA_CLIENTE["nombre"]).first()
        if not cliente:
            self.stdout.write("   (no existía cliente Preserva, nada para borrar)")
            return
        # Sesiones, fichas, progreso, estudiantes test, tipo formulario, curso, cliente
        from formulario.models import FichaGEI, SesionFormulario
        SesionFormulario.objects.filter(estudiante__cliente=cliente).delete()
        FichaGEI.objects.filter(cliente=cliente).delete()
        TipoFormulario.objects.filter(cliente=cliente).delete()
        ProgresoEstudiante.objects.filter(estudiante__cliente=cliente).delete()
        Estudiante.objects.filter(cliente=cliente).delete()
        Curso.objects.filter(cliente=cliente).delete()
        cliente.delete()
        self.stdout.write("   ✓ Entorno Preserva eliminado.")

    def _upsert_cliente(self) -> Cliente:
        cliente, created = Cliente.objects.get_or_create(
            nombre=PRESERVA_CLIENTE["nombre"],
            defaults={k: v for k, v in PRESERVA_CLIENTE.items() if k != "nombre"},
        )
        if not created:
            for k, v in PRESERVA_CLIENTE.items():
                if k != "nombre":
                    setattr(cliente, k, v)
            cliente.save()
        self.stdout.write(f"   {'+' if created else '~'} Cliente {cliente.nombre} (id={cliente.id})")
        return cliente

    def _upsert_curso(self, cliente: Cliente) -> Curso:
        curso, created = Curso.objects.get_or_create(
            nombre=CURSO_PRESERVA["nombre"],
            cliente=cliente,
            defaults={k: v for k, v in CURSO_PRESERVA.items() if k != "nombre"},
        )
        if not created:
            for k, v in CURSO_PRESERVA.items():
                if k != "nombre":
                    setattr(curso, k, v)
        curso.preguntas_ejemplo_ia = "\n".join(PREGUNTAS_IA_CURSO)
        curso.cliente = cliente
        curso.save()
        self.stdout.write(f"   {'+' if created else '~'} Curso {curso.nombre} (id={curso.id}, gei={curso.tiene_formulario_gei})")
        return curso

    def _upsert_modulos(self, curso: Curso) -> dict[int, Modulo]:
        modulos = {}
        for m_data in MODULOS_GEI:
            defaults = {
                "titulo": m_data["titulo"],
                "descripcion": m_data["descripcion"],
                "contenido": m_data["contenido"],
                "examen_obligatorio": m_data.get("examen_obligatorio", False),
                "puntaje_minimo_aprobacion": m_data.get("puntaje_minimo_aprobacion", 70),
            }
            modulo, created = Modulo.objects.get_or_create(
                curso=curso,
                numero=m_data["numero"],
                defaults=defaults,
            )
            if not created:
                for k, v in defaults.items():
                    setattr(modulo, k, v)
                modulo.save()
            modulos[m_data["numero"]] = modulo
            self.stdout.write(f"   {'+' if created else '~'} Módulo {modulo.numero}: {modulo.titulo}")
        return modulos

    def _upsert_preguntas_modulo3(self, modulo3: Modulo):
        preguntas = next((m["preguntas"] for m in MODULOS_GEI if m["numero"] == 3), [])
        for p in preguntas:
            PreguntaModulo.objects.get_or_create(
                modulo=modulo3,
                pregunta=p["pregunta"],
                defaults={
                    "opcion_a": p["opcion_a"],
                    "opcion_b": p["opcion_b"],
                    "opcion_c": p.get("opcion_c") or "",
                    "opcion_d": p.get("opcion_d") or "",
                    "respuesta_correcta": p["respuesta_correcta"],
                    "explicacion": p.get("explicacion", ""),
                },
            )
        self.stdout.write(f"   ~ Preguntas módulo 3: {len(preguntas)}")

    def _upsert_tipo_formulario(self, cliente: Cliente, curso: Curso, modulo: Modulo) -> TipoFormulario:
        tf, created = TipoFormulario.objects.get_or_create(
            nombre="Balance GEI — Preserva",
            cliente=cliente,
            defaults={
                "descripcion": "Recolección GEI específica para productores Preserva (test).",
                "curso": curso,
                "modulo": modulo,
                "activo": True,
            },
        )
        if not created:
            tf.curso = curso
            tf.modulo = modulo
            tf.activo = True
            tf.save()
        self.stdout.write(f"   {'+' if created else '~'} TipoFormulario id={tf.id} cliente={tf.cliente_id}")
        return tf

    def _copiar_pasos_gei(self, tf: TipoFormulario):
        """Copia los 7 pasos del primer TipoFormulario activo (semilla) si no los tiene."""
        if tf.flujo_pasos.exists():
            self.stdout.write(f"   ~ TipoFormulario id={tf.id} ya tiene {tf.flujo_pasos.count()} pasos.")
            return
        seed = (
            TipoFormulario.objects.filter(activo=True)
            .exclude(id=tf.id)
            .filter(flujo_pasos__isnull=False)
            .order_by("id")
            .first()
        )
        if not seed:
            self.stdout.write(self.style.WARNING(
                "   ⚠ No se encontró TipoFormulario semilla; ejecute primero "
                "'python manage.py cargar_flujo_gei <curso_id> <modulo_id>'."
            ))
            return
        pasos_copiados = 0
        for p in seed.flujo_pasos.all().order_by("orden"):
            FlujoPregunta.objects.create(
                formulario=tf,
                orden=p.orden,
                campo_destino=p.campo_destino,
                pregunta_texto=p.pregunta_texto,
                tipo_dato=p.tipo_dato,
                rango_min=p.rango_min,
                rango_max=p.rango_max,
                unidad_parseo=p.unidad_parseo,
                opciones_choice=p.opciones_choice,
                usar_llm_parseo=p.usar_llm_parseo,
                es_opcional=p.es_opcional,
                texto_reintento=p.texto_reintento,
            )
            pasos_copiados += 1
        self.stdout.write(f"   + Pasos GEI copiados desde TF id={seed.id}: {pasos_copiados}")

    def _upsert_estudiantes(self, cliente: Cliente) -> list[Estudiante]:
        estudiantes = []
        for data in ESTUDIANTES_TEST:
            est, created = Estudiante.objects.get_or_create(
                cedula=data["cedula"],
                defaults={
                    "nombre": data["nombre"],
                    "telefono": data["telefono"],
                    "cliente": cliente,
                    "estado_chat": "ACTIVO",
                    "acepto_terminos": True,
                    "estado_onboarding": "completado",
                    "activo": True,
                },
            )
            if not created:
                est.nombre = data["nombre"]
                est.telefono = data["telefono"]
                est.cliente = cliente
                est.estado_chat = "ACTIVO"
                est.acepto_terminos = True
                est.activo = True
                est.save()
            estudiantes.append(est)
            self.stdout.write(f"   {'+' if created else '~'} Estudiante {est.nombre} (cédula={est.cedula})")
        return estudiantes

    def _inscribir_estudiantes(self, curso: Curso, estudiantes: list[Estudiante]):
        for est in estudiantes:
            modulo_inicial = curso.modulos.order_by("numero").first()
            ProgresoEstudiante.objects.get_or_create(
                estudiante=est,
                curso=curso,
                defaults={
                    "modulo_actual": modulo_inicial,
                    "completado": False,
                },
            )
        self.stdout.write(f"   ~ Inscripciones (ProgresoEstudiante): {len(estudiantes)}")
