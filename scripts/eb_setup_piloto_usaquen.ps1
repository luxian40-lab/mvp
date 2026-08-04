# Corre en EB: crea piloto Usaquén + opcional simulación de pin (sin campaña Twilio).
param(
    [string]$Telefono = '3026480629',
    [switch]$SimularUbicacion
)

$ErrorActionPreference = 'Stop'
$digits = ($Telefono -replace '\D', '')
if ($digits.Length -eq 10 -and $digits.StartsWith('3')) { $digits = "57$digits" }
$simFlag = if ($SimularUbicacion) { 'True' } else { 'False' }

$py = @"
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()
from django.utils import timezone
from core.empleabilidad_prueba import configurar_cliente_empleabilidad, preparar_estudiante_prueba, simular_ubicacion_whatsapp
from core.models import AliadoEmpleabilidad, Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante

LAT, LNG, CODIGO = 4.7171843, -74.0312394, 'EKI-USQ-01'
tel = '$digits'
simular = $simFlag
print('tel=', tel)

cliente, created_c = Cliente.objects.get_or_create(
    nombre='eki piloto empleabilidad Usaquén',
    defaults=dict(
        nit='900000PILOTO', contacto_principal='Piloto eki',
        email='piloto.empleabilidad@eki.technology', telefono=tel, activo=True,
        portal_productos='cursos,empleabilidad',
        empleabilidad_exploracion_activa=True, empleabilidad_radio_metros=2000,
    ),
)
print('cliente', cliente.id, 'created', created_c, configurar_cliente_empleabilidad(cliente, radio_metros=2000))

curso, cc = Curso.objects.get_or_create(
    cliente=cliente, nombre='Piloto empleabilidad — prueba 1 módulo',
    defaults=dict(descripcion='Curso mínimo radar empleabilidad.', activo=True, orden=1, usar_agentes_ia=False),
)
mod, mc = Modulo.objects.get_or_create(
    curso=curso, numero=1,
    defaults=dict(
        titulo='Módulo prueba — exploración territorial',
        descripcion='Un solo módulo de prueba.',
        contenido='Módulo de prueba. Envía ubicación por WhatsApp y valida con el código interno EKI-USQ-01.',
    ),
)
print('curso', curso.id, 'mod', mod.id, 'curso_created', cc, 'mod_created', mc)

aliado, _ = AliadoEmpleabilidad.objects.update_or_create(
    cliente=cliente, codigo_secreto=CODIGO,
    defaults=dict(
        nombre_empresa='Punto demo Usaquén (Av. 9 con 140)',
        latitud=LAT, longitud=LNG, vacantes_activas=True, cupos_disponibles=5, prioridad=5,
        indicacion_sector='esquina Av. 9 con Calle 140, Belmira / Usaquén',
        vigencia_desde=timezone.localdate(),
    ),
)
print('aliado', aliado.id, aliado.nombre_empresa, aliado.latitud, aliado.longitud)

est = Estudiante.objects.filter(telefono=tel).first()
if est:
    est.cliente = cliente
    est.activo = True
    est.nombre = est.nombre or 'Piloto Usaquén'
    est.municipio = est.municipio or 'Bogotá'
    est.departamento = est.departamento or 'Bogotá, D.C.'
    est.estado_chat = 'ACTIVO'
    est.estado_onboarding = 'completado'
    est.save()
    print('estudiante reusado', est.id)
else:
    est = Estudiante.objects.create(
        cliente=cliente, nombre='Piloto Usaquén', telefono=tel,
        municipio='Bogotá', departamento='Bogotá, D.C.', activo=True,
        estado_chat='ACTIVO', estado_onboarding='completado',
    )
    print('estudiante creado', est.id)
preparar_estudiante_prueba(est)
ProgresoEstudiante.objects.get_or_create(estudiante=est, curso=curso, defaults={'modulo_actual': mod})
print('OK piloto. Codigo', CODIGO)
print('Sin campaña en frio. Envia PIN de ubicacion al WhatsApp educativo de eki.')
if simular:
    print('--- sim pin ---')
    print(simular_ubicacion_whatsapp(est, LAT, LNG))
"@

$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export USE_S3=True
cd /var/app/current && source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
echo $pyB64 | base64 -d > /tmp/setup_piloto_usaquen.py
python /tmp/setup_piloto_usaquen.py
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Piloto Usaquén en eki-prod-final tel=$digits simular=$SimularUbicacion" -ForegroundColor Cyan
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
