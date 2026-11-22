"""Pulso semanal Andrés: cohorte septiembre (Alitic, Lhaura vet, Agricapital)."""
from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.html import escape

from core.analitica.nps_cierre import nps_nota_cierre
from core.email_service import get_email_service

COHORTE_NOMBRES = ('Alitic', 'Lhaura vet', 'Agricapital')
DESDE_COHORTE = date(2026, 9, 1)


def destinatarios_desde_setting(valor) -> list[str]:
    if not valor:
        return []
    if isinstance(valor, (list, tuple)):
        partes = valor
    else:
        partes = str(valor).split(',')
    out = []
    for parte in partes:
        email = str(parte).strip()
        if email.count('@') == 1 and ' ' not in email:
            out.append(email)
    return out


def url_novedades() -> str:
    base = (getattr(settings, 'EKI_PUBLIC_BASE_URL', '') or 'https://admin.eki.technology').rstrip('/')
    return f'{base}/admin/novedades-eki/'


def _progreso_cohorte(org_id: int, desde: date):
    from core.models import ProgresoEstudiante

    return ProgresoEstudiante.objects.filter(
        estudiante__cliente_id=org_id,
        fecha_inicio__date__gte=desde,
    ).annotate(n_mods=Count('modulos_completados', distinct=True))


def _fila_org(org, *, desde: date, hace7) -> dict:
    from core.models import WhatsappLog
    from core.certificados.models_certificados import Certificado

    progreso_q = _progreso_cohorte(org.pk, desde)
    inscritos = progreso_q.count()
    finalizados = progreso_q.filter(completado=True).count()
    en_curso = progreso_q.filter(completado=False, n_mods__gt=0).count()
    no_iniciados = progreso_q.filter(completado=False, n_mods=0).count()
    avance_pct = round(finalizados * 100 / inscritos) if inscritos else 0
    certificados = Certificado.objects.filter(
        estudiante__cliente_id=org.pk,
        emitido=True,
        fecha_emision__date__gte=desde,
    ).count()
    activos_wa_7d = (
        WhatsappLog.objects.filter(
            fecha__gte=hace7,
            estudiante__cliente_id=org.pk,
            estudiante__isnull=False,
        )
        .values('estudiante')
        .distinct()
        .count()
    )
    activos_avance_7d = (
        progreso_q.filter(fecha_ultimo_avance__gte=hace7)
        .values('estudiante_id')
        .distinct()
        .count()
    )
    nps = nps_nota_cierre(cliente_id=org.pk, fecha_inicio=desde)
    return {
        'org_id': org.pk,
        'org_nombre': org.nombre,
        'inscritos': inscritos,
        'finalizados': finalizados,
        'en_curso': en_curso,
        'no_iniciados': no_iniciados,
        'avance_pct': avance_pct,
        'certificados': certificados,
        'activos_wa_7d': activos_wa_7d,
        'activos_avance_7d': activos_avance_7d,
        'nps': nps,
    }


def recoger_snapshot(*, desde: date | None = None) -> dict:
    from core.models import Cliente, WhatsappLog

    hoy = timezone.localdate()
    desde = desde or DESDE_COHORTE
    ahora = timezone.now()
    hace7 = ahora - timedelta(days=7)
    orgs = list(
        Cliente.objects.filter(nombre__in=COHORTE_NOMBRES, activo=True).order_by('nombre')
    )
    filas = [_fila_org(org, desde=desde, hace7=hace7) for org in orgs]
    # Orden estable: Alitic, Agricapital, Lhaura vet (por nombre alfabetico ya)
    filas_por_nombre = {f['org_nombre']: f for f in filas}
    orgs_out = [filas_por_nombre[n] for n in COHORTE_NOMBRES if n in filas_por_nombre]

    tot = {
        'orgs': len(orgs_out),
        'inscritos': sum(int(f['inscritos']) for f in orgs_out),
        'finalizados': sum(int(f['finalizados']) for f in orgs_out),
        'en_curso': sum(int(f['en_curso']) for f in orgs_out),
        'no_iniciados': sum(int(f['no_iniciados']) for f in orgs_out),
        'certificados': sum(int(f['certificados']) for f in orgs_out),
        'activos_wa_7d': sum(int(f['activos_wa_7d']) for f in orgs_out),
        'activos_avance_7d': sum(int(f['activos_avance_7d']) for f in orgs_out),
    }
    insc = tot['inscritos']
    tot['avance_pct'] = round(tot['finalizados'] * 100 / insc) if insc else 0

    org_ids = [f['org_id'] for f in orgs_out]
    desde7 = hoy - timedelta(days=6)
    wa_rows = (
        WhatsappLog.objects.filter(
            fecha__date__gte=desde7,
            fecha__date__lte=hoy,
            estudiante__cliente_id__in=org_ids,
        )
        .annotate(dia=TruncDate('fecha'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
        if org_ids
        else []
    )
    wa_map = {r['dia']: int(r['total']) for r in wa_rows}
    wa_serie = []
    for i in range(7):
        d = hoy - timedelta(days=6 - i)
        wa_serie.append({
            'dia': d.isoformat(),
            'label': d.strftime('%d/%m'),
            'total': int(wa_map.get(d, 0)),
        })

    # NPS de la cohorte: notas de los tres clientes desde septiembre.
    nps = {'n': 0, 'nps': None, 'promotores': 0, 'pasivos': 0, 'detractores': 0}
    if org_ids:
        from django.db.models import Q

        from core.models import NotaCierreCurso

        qs = NotaCierreCurso.objects.filter(
            estudiante__activo=True,
            estudiante__cliente_id__in=org_ids,
            fecha__date__gte=desde,
        )
        fila = qs.aggregate(
            n=Count('id'),
            promotores=Count('id', filter=Q(nota__gte=9)),
            pasivos=Count('id', filter=Q(nota__gte=7, nota__lte=8)),
            detractores=Count('id', filter=Q(nota__lte=6)),
        )
        n = int(fila['n'] or 0)
        prom = int(fila['promotores'] or 0)
        det = int(fila['detractores'] or 0)
        nps = {
            'n': n,
            'nps': None if not n else round((prom - det) * 100 / n),
            'promotores': prom,
            'pasivos': int(fila['pasivos'] or 0),
            'detractores': det,
        }

    return {
        'generado': ahora,
        'hoy': hoy,
        'hoy_label': hoy.strftime('%d/%m/%Y'),
        'desde': desde,
        'desde_label': desde.strftime('%d/%m/%Y'),
        'totales': tot,
        'nps': nps,
        'orgs': orgs_out,
        'wa_7d': wa_serie,
        'novedades_url': url_novedades(),
    }


def construir_texto(snap: dict) -> str:
    t = snap['totales']
    nps = snap['nps']
    nps_txt = 'sin notas' if nps.get('nps') is None else str(nps['nps'])
    lineas = [
        f"Pulso cohorte septiembre · {snap['hoy_label']}",
        f"Ventana: {snap['desde_label']} → {snap['hoy_label']}",
        f"Clientes: Alitic, Lhaura vet, Agricapital ({t['orgs']} encontrados)",
        f"Inscripciones: {t['inscritos']}",
        f"Terminaron: {t['finalizados']} ({t['avance_pct']}%)",
        f"En curso: {t['en_curso']}",
        f"Sin iniciar: {t['no_iniciados']}",
        f"Certificados desde sep: {t['certificados']}",
        f"NPS cohorte: {nps_txt} (n={nps.get('n') or 0})",
        f"WhatsApp 7d (personas): {t['activos_wa_7d']}",
        '',
        'Novedades eki: ' + snap.get('novedades_url', url_novedades()),
        '',
        'Inscrito = ProgresoEstudiante con fecha_inicio desde el 1 sep 2026.',
    ]
    for org in snap['orgs']:
        lineas.append(
            f"- {org['org_nombre']}: {org['inscritos']} inscritos, "
            f"{org['avance_pct']}% avance, cert {org['certificados']}"
        )
    return '\n'.join(lineas)


def _pct(parte: int, total: int) -> int:
    if not total:
        return 0
    return max(0, min(100, round(parte * 100 / total)))


def _barra_apilada(org: dict) -> str:
    total = int(org['inscritos']) or 1
    fin = _pct(int(org['finalizados']), total)
    curso = _pct(int(org['en_curso']), total)
    no = max(0, 100 - fin - curso)
    # Si inscritos=0, barra gris
    if int(org['inscritos']) == 0:
        return (
            f"<div style=\"font-size:13px;font-weight:bold;margin:12px 0 4px;\">{escape(org['org_nombre'])}</div>"
            f"<div style=\"font-size:12px;color:#6b5a74;margin-bottom:4px;\">Sin inscripciones desde {escape('01/09/2026')}</div>"
            f"<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\">"
            f"<tr><td style=\"background:#ddd;height:14px;\"></td></tr></table>"
        )
    return (
        f"<div style=\"font-size:13px;font-weight:bold;margin:12px 0 4px;\">{escape(org['org_nombre'])}</div>"
        f"<div style=\"font-size:12px;color:#6b5a74;margin-bottom:4px;\">"
        f"{int(org['inscritos'])} inscritos · {int(org['finalizados'])} terminó · "
        f"{int(org['en_curso'])} en curso · {int(org['no_iniciados'])} sin iniciar · "
        f"avance {int(org['avance_pct'])}% · cert {int(org['certificados'])} · "
        f"WA 7d {int(org['activos_wa_7d'])}</div>"
        f"<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\">"
        f"<tr>"
        f"<td width=\"{fin}%\" style=\"background:#2f7d4a;height:14px;\"></td>"
        f"<td width=\"{curso}%\" style=\"background:#4a7ea8;height:14px;\"></td>"
        f"<td width=\"{no}%\" style=\"background:#c47a2c;height:14px;\"></td>"
        f"</tr></table>"
    )


def _barras_wa(serie: list[dict]) -> str:
    if not serie:
        return ''
    max_t = max(int(p['total']) for p in serie) or 1
    celdas = []
    for p in serie:
        h = max(4, round(80 * int(p['total']) / max_t))
        celdas.append(
            f"<td valign=\"bottom\" align=\"center\" width=\"14%\">"
            f"<div style=\"background:#9A6CAC;width:18px;height:{h}px;margin:0 auto;\"></div>"
            f"<div style=\"margin-top:6px;font-size:11px;color:#6b5a74;\">"
            f"{escape(p['label'])}<br><b style=\"color:#1f1524;\">{int(p['total'])}</b></div>"
            f"</td>"
        )
    return (
        '<table width="100%" cellspacing="0" cellpadding="0">'
        f"<tr>{''.join(celdas)}</tr></table>"
    )


def construir_html(snap: dict) -> str:
    t = snap['totales']
    nps = snap['nps']
    nps_txt = 'sin notas' if nps.get('nps') is None else str(nps['nps'])
    barras = ''.join(_barra_apilada(o) for o in snap['orgs'])
    wa_html = _barras_wa(snap.get('wa_7d') or [])
    novedades = escape(snap.get('novedades_url') or url_novedades())
    return f"""<!DOCTYPE html>
<html lang="es">
<body style="margin:0;padding:0;background:#f4f1f6;font-family:Arial,Helvetica,sans-serif;color:#1f1524;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f1f6;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="background:#ffffff;border:1px solid #e6dcec;">
        <tr>
          <td style="background:#9A6CAC;color:#ffffff;padding:20px 28px;">
            <div style="font-size:13px;letter-spacing:0.04em;">EKI · CORTE SEMANAL</div>
            <div style="font-size:22px;font-weight:bold;margin-top:6px;">Cohorte septiembre · {escape(snap['hoy_label'])}</div>
            <div style="font-size:13px;margin-top:6px;">Alitic · Lhaura vet · Agricapital · desde {escape(snap['desde_label'])}</div>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 28px;background:#fbf7ee;border-bottom:1px solid #e6dcec;font-size:14px;line-height:1.5;">
            Inscripciones con fecha de inicio desde el 1 de septiembre de 2026. Verde = terminó, azul = en curso, naranja = sin iniciar.
          </td>
        </tr>
        <tr>
          <td style="padding:24px 28px 8px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
              <tr>
                <td width="25%"><div style="font-size:28px;font-weight:bold;color:#9A6CAC;">{int(t['inscritos'])}</div><div style="font-size:12px;color:#6b5a74;">inscripciones</div></td>
                <td width="25%"><div style="font-size:28px;font-weight:bold;">{int(t['avance_pct'])}%</div><div style="font-size:12px;color:#6b5a74;">terminaron</div></td>
                <td width="25%"><div style="font-size:28px;font-weight:bold;">{escape(nps_txt)}</div><div style="font-size:12px;color:#6b5a74;">NPS (n={int(nps.get('n') or 0)})</div></td>
                <td width="25%"><div style="font-size:28px;font-weight:bold;">{int(t['certificados'])}</div><div style="font-size:12px;color:#6b5a74;">certificados</div></td>
              </tr>
              <tr>
                <td><div style="font-size:22px;font-weight:bold;padding-top:12px;">{int(t['en_curso'])}</div><div style="font-size:12px;color:#6b5a74;">en curso</div></td>
                <td><div style="font-size:22px;font-weight:bold;padding-top:12px;">{int(t['no_iniciados'])}</div><div style="font-size:12px;color:#6b5a74;">sin iniciar</div></td>
                <td><div style="font-size:22px;font-weight:bold;padding-top:12px;">{int(t['activos_wa_7d'])}</div><div style="font-size:12px;color:#6b5a74;">con WhatsApp 7d</div></td>
                <td><div style="font-size:22px;font-weight:bold;padding-top:12px;">{int(t['activos_avance_7d'])}</div><div style="font-size:12px;color:#6b5a74;">con avance 7d</div></td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 28px 8px;font-size:16px;font-weight:bold;">Estado por cliente</td>
        </tr>
        <tr>
          <td style="padding:0 28px 24px;">{barras}</td>
        </tr>
        <tr>
          <td style="padding:0 28px 8px;font-size:16px;font-weight:bold;">WhatsApp cohorte · últimos 7 días</td>
        </tr>
        <tr>
          <td style="padding:0 28px 8px;font-size:12px;color:#6b5a74;">Mensajes de estudiantes de Alitic, Lhaura vet y Agricapital.</td>
        </tr>
        <tr>
          <td style="padding:0 28px 24px;">{wa_html}</td>
        </tr>
        <tr>
          <td style="padding:16px 28px;background:#f4eef7;font-size:14px;line-height:1.5;">
            <b>Novedades eki</b> (misma URL siempre; se actualiza cada ~3 semanas):<br>
            <a href="{novedades}" style="color:#9A6CAC;">{novedades}</a>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 28px;background:#f7f4f9;font-size:11px;color:#6b5a74;line-height:1.5;">
            Inscrito = ProgresoEstudiante con fecha_inicio ≥ {escape(snap['desde_label'])}. Avance = terminados / inscritos. NPS = nota 1–10 al cerrar. Fuente: producción eki, {escape(snap['hoy_label'])}.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def enviar_reporte_clientes() -> dict:
    destinos = destinatarios_desde_setting(
        getattr(settings, 'EKI_REPORTE_CLIENTES_EMAIL', []),
    )
    if not destinos:
        return {'enviado': False, 'motivo': 'sin_destinatarios'}
    snap = recoger_snapshot()
    ok = get_email_service().send_email(
        to_emails=destinos,
        subject=f"eki · cohorte septiembre · {snap['hoy_label']}",
        body=construir_texto(snap),
        html_body=construir_html(snap),
    )
    return {
        'enviado': bool(ok),
        'orgs': int(snap['totales'].get('orgs') or 0),
        'destinatarios': len(destinos),
    }
