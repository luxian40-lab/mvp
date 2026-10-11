"""Crea las plantillas de bienvenida como borrador. No llama a Meta."""
from django.core.management.base import BaseCommand

from core.models_campana_meta import PlantillaMeta

PIE = 'eki · Aprender y asesorar en el campo'
BAJA = 'No recibir más'
AVISO_CARRUSEL = (
    'Bloqueada hasta tener WHATSAPP_APP_ID y las fotos del carrusel. '
    'No enviar a Meta. Tarjeta 1: Formación, botón Ver cursos. '
    'Tarjeta 2: Asesoría, botón Preguntar.'
)

_BOTONES = {
    'boton_1_tipo': 'QUICK_REPLY',
    'boton_2_tipo': 'QUICK_REPLY',
    'boton_2_texto': BAJA,
    'boton_1_url': '',
    'boton_1_ejemplo': '',
    'boton_2_url': '',
    'boton_2_ejemplo': '',
    'header_texto': '',
    'header_ejemplo': '',
    'footer': PIE,
    'categoria': 'MARKETING',
    'idioma': 'es',
    'tipo': 'TEXTO',
    'estado': 'BORRADOR',
    'activa': True,
}

PLANTILLAS_TEXTO = (
    {
        'meta_name': 'eki_bienvenida_texto',
        'nombre_interno': 'Bienvenida con organización',
        'cuerpo': (
            'Hola {{1}}, le damos la bienvenida a eki 🌱\n\n'
            '{{2}} le abrió este espacio en WhatsApp para que aprenda y resuelva '
            'dudas del campo sin salir del celular.\n\n'
            'Toque *Empezar* para abrir el menú.'
        ),
        'ejemplos_cuerpo': 'María|Cooperativa Café del Huila',
        'boton_1_texto': 'Empezar',
    },
    {
        'meta_name': 'eki_bienvenida_curso',
        'nombre_interno': 'Bienvenida a un curso',
        'cuerpo': (
            'Hola {{1}}, {{2}} le invita al curso *{{3}}* en eki 🌱\n\n'
            'Lo hace a su ritmo, desde WhatsApp, con mensajes cortos y ejemplos de finca.\n\n'
            'Toque *Seguir* para abrir el menú y empezar.'
        ),
        'ejemplos_cuerpo': 'María|Cooperativa Café del Huila|Finanzas para la finca',
        'boton_1_texto': 'Seguir',
    },
    {
        'meta_name': 'eki_bienvenida_generica',
        'nombre_interno': 'Bienvenida sin organización',
        'cuerpo': (
            'Hola {{1}}, le damos la bienvenida a eki 🌱\n\n'
            'Aquí puede tomar cursos cortos y consultar a asesores sobre su cultivo, '
            'sus cuentas, sus ventas y el uso del celular.\n\n'
            'Toque *Empezar* para ver el menú.'
        ),
        'ejemplos_cuerpo': 'María',
        'boton_1_texto': 'Empezar',
    },
    {
        'meta_name': 'eki_bienvenida_asesoria',
        'nombre_interno': 'Bienvenida a asesoría',
        'cuerpo': (
            'Hola {{1}}, tiene asesores de eki disponibles por WhatsApp 🌱\n\n'
            'Puede preguntarle a un agrónomo, un coach de hábitos, un profesor de IA, '
            'un asesor de ventas o un experto en finanzas, según lo que necesite hoy.\n\n'
            'Toque *Preguntar* y escoja su asesor.'
        ),
        'ejemplos_cuerpo': 'María',
        'boton_1_texto': 'Preguntar',
    },
)

PLANTILLA_CARRUSEL = {
    'meta_name': 'eki_bienvenida_carrusel',
    'nombre_interno': 'Bienvenida carrusel',
    'cuerpo': (
        'Hola {{1}}, esto es lo que puede hacer en eki 🌱 '
        'Deslice y toque la opción que le sirva.'
    ),
    'ejemplos_cuerpo': 'María',
    'tipo': 'CARRUSEL',
    'ultimo_error_mensaje': AVISO_CARRUSEL,
}


def cargar_borradores() -> list[tuple[str, str]]:
    """Crea o actualiza borradores. Una plantilla ya enviada a Meta no se pisa."""
    filas = []
    for definicion in PLANTILLAS_TEXTO:
        filas.append(_guardar({**_BOTONES, **definicion, 'ultimo_error_mensaje': ''}))
    filas.append(_guardar({
        **_BOTONES,
        **PLANTILLA_CARRUSEL,
        'boton_1_tipo': '',
        'boton_1_texto': '',
        'boton_2_tipo': '',
        'boton_2_texto': '',
    }))
    return filas


def _guardar(campos: dict) -> tuple[str, str]:
    nombre = campos['meta_name']
    idioma = campos.get('idioma') or 'es'
    actual = PlantillaMeta.objects.filter(meta_name=nombre, idioma=idioma).first()
    if actual is not None and actual.estado != 'BORRADOR':
        return nombre, 'intacta'
    if actual is None:
        actual = PlantillaMeta(meta_name=nombre, idioma=idioma)
        marca = 'creada'
    else:
        marca = 'actualizada'
    for clave, valor in campos.items():
        if clave in ('meta_name', 'idioma'):
            continue
        setattr(actual, clave, valor)
    actual.full_clean()
    actual.save()
    return nombre, marca


class Command(BaseCommand):
    help = (
        'Carga las plantillas de bienvenida como borrador en Plantillas Meta. '
        'No las envía a aprobación.'
    )

    def handle(self, *args, **options):
        for nombre, marca in cargar_borradores():
            self.stdout.write(f'{nombre} {marca}')
        self.stdout.write(self.style.SUCCESS(
            'Listo. Revise en Admin → Plantillas Meta y use '
            '"Enviar plantilla a Meta para aprobación" solo en las de texto.'
        ))
