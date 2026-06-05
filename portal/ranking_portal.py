"""Ranking de mejores estudiantes para el dashboard del portal."""


def ranking_portal(org, curso_id=None, limite=15):
    from core.gamificacion import PerfilGamificacion
    from core.gamificacion_modo import (
        MODO_CALIFICACION,
        MODO_PUNTOS,
        formatear_nota,
        gamificacion_activa,
        get_modo_gamificacion,
        modo_usa_calificacion,
        ranking_calificaciones_cliente,
    )

    modo = get_modo_gamificacion(org)
    if not gamificacion_activa(org):
        return {
            'activa': False,
            'modo': modo,
            'modo_label': '',
            'es_calificacion': False,
            'columna_valor': '',
            'ranking': [],
        }

    modo_labels = {
        MODO_PUNTOS: 'Puntos',
        MODO_CALIFICACION: 'Calificación 1–5',
    }
    ranking = []
    columna_valor = 'Puntos'

    if modo == MODO_CALIFICACION:
        columna_valor = 'Promedio (1–5)'
        for fila in ranking_calificaciones_cliente(org, curso_id=curso_id, limite=limite):
            ranking.append({
                'posicion': fila['posicion'],
                'estudiante_id': fila['estudiante_id'],
                'nombre': fila['nombre'],
                'valor': formatear_nota(fila['promedio']),
                'detalle': f"{fila['cantidad']} evaluación(es)",
            })
    elif modo == MODO_PUNTOS:
        perfiles = (
            PerfilGamificacion.objects.filter(estudiante__cliente=org, estudiante__activo=True)
            .select_related('estudiante')
            .order_by('-puntos_totales', 'estudiante__nombre')[:limite]
        )
        for i, perfil in enumerate(perfiles, start=1):
            ranking.append({
                'posicion': i,
                'estudiante_id': perfil.estudiante_id,
                'nombre': perfil.estudiante.nombre,
                'valor': str(perfil.puntos_totales),
                'detalle': f"Nivel {perfil.nivel}",
            })

    return {
        'activa': True,
        'modo': modo,
        'modo_label': modo_labels.get(modo, modo),
        'es_calificacion': modo_usa_calificacion(org),
        'columna_valor': columna_valor,
        'ranking': ranking,
    }
