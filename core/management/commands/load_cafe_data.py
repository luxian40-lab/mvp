from django.core.management.base import BaseCommand
from core.models import Curso, Modulo, PreguntaModulo


class Command(BaseCommand):
    help = 'Carga datos de ejemplo: 2 cursos de café con 6 módulos y preguntas'

    def handle(self, *args, **options):
        # Limpiar datos anteriores
        Curso.objects.all().delete()

        # ==================== CURSO 1: FUNDAMENTOS DEL CAFÉ ====================
        curso1 = Curso.objects.create(
            nombre="☕ Fundamentos del Café",
            descripcion="Curso completo sobre los fundamentos del cultivo y procesamiento del café",
            emoji="☕",
            duracion_semanas=4,
            activo=True
        )

        # Módulo 1
        modulo1_1 = Modulo.objects.create(
            curso=curso1,
            numero=1,
            titulo="Introducción al Café",
            descripcion="Conoce la historia y origen del café",
            contenido="☕ **Historia del Café**\n\nOriginario de Etiopía, el café se ha convertido en la segunda bebida más consumida en el mundo.",
            duracion_dias=3
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_1,
            pregunta="¿De qué país es originario el café?",
            opcion_a="Etiopía",
            opcion_b="Brasil",
            opcion_c="Colombia",
            opcion_d="Vietnam",
            respuesta_correcta="A"
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_1,
            pregunta="¿Cuál es la variedad más consumida?",
            opcion_a="Robusta",
            opcion_b="Arábica",
            opcion_c="Libérica",
            opcion_d="Excelsa",
            respuesta_correcta="B"
        )

        # Módulo 2
        modulo1_2 = Modulo.objects.create(
            curso=curso1,
            numero=2,
            titulo="Siembra y Establecimiento",
            descripcion="Cómo preparar y sembrar correctamente",
            contenido="🌱 **Siembra del Café**\n\nAltitud: 1200-2000 msnm\nTemperatura: 17-23°C",
            duracion_dias=4
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_2,
            pregunta="¿Cuál es la temperatura ideal?",
            opcion_a="10-15°C",
            opcion_b="17-23°C",
            opcion_c="30-35°C",
            opcion_d="40°C+",
            respuesta_correcta="B"
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_2,
            pregunta="¿Cuál es la distancia entre plantas?",
            opcion_a="1m x 1m",
            opcion_b="1.5m x 1.5m",
            opcion_c="2m x 2m",
            opcion_d="3m x 3m",
            respuesta_correcta="B"
        )

        # Módulo 3
        modulo1_3 = Modulo.objects.create(
            curso=curso1,
            numero=3,
            titulo="Cuidados y Mantenimiento",
            descripcion="Mantenimiento diario y control de plagas",
            contenido="🛡️ **Cuidados del Cafetal**\n\nRiego: 2-3 veces por semana\nPlagas: Roya, Broca del café",
            duracion_dias=5
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_3,
            pregunta="¿Con qué frecuencia riego?",
            opcion_a="1 vez/semana",
            opcion_b="2-3 veces/semana",
            opcion_c="Diariamente",
            opcion_d="1 vez/mes",
            respuesta_correcta="B"
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_3,
            pregunta="¿Plaga más común?",
            opcion_a="Roya",
            opcion_b="Mosca blanca",
            opcion_c="Gusano maíz",
            opcion_d="Ácaros",
            respuesta_correcta="A"
        )

        # Módulo 4
        modulo1_4 = Modulo.objects.create(
            curso=curso1,
            numero=4,
            titulo="Cosecha del Café",
            descripcion="Técnicas de cosecha y selección",
            contenido="🌾 **Cosecha**\n\nFruto rojo brillante = listo\nOctubre-Diciembre",
            duracion_dias=3
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_4,
            pregunta="¿Cuándo cosechar?",
            opcion_a="Verde",
            opcion_b="Rojo brillante",
            opcion_c="Marrón oscuro",
            opcion_d="Al caer",
            respuesta_correcta="B"
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_4,
            pregunta="¿Rendimiento/ha?",
            opcion_a="500-700 kg",
            opcion_b="400-500 kg",
            opcion_c="1000-1500 kg",
            opcion_d="100-200 kg",
            respuesta_correcta="B"
        )

        # Módulo 5
        modulo1_5 = Modulo.objects.create(
            curso=curso1,
            numero=5,
            titulo="Procesamiento del Café",
            descripcion="Métodos: fermentación y secado",
            contenido="⚙️ **Procesamiento**\n\nMétodo Húmedo: mejor calidad\nMétodo Seco: menos inversión",
            duracion_dias=4
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_5,
            pregunta="¿Métodos principales?",
            opcion_a="Tostado-molido",
            opcion_b="Húmedo-seco",
            opcion_c="Fermentado-natural",
            opcion_d="Rápido-lento",
            respuesta_correcta="B"
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_5,
            pregunta="¿Tiempo secado método húmedo?",
            opcion_a="3-5 días",
            opcion_b="10-14 días",
            opcion_c="20-30 días",
            opcion_d="2-3 meses",
            respuesta_correcta="B"
        )

        # Módulo 6
        modulo1_6 = Modulo.objects.create(
            curso=curso1,
            numero=6,
            titulo="Comercialización y Mercado",
            descripcion="Venta, precios y oportunidades",
            contenido="💰 **Mercado del Café**\n\nArábica: $1.50-2.50/libra\nCertificaciones: Fair Trade, UTZ",
            duracion_dias=3
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_6,
            pregunta="¿Precio Arábica?",
            opcion_a="$0.50-0.80/libra",
            opcion_b="$1.50-2.50/libra",
            opcion_c="$3.00-4.00/libra",
            opcion_d="$5.00+/libra",
            respuesta_correcta="B"
        )
        PreguntaModulo.objects.create(
            modulo=modulo1_6,
            pregunta="¿Qué mejora el precio?",
            opcion_a="Baja altitud",
            opcion_b="Sin procesar",
            opcion_c="Certificaciones sostenibles",
            opcion_d="Secado rápido",
            respuesta_correcta="C"
        )

        # ==================== CURSO 2: CAFÉ ESPECIALIZADO ====================
        curso2 = Curso.objects.create(
            nombre="🌟 Café Especializado",
            descripcion="Técnicas avanzadas para café de alta calidad",
            emoji="🌟",
            duracion_semanas=6,
            activo=True
        )

        # Módulo 1
        modulo2_1 = Modulo.objects.create(
            curso=curso2,
            numero=1,
            titulo="Fermentación Controlada",
            descripcion="Técnicas de fermentación para mejorar sabor",
            contenido="🧪 **Fermentación Avanzada**\n\nAnaerobia: 24-48h - Aerobia: 12-24h",
            duracion_dias=5
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_1,
            pregunta="¿Temperatura ideal fermentación?",
            opcion_a="10-15°C",
            opcion_b="20-25°C",
            opcion_c="30-35°C",
            opcion_d="40°C+",
            respuesta_correcta="B"
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_1,
            pregunta="¿Fermentación más ácida?",
            opcion_a="Anaerobia",
            opcion_b="Aerobia",
            opcion_c="Mixta",
            opcion_d="Ninguna",
            respuesta_correcta="B"
        )

        # Módulo 2
        modulo2_2 = Modulo.objects.create(
            curso=curso2,
            numero=2,
            titulo="Análisis Sensorial del Café",
            descripcion="Evaluación de calidad (cupping)",
            contenido="👃 **Cupping - Análisis Sensorial**\n\n0-100 puntos\n80+ = Specialty",
            duracion_dias=4
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_2,
            pregunta="¿Puntuación mínima Specialty?",
            opcion_a="75",
            opcion_b="80",
            opcion_c="85",
            opcion_d="90",
            respuesta_correcta="B"
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_2,
            pregunta="¿Aspectos evaluados cupping?",
            opcion_a="3",
            opcion_b="5",
            opcion_c="8",
            opcion_d="10",
            respuesta_correcta="C"
        )

        # Módulo 3
        modulo2_3 = Modulo.objects.create(
            curso=curso2,
            numero=3,
            titulo="Trazabilidad y Sostenibilidad",
            descripcion="Certificaciones y prácticas sostenibles",
            contenido="🌱 **Café Sostenible**\n\nFair Trade, Rainforest, UTZ, Orgánico",
            duracion_dias=5
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_3,
            pregunta="¿Prima Fair Trade?",
            opcion_a="5-10%",
            opcion_b="10-15%",
            opcion_c="20-40%",
            opcion_d="50%+",
            respuesta_correcta="C"
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_3,
            pregunta="¿Ventaja trazabilidad?",
            opcion_a="Reducir costos",
            opcion_b="Vender rápido",
            opcion_c="Garantizar origen-calidad",
            opcion_d="Aumentar producción",
            respuesta_correcta="C"
        )

        # Módulo 4
        modulo2_4 = Modulo.objects.create(
            curso=curso2,
            numero=4,
            titulo="Microclimas y Terroir",
            descripcion="Cómo terreno y clima afectan sabor",
            contenido="🏔️ **Terroir del Café**\n\nAltitud, suelo, temperatura, humedad",
            duracion_dias=4
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_4,
            pregunta="¿Altitud más ácida?",
            opcion_a=">800",
            opcion_b=">1200",
            opcion_c=">1600",
            opcion_d=">2000",
            respuesta_correcta="C"
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_4,
            pregunta="¿pH ideal suelo?",
            opcion_a="4.0-4.5",
            opcion_b="5.5-6.5",
            opcion_c="7.0-7.5",
            opcion_d="8.0-8.5",
            respuesta_correcta="B"
        )

        # Módulo 5
        modulo2_5 = Modulo.objects.create(
            curso=curso2,
            numero=5,
            titulo="Tecnología Agrícola Moderna",
            descripcion="Herramientas tecnológicas para optimizar",
            contenido="🚀 **Tecnología en Café**\n\nDrones, IoT, Apps, GPS",
            duracion_dias=4
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_5,
            pregunta="¿Ahorro riego inteligente?",
            opcion_a="10-15%",
            opcion_b="20-25%",
            opcion_c="30-40%",
            opcion_d="50%+",
            respuesta_correcta="C"
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_5,
            pregunta="¿Ventaja drones?",
            opcion_a="Reducir mano obra",
            opcion_b="Monitorear plagas",
            opcion_c="Aumentar lluvia",
            opcion_d="Cambiar suelo",
            respuesta_correcta="B"
        )

        # Módulo 6
        modulo2_6 = Modulo.objects.create(
            curso=curso2,
            numero=6,
            titulo="Negocios y Exportación",
            descripcion="Modelos negocio y exportación",
            contenido="📊 **Café como Negocio**\n\nMargen Specialty: 50-100%\nDirecto: 200%+",
            duracion_dias=5
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_6,
            pregunta="¿Costo anual mantenimiento?",
            opcion_a="$200-300/ha",
            opcion_b="$500-700/ha",
            opcion_c="$800-1200/ha",
            opcion_d="$2000+/ha",
            respuesta_correcta="C"
        )
        PreguntaModulo.objects.create(
            modulo=modulo2_6,
            pregunta="¿Margen Specialty?",
            opcion_a="10-20%",
            opcion_b="20-30%",
            opcion_c="50-100%",
            opcion_d="5-10%",
            respuesta_correcta="C"
        )

        self.stdout.write(self.style.SUCCESS('✅ DATOS DE CAFÉ CARGADOS EXITOSAMENTE!'))
        self.stdout.write(f'✅ Curso 1: {curso1.nombre} con {curso1.modulos.count()} módulos')
        self.stdout.write(f'✅ Curso 2: {curso2.nombre} con {curso2.modulos.count()} módulos')
        self.stdout.write(f'✅ Total preguntas: {PreguntaModulo.objects.count()}')
