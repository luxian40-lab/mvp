"""Flow de registro de la línea 3.

Una sola ficha para todos los clientes. El cliente no se pregunta:
llega en la frase del QR. El teléfono llega en el mensaje de WhatsApp.
Este módulo solo arma el JSON. No lo publica ni escribe la ficha.
"""
from __future__ import annotations

PANTALLA = 'REGISTRO'
NOMBRE_FLOW = 'eki_registro'


def flow_registro() -> dict:
    return {
        'version': '7.0',
        'screens': [{
            'id': PANTALLA,
            'title': 'Registro',
            'terminal': True,
            'success': True,
            'data': {},
            'layout': {
                'type': 'SingleColumnLayout',
                'children': [{
                    'type': 'Form',
                    'name': 'form',
                    'children': [
                        {
                            'type': 'TextBody',
                            'text': (
                                'Para crear su registro necesitamos su nombre y su cédula. '
                                'El municipio puede dejarlo vacío. Su número de WhatsApp ya lo tenemos.'
                            ),
                        },
                        {
                            'type': 'OptIn',
                            'name': 'habeas',
                            'label': 'Acepto el tratamiento de mis datos para crear mi registro.',
                            'required': True,
                        },
                        {
                            'type': 'TextInput',
                            'name': 'nombre',
                            'label': 'Nombre',
                            'required': True,
                            'input-type': 'text',
                        },
                        {
                            'type': 'TextInput',
                            'name': 'cedula',
                            'label': 'Cédula',
                            'required': True,
                            'input-type': 'text',
                        },
                        {
                            'type': 'TextInput',
                            'name': 'municipio',
                            'label': 'Municipio',
                            'required': False,
                            'input-type': 'text',
                        },
                        {
                            'type': 'Footer',
                            'label': 'Enviar',
                            'on-click-action': {
                                'name': 'complete',
                                'payload': {
                                    'habeas': '${form.habeas}',
                                    'nombre': '${form.nombre}',
                                    'cedula': '${form.cedula}',
                                    'municipio': '${form.municipio}',
                                },
                            },
                        },
                    ],
                }],
            },
        }],
    }
