#!/bin/bash
# Curso 35 (Agrosavia — Identificación y Toma de Muestras en Apiarios):
# migra pendientes + carga guía de reto y tipo por módulo. Idempotente; no toca contenido ni pasos.
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME OPENAI_API_KEY; do
  export "$key=$($GC environment -k $key 2>/dev/null)"
done
export USE_S3=True
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
cd /var/app/current
source /var/app/venv/*/bin/activate

echo "--- showmigrations core (últimas)"
python manage.py showmigrations core | tail -n 5
echo "--- migrate"
python manage.py migrate --noinput | tail -n 8

python manage.py shell <<'PY'
from core.models import Curso, Modulo

GUIAS = {
    1: (
        Modulo.TIPO_RETO_DIAGNOSTICO,
        """Tema del checkpoint: reconocer señales de alarma en la colmena ANTES de intervenir.

El reto debe pedir una revisión contable, no una reflexión:
- Revisar entre 5 y 10 colmenas del apiario en una sola jornada.
- Registrar cuántas presentan cada señal: cría salteada o con mal olor, abejas
  temblorosas o que no logran volar, mortalidad frente a la piquera, varroa visible
  sobre abejas adultas, caída fuerte de población.
- Exigir cifras en la respuesta ("de 10 revisadas, X con ...").
- Pedir que señale la colmena más sospechosa y el criterio observable por el que la eligió.
- Evidencia sugerida: foto del cuadro de cría o de la piquera de esa colmena.

Prohibido: pedir opiniones generales, "reflexione sobre la importancia", tratamientos,
dosis o nombres comerciales.""",
    ),
    2: (
        Modulo.TIPO_RETO_APLICACION,
        """Tema del checkpoint: tomar la muestra correcta según la sospecha.

El reto debe pedir ejecutar una toma real:
- Elegir la colmena sospechosa y decir qué va a muestrear (abejas adultas, cría, miel,
  cera o material de piquera) y por qué eso y no otra cosa.
- Cantidad y punto de toma con número (por ejemplo, cerca de 30 abejas adultas tomadas
  de cuadros con cría abierta).
- Nombrar el recipiente y el rótulo completo: apiario, número de colmena, fecha,
  municipio y responsable.
- Reportar cuál de los errores frecuentes evitó: muestrear abejas ya descompuestas,
  mezclar varias colmenas en un mismo frasco, enviar la muestra sin rótulo.
- Evidencia sugerida: foto de la muestra rotulada.

Prohibido: interpretar resultados de laboratorio, dosis o productos comerciales.""",
    ),
    3: (
        Modulo.TIPO_RETO_PLAN,
        """Tema del checkpoint: conservar y enviar la muestra sin arruinarla.

El reto debe pedir la cadena de custodia concreta de SU muestra:
- Cómo la conserva (frío, seco o en alcohol según el tipo de muestra), en qué recipiente
  y a qué temperatura aproximada.
- Cuántas horas o días pasarán hasta el laboratorio y qué hace si el envío se retrasa.
- Qué datos van con la muestra (remisión: apiario, número de colmenas, síntomas
  observados, fecha, contacto).
- Un riesgo real de su ruta (calor, transporte, fin de semana) y su plan B.
- Evidencia sugerida: foto del empaque listo para envío o del formato de remisión.

Exija tiempos y números, no intenciones.""",
    ),
    4: (
        Modulo.TIPO_RETO_SITUACION,
        """Tema del checkpoint: convertir resultados de laboratorio en decisiones de manejo.

El reto debe partir de un resultado hipotético breve (por ejemplo, carga alta de varroa,
o hallazgo de residuo de plaguicida en abejas muertas) y pedir:
- Qué hace en las próximas 48 horas y qué hace en las 2 semanas siguientes, con acciones
  observables (aislar la colmena, reforzar población, cambiar cuadros, repetir muestreo,
  avisar al vecino o a la autoridad sanitaria).
- Qué indicador va a medir para saber si funcionó y cada cuánto (conteo de varroa por
  100 abejas, mortalidad diaria frente a la piquera, avance de cría).
- Qué NO haría y por qué.
- Evidencia sugerida: foto del registro donde anotará ese indicador.

Prohibido: dosis, nombres comerciales o mezclas. Si el manejo requiere un producto,
indique que consulte a la asistencia técnica o al ICA.""",
    ),
}

curso = Curso.objects.get(id=35)
print('CURSO', curso.id, curso.nombre, '| perfil:', repr(curso.perfil_facilitador))
for modulo in curso.modulos.order_by('numero'):
    par = GUIAS.get(modulo.numero)
    if not par:
        print('M%s sin guía definida (se deja igual)' % modulo.numero)
        continue
    tipo, guia = par
    modulo.tipo_reto_ia = tipo
    modulo.reto_guia_ia = guia.strip()
    modulo.save(update_fields=['tipo_reto_ia', 'reto_guia_ia'])
    print('M%s | %s | tipo=%s | guia_len=%s' % (
        modulo.numero, modulo.titulo, modulo.tipo_reto_ia, len(modulo.reto_guia_ia)))
PY
