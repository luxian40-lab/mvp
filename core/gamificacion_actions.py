"""
Sistema de Acciones Gamificadas para EKI
Funciones para otorgar puntos por diferentes actividades
"""

import logging
from .gamificacion import PerfilGamificacion, Badge, BadgeEstudiante

logger = logging.getLogger(__name__)


# Configuración de puntos por actividad
# ENFOQUE: PROGRESO EDUCATIVO REAL (no mensajería)
PUNTOS_CONFIG = {
    # Mensajería (mínimo - solo para engagement)
    'mensaje_enviado': 1,  # Reducido: solo interacción básica
    'audio_enviado': 2,    # Reducido: preferencia de comunicación
    
    # CORE: Progreso Académico (alto valor)
    'modulo_iniciado': 10,          # Empezó un módulo
    'modulo_completado': 100,       # ⭐ Completó módulo
    'lectura_completa': 20,         # Leyó todo el contenido
    
    # CORE: Evaluaciones (basado en desempeño)
    'examen_aprobado_60': 80,       # 60-69%
    'examen_aprobado_70': 120,      # 70-79%
    'examen_aprobado_80': 180,      # 80-89%
    'examen_aprobado_90': 250,      # 90-99%
    'examen_perfecto': 400,         # ⭐⭐⭐ 100%
    'examen_reprobado': -20,        # Penalización (motivar a reintentar)
    
    # CORE: Cursos (máximo valor)
    'curso_completado': 500,        # ⭐⭐⭐ Completó curso entero
    'curso_excelencia': 800,        # Curso con promedio 90+
    'primer_curso': 100,
    
    # Rachas de Estudio (consistencia)
    'racha_3_dias': 30,
    'racha_7_dias': 100,
    'racha_30_dias': 500,
    
    # Colaboración
    'ayudar_otro_estudiante': 25,
    'pregunta_respondida': 15,
}


def otorgar_puntos_actividad(estudiante, actividad, puntos_extra=0):
    """
    Otorga puntos por una actividad específica
    
    Args:
        estudiante: Instancia de Estudiante
        actividad: Key de PUNTOS_CONFIG
        puntos_extra: Puntos adicionales (opcional)
    
    Returns:
        dict con info de la transacción
    """
    try:
        # Obtener o crear perfil
        perfil, created = PerfilGamificacion.objects.get_or_create(
            estudiante=estudiante
        )
        
        # Actualizar racha
        racha_actualizada = perfil.actualizar_racha()
        
        # Obtener puntos de la configuración
        puntos = PUNTOS_CONFIG.get(actividad, 0) + puntos_extra
        
        if puntos <= 0:
            return {'success': False, 'mensaje': 'Actividad no válida'}
        
        # Agregar puntos
        subio_nivel = perfil.agregar_puntos(puntos, razon=actividad)
        
        resultado = {
            'success': True,
            'puntos_ganados': puntos,
            'puntos_totales': perfil.puntos_totales,
            'nivel': perfil.nivel,
            'subio_nivel': subio_nivel,
            'racha_actualizada': racha_actualizada,
            'racha_dias': perfil.racha_dias_actual
        }
        
        logger.info(f"✨ {estudiante.nombre} ganó {puntos} puntos por {actividad}")
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error otorgando puntos: {e}")
        return {'success': False, 'mensaje': str(e)}


def otorgar_puntos_mensaje(estudiante):
    """Otorga puntos por enviar mensaje"""
    return otorgar_puntos_actividad(estudiante, 'mensaje_enviado')


def otorgar_puntos_audio(estudiante):
    """Otorga puntos por enviar audio"""
    return otorgar_puntos_actividad(estudiante, 'audio_enviado')


def otorgar_puntos_modulo(estudiante, modulo=None):
    """
    Otorga puntos por completar módulo
    CORE del sistema educativo
    """
    try:
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        puntos = PUNTOS_CONFIG['modulo_completado']
        
        nombre_modulo = modulo.titulo if modulo else 'Módulo'
        razon = f"📚 Módulo completado: {nombre_modulo}"
        
        resultado = perfil.agregar_puntos(puntos, razon)
        
        # Actualizar estadística
        perfil.modulos_completados += 1
        perfil.save()
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error al otorgar puntos por módulo: {e}")
        return {'success': False, 'error': str(e)}


def otorgar_puntos_examen(estudiante, puntaje, examen=None):
    """
    Otorga puntos por examen basado en CALIFICACIÓN REAL
    Sistema escalonado que premia el esfuerzo y la excelencia
    
    Args:
        estudiante: Instancia de Estudiante
        puntaje: Calificación (0-100)
        examen: Instancia de Examen (opcional)
    """
    try:
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        
        nombre_examen = examen.curso.nombre if examen else 'Evaluación'
        
        # Sistema escalonado basado en calificación
        if puntaje >= 100:
            puntos = PUNTOS_CONFIG['examen_perfecto']
            razon = f"🏆 ¡Examen Perfecto! 100% - {nombre_examen}"
            emoji = "🏆"
        elif puntaje >= 90:
            puntos = PUNTOS_CONFIG['examen_aprobado_90']
            razon = f"⭐ Excelente: {puntaje}% - {nombre_examen}"
            emoji = "⭐"
        elif puntaje >= 80:
            puntos = PUNTOS_CONFIG['examen_aprobado_80']
            razon = f"👍 Muy bien: {puntaje}% - {nombre_examen}"
            emoji = "👍"
        elif puntaje >= 70:
            puntos = PUNTOS_CONFIG['examen_aprobado_70']
            razon = f"✅ Bien: {puntaje}% - {nombre_examen}"
            emoji = "✅"
        elif puntaje >= 60:
            puntos = PUNTOS_CONFIG['examen_aprobado_60']
            razon = f"✓ Aprobado: {puntaje}% - {nombre_examen}"
            emoji = "✓"
        else:
            # Reprobado: pequeña penalización para motivar a mejorar
            puntos = PUNTOS_CONFIG['examen_reprobado']
            razon = f"💪 Intenta de nuevo: {puntaje}% - {nombre_examen}"
            emoji = "💪"
        
        resultado = perfil.agregar_puntos(puntos, razon)
        
        # Actualizar estadística solo si aprobó
        if puntaje >= 60:
            perfil.examenes_aprobados += 1
            perfil.save()
        
        resultado['emoji'] = emoji
        resultado['puntaje'] = puntaje
        resultado['mensaje_estudiante'] = f"{emoji} {razon.split(' - ')[0]}"
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error al otorgar puntos por examen: {e}")
        return {'success': False, 'error': str(e)}


def otorgar_puntos_primer_curso(estudiante):
    """Otorga puntos y badge por inscribirse en primer curso"""
    resultado = otorgar_puntos_actividad(estudiante, 'primer_curso')
    
    # Otorgar badge de "Primer Paso"
    try:
        badge_primer_curso = Badge.objects.get(nombre="Primer Paso")
        BadgeEstudiante.objects.get_or_create(
            estudiante=estudiante,
            badge=badge_primer_curso
        )
        resultado['badge_obtenido'] = badge_primer_curso.nombre
    except Badge.DoesNotExist:
        pass
    
    return resultado


def otorgar_puntos_curso_completado(estudiante, curso, promedio_final=None):
    """
    Otorga puntos y badge por completar curso
    LOGRO MAYOR con bonus por excelencia académica
    
    Args:
        estudiante: Instancia de Estudiante
        curso: Instancia de Curso completado
        promedio_final: Promedio de calificaciones del curso (0-100)
    """
    try:
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        
        # Puntos base por completar curso
        puntos = PUNTOS_CONFIG['curso_completado']
        razon = f"🎓 Curso completado: {curso.nombre}"
        
        # Bonus por excelencia académica (promedio >= 90%)
        if promedio_final and promedio_final >= 90:
            puntos = PUNTOS_CONFIG['curso_excelencia']
            razon = f"🏅 Curso con EXCELENCIA ({promedio_final}%): {curso.nombre}"
        
        resultado = perfil.agregar_puntos(puntos, razon)
        
        # Actualizar estadística
        perfil.cursos_completados += 1
        perfil.save()
        
        # Otorgar badge específico del curso si existe
        try:
            badge_curso = Badge.objects.get(
                tipo='CURSO',
                curso_requerido=curso
            )
            BadgeEstudiante.objects.get_or_create(
                estudiante=estudiante,
                badge=badge_curso
            )
            resultado['badge_obtenido'] = badge_curso.nombre
        except Badge.DoesNotExist:
            pass
        
        resultado['promedio'] = promedio_final
        resultado['excelencia'] = promedio_final >= 90 if promedio_final else False
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error al otorgar puntos por curso completado: {e}")
        return {'success': False, 'error': str(e)}
    except Badge.DoesNotExist:
        pass
    
    return resultado


def obtener_ranking_global(limite=10):
    """
    Obtiene el ranking global de estudiantes
    
    Args:
        limite: Número máximo de estudiantes a retornar
    
    Returns:
        QuerySet de PerfilGamificacion ordenado por puntos
    """
    return PerfilGamificacion.objects.select_related('estudiante').order_by(
        '-puntos_totales'
    )[:limite]


def obtener_posicion_estudiante(estudiante):
    """
    Obtiene la posición del estudiante en el ranking
    
    Args:
        estudiante: Instancia de Estudiante
    
    Returns:
        int: Posición en el ranking (1-indexed)
    """
    try:
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
        posicion = PerfilGamificacion.objects.filter(
            puntos_totales__gt=perfil.puntos_totales
        ).count() + 1
        
        # Actualizar posición en el perfil
        perfil.posicion_ranking = posicion
        perfil.save(update_fields=['posicion_ranking'])
        
        return posicion
    except PerfilGamificacion.DoesNotExist:
        return 0


def obtener_estadisticas_estudiante(estudiante):
    """
    Obtiene estadísticas completas de gamificación del estudiante
    
    Returns:
        dict con todas las estadísticas
    """
    try:
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
        badges = BadgeEstudiante.objects.filter(estudiante=estudiante).select_related('badge')
        
        return {
            'puntos_totales': perfil.puntos_totales,
            'nivel': perfil.nivel,
            'porcentaje_nivel': perfil.porcentaje_nivel(),
            'puntos_para_siguiente': perfil.puntos_para_siguiente_nivel(),
            'racha_actual': perfil.racha_dias_actual,
            'racha_maxima': perfil.racha_dias_maxima,
            'posicion_ranking': obtener_posicion_estudiante(estudiante),
            'badges_obtenidos': badges.count(),
            'badges': [
                {
                    'nombre': b.badge.nombre,
                    'icono': b.badge.icono,
                    'descripcion': b.badge.descripcion,
                    'fecha': b.fecha_obtenido
                }
                for b in badges
            ],
            'estadisticas': {
                'modulos_completados': perfil.modulos_completados,
                'examenes_aprobados': perfil.examenes_aprobados,
                'preguntas_respondidas': perfil.preguntas_respondidas,
                'audios_enviados': perfil.audios_enviados,
            }
        }
    except PerfilGamificacion.DoesNotExist:
        return None


def generar_mensaje_motivacional(estudiante):
    """
    Genera mensaje motivacional basado en el progreso del estudiante
    
    Returns:
        str: Mensaje motivacional personalizado
    """
    try:
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
        
        # Mensajes basados en nivel
        if perfil.nivel == 1:
            return f"🌱 ¡Estás comenzando tu camino, {estudiante.nombre}! Cada punto cuenta."
        elif perfil.nivel <= 3:
            return f"🚀 ¡Vas bien, {estudiante.nombre}! Ya estás en nivel {perfil.nivel}."
        elif perfil.nivel <= 5:
            return f"⭐ ¡Impresionante, {estudiante.nombre}! Nivel {perfil.nivel} alcanzado."
        elif perfil.nivel <= 7:
            return f"🏆 ¡Eres un experto, {estudiante.nombre}! Nivel {perfil.nivel}."
        elif perfil.nivel <= 9:
            return f"💎 ¡Increíble, {estudiante.nombre}! Nivel {perfil.nivel} es élite."
        else:
            return f"👑 ¡LEYENDA! {estudiante.nombre}, ¡has alcanzado el nivel máximo!"
        
    except PerfilGamificacion.DoesNotExist:
        return f"👋 ¡Bienvenido, {estudiante.nombre}! Comienza tu aventura educativa."


def verificar_y_otorgar_badges_automaticos(estudiante):
    """
    Verifica y otorga badges automáticos basados en logros actuales
    
    Returns:
        list: Lista de badges otorgados
    """
    try:
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
        badges_otorgados = []
        
        # Badge por nivel
        try:
            badge_nivel = Badge.objects.get(
                tipo='NIVEL',
                nivel_requerido=perfil.nivel
            )
            badge_est, created = BadgeEstudiante.objects.get_or_create(
                estudiante=estudiante,
                badge=badge_nivel
            )
            if created:
                badges_otorgados.append(badge_nivel)
        except Badge.DoesNotExist:
            pass
        
        # Badge por racha
        if perfil.racha_dias_actual >= 30:
            try:
                badge_racha = Badge.objects.get(
                    tipo='RACHA',
                    valor_requerido=30
                )
                badge_est, created = BadgeEstudiante.objects.get_or_create(
                    estudiante=estudiante,
                    badge=badge_racha
                )
                if created:
                    badges_otorgados.append(badge_racha)
            except Badge.DoesNotExist:
                pass
        elif perfil.racha_dias_actual >= 7:
            try:
                badge_racha = Badge.objects.get(
                    tipo='RACHA',
                    valor_requerido=7
                )
                badge_est, created = BadgeEstudiante.objects.get_or_create(
                    estudiante=estudiante,
                    badge=badge_racha
                )
                if created:
                    badges_otorgados.append(badge_racha)
            except Badge.DoesNotExist:
                pass
        
        return badges_otorgados
        
    except PerfilGamificacion.DoesNotExist:
        return []


def notificar_logro_academico(estudiante, tipo_logro, detalles, via='whatsapp'):
    """
    Notifica al estudiante sobre un LOGRO ACADÉMICO importante
    (módulos, exámenes, cursos - NO mensajes simples)
    
    Args:
        estudiante: Instancia de Estudiante
        tipo_logro: 'modulo' | 'examen' | 'curso'
        detalles: dict con información del logro
        via: 'whatsapp' | 'email'
    """
    try:
        perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
        
        # Construir mensaje según tipo de logro
        if tipo_logro == 'modulo':
            mensaje = f"""
🎯 ¡MÓDULO COMPLETADO!

📚 {detalles.get('nombre', 'Módulo')}
✨ +{detalles.get('puntos', 100)} puntos
🏆 Nivel {perfil.nivel} | {perfil.puntos_totales} pts totales

¡Sigue así! 💪
"""
        
        elif tipo_logro == 'examen':
            puntaje = detalles.get('puntaje', 0)
            puntos = detalles.get('puntos', 0)
            emoji = detalles.get('emoji', '✅')
            
            mensaje = f"""
{emoji} EXAMEN CALIFICADO

📝 {detalles.get('nombre', 'Evaluación')}
📊 Calificación: {puntaje}%
✨ +{puntos} puntos
🏆 Nivel {perfil.nivel}

{'¡Excelente trabajo! 🌟' if puntaje >= 90 else '¡Bien hecho! 👍' if puntaje >= 70 else '¡Sigue mejorando! 💪'}
"""
        
        elif tipo_logro == 'curso':
            excelencia = detalles.get('excelencia', False)
            promedio = detalles.get('promedio', 0)
            
            mensaje = f"""
🎓 {'¡CURSO CON EXCELENCIA!' if excelencia else '¡CURSO COMPLETADO!'}

📚 {detalles.get('nombre', 'Curso')}
{'📊 Promedio: ' + str(promedio) + '%' if promedio else ''}
✨ +{detalles.get('puntos', 500)} puntos
🏆 Nivel {perfil.nivel} | {perfil.puntos_totales} pts totales

{'¡Eres INCREÍBLE! 🏅' if excelencia else '¡Felicitaciones! 🎉'}

{f'Cursos completados: {perfil.cursos_completados}' if perfil.cursos_completados > 1 else '¡Tu primer curso completo!'}
"""
        
        else:
            return False
        
        # Enviar notificación
        if via == 'whatsapp':
            try:
                from .utils import enviar_whatsapp, enviar_whatsapp_twilio
                telefono = estudiante.telefono
                
                # Intentar con proveedor configurado
                proveedor = detalles.get('proveedor', 'meta')
                if proveedor == 'twilio':
                    enviar_whatsapp_twilio(telefono, mensaje.strip())
                else:
                    enviar_whatsapp(telefono, mensaje.strip())
                
                logger.info(f"📨 Notificación de {tipo_logro} enviada a {estudiante.nombre}")
                return True
                
            except Exception as e:
                logger.error(f"Error enviando notificación WhatsApp: {e}")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Error en notificar_logro_academico: {e}")
        return False


def calcular_promedio_curso(estudiante, curso):
    """
    Calcula el promedio de un estudiante en un curso
    basado en los exámenes completados
    
    Args:
        estudiante: Instancia de Estudiante
        curso: Instancia de Curso
    
    Returns:
        float: Promedio (0-100) o None si no hay exámenes
    """
    try:
        from .models import ResultadoExamen
        
        resultados = ResultadoExamen.objects.filter(
            estudiante=estudiante,
            examen__curso=curso
        )
        
        if not resultados.exists():
            return None
        
        suma_puntajes = sum(r.puntaje for r in resultados)
        promedio = suma_puntajes / resultados.count()
        
        return round(promedio, 2)
        
    except Exception as e:
        logger.error(f"Error calculando promedio: {e}")
        return None
