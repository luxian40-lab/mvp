"""
Vista de ranking y leaderboard de gamificación
"""

from django.contrib import admin
from django.db.models import Count, Avg, Max
from django.utils.html import format_html
from .gamificacion import PerfilGamificacion, BadgeEstudiante
from .models import Estudiante


class RankingGamificacionAdmin(admin.ModelAdmin):
    """Vista personalizada de rankings de gamificación"""
    
    change_list_template = 'admin/ranking_gamificacion.html'
    
    def changelist_view(self, request, extra_context=None):
        # Top 10 por puntos totales
        top_puntos = PerfilGamificacion.objects.select_related('estudiante').order_by('-puntos_totales')[:10]
        
        # Top 10 por nivel
        top_nivel = PerfilGamificacion.objects.select_related('estudiante').order_by('-nivel', '-experiencia_nivel_actual')[:10]
        
        # Top 10 por racha actual
        top_racha = PerfilGamificacion.objects.select_related('estudiante').order_by('-racha_dias_actual')[:10]
        
        # Top coleccionistas de badges
        top_badges = Estudiante.objects.annotate(
            total_badges=Count('badges_obtenidos')
        ).filter(total_badges__gt=0).order_by('-total_badges')[:10]
        
        # Estadísticas generales
        total_estudiantes = PerfilGamificacion.objects.count()
        puntos_promedio = PerfilGamificacion.objects.aggregate(avg=Avg('puntos_totales'))['avg'] or 0
        nivel_promedio = PerfilGamificacion.objects.aggregate(avg=Avg('nivel'))['avg'] or 0
        racha_maxima = PerfilGamificacion.objects.aggregate(max=Max('racha_dias_maxima'))['max'] or 0
        
        extra_context = extra_context or {}
        extra_context.update({
            'title': '🏆 Rankings de Gamificación',
            'top_puntos': top_puntos,
            'top_nivel': top_nivel,
            'top_racha': top_racha,
            'top_badges': top_badges,
            'estadisticas': {
                'total_estudiantes': total_estudiantes,
                'puntos_promedio': round(puntos_promedio),
                'nivel_promedio': round(nivel_promedio, 1),
                'racha_maxima': racha_maxima,
            }
        })
        
        return super().changelist_view(request, extra_context=extra_context)
