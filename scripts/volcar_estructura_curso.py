# -*- coding: utf-8 -*-
"""Vuelca la estructura de un curso, sin estudiantes ni datos de contacto.

Incluye curso, módulos, secciones, pasos y archivos. Vacía cliente y
enlace_grupo_whatsapp. No incluye Estudiante ni ProgresoEstudiante.
No guarda el archivo en el repositorio: lo escribe en %LOCALAPPDATA%\\eki_backups.

Sin EKI_USE_REMOTE_DB lee el SQLite local.

  $env:PYTHONUTF8='1'
  $env:CURSO_ID='28'
  python scripts/volcar_estructura_curso.py

Para cargar el JSON en un SQLite que no tenga ese id:

  python manage.py loaddata "$env:LOCALAPPDATA\\eki_backups\\curso_28_estructura.json"

Producción: no uses el usuario de la aplicación. Un rol de Postgres con
SELECT solo en core_curso, core_modulo, core_seccionmodulo, core_pasomodulo
y core_archivomodulo, desde una máquina que ya llegue a RDS (esta no llegó:
la conexión expiró). No lo crees desde aquí.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

import django

django.setup()

from django.core import serializers

from core.models import Curso, Modulo, PasoModulo, SeccionModulo
from core.models_extras import ArchivoModulo


def main():
    cid = int(os.environ['CURSO_ID'])
    curso = Curso.objects.get(pk=cid)
    curso.cliente_id = None
    curso.enlace_grupo_whatsapp = ''
    bloques = [
        [curso],
        Modulo.objects.filter(curso_id=cid),
        SeccionModulo.objects.filter(modulo__curso_id=cid),
        PasoModulo.objects.filter(modulo__curso_id=cid),
        ArchivoModulo.objects.filter(modulo__curso_id=cid),
    ]
    payload = []
    for qs in bloques:
        payload.extend(json.loads(serializers.serialize('json', qs)))
    destino = Path(os.environ['LOCALAPPDATA']) / 'eki_backups' / f'curso_{cid}_estructura.json'
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(
        destino,
        'modulos', bloques[1].count(),
        'secciones', bloques[2].count(),
        'pasos', bloques[3].count(),
        'archivos', bloques[4].count(),
    )


if __name__ == '__main__':
    main()
