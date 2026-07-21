"""Vista previa de certificado desde admin (plantilla + estudiante opcional)."""

from __future__ import annotations

from django.http import HttpResponse

from core.certificado_preview import generar_preview_certificado
from core.certificado_presencial_service import info_plantilla_curso
from core.models import Cliente, Curso, Estudiante
from core.models_certificados import PlantillaCertificado


GUIA_MARCADORES_HTML = """
<div style="font-size:13px;line-height:1.55;background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;padding:12px 14px;margin-bottom:1rem;">
<strong>Guía de marcadores (modo imagen)</strong>
<ul style="margin:8px 0 0;padding-left:1.2rem;">
<li><span style="display:inline-block;width:14px;height:14px;background:rgb(128,128,128);vertical-align:middle;border:1px solid #999;"></span>
<strong> Gris RGB (128, 128, 128)</strong> → nombre del estudiante</li>
<li><span style="display:inline-block;width:14px;height:14px;background:rgb(255,0,0);vertical-align:middle;"></span>
<strong> Rojo RGB (255, 0, 0)</strong> → cédula / documento</li>
<li><span style="display:inline-block;width:14px;height:14px;background:rgb(0,0,255);vertical-align:middle;"></span>
<strong> Azul RGB (0, 0, 255)</strong> → código QR de verificación</li>
</ul>
<p style="margin:8px 0 0;color:#78350f;">Pinte cuadrados pequeños (10–30 px) en Photoshop/Canva. Al generar, eki los reemplaza y borra el color.</p>
</div>
"""


def _resolver_plantilla_preview(
    cliente: Cliente,
    curso: Curso,
    plantilla_id: int | None,
    post_data,
) -> PlantillaCertificado | None:
    if plantilla_id:
        pl = PlantillaCertificado.objects.filter(pk=plantilla_id, activa=True).first()
        if pl:
            return pl
    info = info_plantilla_curso(cliente, curso, plantilla_id)
    return info.get('plantilla') if info else None


def guardar_plantilla_imagen_curso(
    cliente: Cliente,
    curso: Curso,
    archivo,
    plantilla_id: int | None = None,
) -> PlantillaCertificado:
    """Sube imagen a S3 (storages) y la asocia al curso/cliente."""
    plantilla = None
    if plantilla_id:
        plantilla = PlantillaCertificado.objects.filter(pk=plantilla_id, activa=True).first()
    if plantilla is None:
        plantilla = PlantillaCertificado.objects.filter(
            curso=curso, cliente=cliente, activa=True,
        ).order_by('-por_defecto', '-id').first()
    if plantilla is None:
        plantilla = PlantillaCertificado(
            nombre=f'Plantilla {curso.nombre}'[:120],
            cliente=cliente,
            curso=curso,
            modo_plantilla='imagen',
            activa=True,
            por_defecto=True,
        )
    plantilla.modo_plantilla = 'imagen'
    plantilla.archivo_plantilla_imagen = archivo
    plantilla.save()
    return plantilla


def respuesta_preview_png(request, cliente: Cliente, curso: Curso) -> HttpResponse:
    plantilla_id_raw = request.POST.get('plantilla_id') or request.GET.get('plantilla_id')
    plantilla_id = int(plantilla_id_raw) if str(plantilla_id_raw or '').isdigit() else None
    plantilla = _resolver_plantilla_preview(cliente, curso, plantilla_id, request.POST)
    if not plantilla:
        return HttpResponse('No hay plantilla. Suba una imagen primero.', status=400)

    est_id_raw = request.POST.get('estudiante_preview') or request.GET.get('estudiante_preview')
    nombre = cedula = org = url = None
    if str(est_id_raw or '').isdigit():
        est = Estudiante.objects.filter(
            pk=int(est_id_raw), cliente=cliente, activo=True,
        ).first()
        if est:
            nombre = est.nombre
            cedula = est.cedula or ''
            org = cliente.nombre
            url = 'https://admin.eki.technology/verificar-certificado/PREVIEW/'

    try:
        buf = generar_preview_certificado(
            plantilla,
            post_data=request.POST,
            files=request.FILES,
            nombre_estudiante=nombre,
            cedula_estudiante=cedula,
            organizacion_nombre=org,
            url_verificacion=url,
        )
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    except Exception as exc:
        return HttpResponse(f'Error al generar vista previa: {exc}', status=500)

    if not buf:
        return HttpResponse('No se pudo generar la imagen.', status=500)
    return HttpResponse(buf.getvalue(), content_type='image/png')
