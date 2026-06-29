from core.admin._common import *  # noqa: F401,F403

# ==========================================
# PERSONALIZACIÓN DEL INDEX DEL ADMIN
# ==========================================
from django.contrib.admin import AdminSite
from django.urls import reverse
from django.utils.html import format_html

# Sobrescribir el template del index para agregar enlaces personalizados
def index_view(self, request, extra_context=None):
    """Vista personalizada del index del admin con enlaces a conversaciones"""
    extra_context = extra_context or {}
    
    # Agregar enlace a conversaciones en el contexto
    extra_context['conversaciones_url'] = reverse('conversaciones')
    extra_context['dashboard_url'] = reverse('dashboard_unificado')
    extra_context['dashboard_control_url'] = reverse('dashboard_unificado')  # Para compatibilidad con template
    extra_context['dashboard_analytics_url'] = reverse('dashboard_analytics')
    
    return AdminSite.index(self, request, extra_context)

# Aplicar la vista personalizada
admin.site.index = index_view.__get__(admin.site, AdminSite)


# ========================================
# 🎮 GAMIFICACIÓN
# ========================================
# 🏆 ADMIN UNIFICADO DE GAMIFICACIÓN (TODO EN UNO)
# ========================================

class PerfilGamificacionAdmin(admin.ModelAdmin):
    """
    🏆 GESTIÓN UNIFICADA DE GAMIFICACIÓN
    Desde aquí puedes gestionar:
    - Perfiles de Gamificación
    - Ver Badges (insignias)
    - Ver Recompensas
    - Ver Canjes de Recompensas
    """
    list_display = ('estudiante_info', 'nivel_display', 'puntos_totales', 'racha_display', 'badges_link', 'recompensas_link', 'posicion_ranking')
    list_filter = ('nivel', 'racha_dias_actual')
    search_fields = ('estudiante__nombre', 'estudiante__telefono')
    readonly_fields = ('puntos_totales', 'nivel', 'experiencia_nivel_actual', 'fecha_creacion', 'fecha_actualizacion', 'posicion_ranking')
    list_per_page = 50
    ordering = ['-puntos_totales']
    actions = ['ver_badges', 'ver_recompensas', 'resetear_racha']
    
    fieldsets = (
        ('👤 Estudiante', {
            'fields': ('estudiante',)
        }),
        ('🎯 Nivel y Puntos', {
            'fields': ('nivel', 'puntos_totales', 'experiencia_nivel_actual')
        }),
        ('🔥 Rachas', {
            'fields': ('racha_dias_actual', 'racha_dias_maxima', 'ultima_actividad')
        }),
        ('📊 Estadísticas', {
            'fields': ('modulos_completados', 'examenes_aprobados', 'preguntas_respondidas', 'audios_enviados')
        }),
        ('🏆 Ranking', {
            'fields': ('posicion_ranking',)
        }),
    )
    
    def estudiante_info(self, obj):
        return f"{obj.estudiante.nombre}"
    estudiante_info.short_description = "Estudiante"
    
    def nivel_display(self, obj):
        colores = {
            1: '#9e9e9e', 2: '#795548', 3: '#4caf50', 4: '#03a9f4',
            5: '#3f51b5', 6: '#9c27b0', 7: '#e91e63', 8: '#ff5722',
            9: '#ff9800', 10: '#ffc107'
        }
        color = colores.get(obj.nivel, '#000')
        porcentaje = obj.porcentaje_nivel()
        return format_html(
            '<div style="background:{};color:white;padding:8px 16px;border-radius:20px;font-weight:bold;text-align:center;">'
            'Nivel {} <br><small>{}% progreso</small></div>',
            color, obj.nivel, porcentaje
        )
    nivel_display.short_description = "Nivel"
    
    def racha_display(self, obj):
        if obj.racha_dias_actual >= 7:
            color = '#ff5722'
            emoji = '🔥🔥'
        elif obj.racha_dias_actual >= 3:
            color = '#ff9800'
            emoji = '🔥'
        else:
            color = '#9e9e9e'
            emoji = '📅'
        
        return format_html(
            '<span style="background:{};color:white;padding:6px 12px;border-radius:12px;font-weight:bold;">'
            '{} {} días</span>',
            color, emoji, obj.racha_dias_actual
        )
    racha_display.short_description = "Racha Actual"
    
    def badges_link(self, obj):
        """Link directo para ver badges del estudiante"""
        count = obj.get_badges().count()
        
        return format_html(
            '<a href="/admin/core/badge/" style="background:#ffc107;color:#000;padding:6px 12px;border-radius:12px;text-decoration:none;font-size:11px;font-weight:600;">🏅 {} Badges</a>',
            count
        )
    badges_link.short_description = "Insignias"
    
    def recompensas_link(self, obj):
        """Link directo para ver canjes de recompensas"""
        count = CanjeRecompensa.objects.filter(estudiante=obj.estudiante).count()
        
        return format_html(
            '<a href="/admin/core/canjerecompensa/?estudiante__id__exact={}" style="background:#9c27b0;color:white;padding:6px 12px;border-radius:12px;text-decoration:none;font-size:11px;font-weight:600;">🎁 {} Canjes</a>',
            obj.estudiante.id,
            count
        )
    recompensas_link.short_description = "Recompensas"
    
    def ver_badges(self, request, queryset):
        """Ver todos los badges disponibles"""
        from django.shortcuts import redirect
        return redirect('/admin/core/badge/')
    ver_badges.short_description = "🏅 Ver catálogo de badges"
    
    def ver_recompensas(self, request, queryset):
        """Ver todas las recompensas disponibles"""
        from django.shortcuts import redirect
        return redirect('/admin/core/recompensa/')
    ver_recompensas.short_description = "🎁 Ver catálogo de recompensas"
    
    def resetear_racha(self, request, queryset):
        """Resetear racha de estudiantes seleccionados"""
        queryset.update(racha_dias_actual=0)
        self.message_user(request, f"✅ Racha reseteada para {queryset.count()} estudiante(s)")
    resetear_racha.short_description = "🔄 Resetear racha"
    
    def badges_count(self, obj):
        count = obj.get_badges().count()
        if count > 0:
            return format_html(
                '<span style="background:#ffc107;color:#000;padding:6px 12px;border-radius:12px;font-weight:bold;">'
                '🏆 {} badges</span>',
                count
            )
        return format_html('<span style="color:#999;">0</span>')
    badges_count.short_description = "Badges"


class BadgeAdmin(admin.ModelAdmin):
    """Administración de badges/insignias (Ver también desde Perfil Gamificación)"""
    list_display = ('icono_nombre', 'tipo', 'descripcion_corta', 'criterios', 'puntos_bonus', 'total_obtenidos_display', 'activo')
    list_filter = ('tipo', 'activo', 'es_secreto')
    search_fields = ('nombre', 'descripcion')
    list_editable = ('activo',)
    list_per_page = 50
    ordering = ['orden', 'tipo', 'nombre']
    
    fieldsets = (
        ('🏆 Información del Badge', {
            'fields': ('nombre', 'descripcion', 'icono', 'tipo')
        }),
        ('✅ Criterios de Obtención', {
            'fields': ('nivel_requerido', 'valor_requerido', 'curso_requerido', 'puntos_bonus')
        }),
        ('⚙️ Configuración', {
            'fields': ('es_secreto', 'activo', 'orden')
        }),
    )
    
    actions = ['duplicar_badge', 'activar_badges', 'desactivar_badges']
    
    def icono_nombre(self, obj):
        return f"{obj.icono} {obj.nombre}"
    icono_nombre.short_description = "Badge"
    
    def descripcion_corta(self, obj):
        if len(obj.descripcion) > 60:
            return obj.descripcion[:60] + '...'
        return obj.descripcion
    descripcion_corta.short_description = "Descripción"
    
    def criterios(self, obj):
        """Muestra los criterios para obtener el badge"""
        criterios = []
        if obj.nivel_requerido:
            criterios.append(f"Nivel {obj.nivel_requerido}")
        if obj.valor_requerido:
            if obj.tipo == 'RACHA':
                criterios.append(f"{obj.valor_requerido} días de racha")
            elif obj.tipo == 'CURSO':
                criterios.append(f"{obj.valor_requerido} cursos completados")
            else:
                criterios.append(f"Valor: {obj.valor_requerido}")
        if obj.curso_requerido:
            criterios.append(f"Curso: {obj.curso_requerido.nombre}")
        
        if not criterios:
            return format_html('<span style="color:#999;font-style:italic;">Sin criterios</span>')
        
        return format_html('<span style="color:#666;">{}</span>', ' | '.join(criterios))
    criterios.short_description = "Criterios"
    
    def total_obtenidos_display(self, obj):
        count = obj.total_obtenidos()
        if count > 0:
            return format_html(
                '<span style="background:#4caf50;color:white;padding:4px 12px;border-radius:12px;font-weight:bold;">{} estudiantes</span>',
                count
            )
        return format_html('<span style="color:#999;">Nadie aún</span>')
    total_obtenidos_display.short_description = "Obtenido por"
    
    def duplicar_badge(self, request, queryset):
        """Duplica badges seleccionados"""
        count = 0
        for badge in queryset:
            badge.pk = None
            badge.nombre = f"{badge.nombre} (Copia)"
            badge.save()
            count += 1
        self.message_user(request, f"{count} badge(s) duplicado(s)")
    duplicar_badge.short_description = "📋 Duplicar badges"
    
    def activar_badges(self, request, queryset):
        count = queryset.update(activo=True)
        self.message_user(request, f"{count} badge(s) activado(s)")
    activar_badges.short_description = "✅ Activar badges"
    
    def desactivar_badges(self, request, queryset):
        count = queryset.update(activo=False)
        self.message_user(request, f"{count} badge(s) desactivado(s)")
    desactivar_badges.short_description = "❌ Desactivar badges"


class BadgeEstudianteAdmin(admin.ModelAdmin):
    """Administración de badges obtenidos por estudiantes"""
    list_display = ('estudiante', 'badge_display', 'fecha_obtenido')
    list_filter = ('badge__tipo', 'fecha_obtenido')
    search_fields = ('estudiante__nombre', 'badge__nombre')
    readonly_fields = ('fecha_obtenido',)
    list_per_page = 50

    def badge_display(self, obj):
        return f"{obj.badge.icono} {obj.badge.nombre}"
    badge_display.short_description = "Badge"


class AliadoEmpleabilidadAdmin(admin.ModelAdmin):
    list_display = (
        'nombre_empresa',
        'cliente',
        'vacantes_activas',
        'cupos_disponibles',
        'prioridad',
        'vigencia_desde',
        'vigencia_hasta',
        'latitud',
        'longitud',
        'codigo_secreto',
    )
    list_filter = ('vacantes_activas', 'cliente', 'prioridad', 'vigencia_desde', 'vigencia_hasta')
    search_fields = ('nombre_empresa', 'codigo_secreto')
    list_editable = ('vacantes_activas', 'cupos_disponibles', 'prioridad')


class MisionEmpleabilidadAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'estudiante',
        'aliado',
        'cliente',
        'estado',
        'estado_flujo',
        'puntaje_prioridad',
        'distancia_metros',
        'codigo_validado',
        'puntos_otorgados',
        'fecha_descubierta',
    )
    list_filter = ('estado', 'estado_flujo', 'cliente', 'codigo_validado', 'fecha_descubierta')
    search_fields = ('estudiante__nombre', 'estudiante__telefono', 'aliado__nombre_empresa')
    readonly_fields = (
        'fecha_descubierta',
        'fecha_reclamada',
        'fecha_completada',
        'fecha_interes',
        'fecha_postulacion',
        'fecha_entrevista',
        'fecha_vinculacion',
    )
    list_per_page = 100


class PreguntaAbiertaFinalCursoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'orden', 'activa', 'fecha_creacion')
    list_filter = ('activa', 'curso')
    search_fields = ('curso__nombre', 'pregunta')
    ordering = ('curso', 'orden', 'id')


class RespuestaAbiertaFinalAdmin(admin.ModelAdmin):
    list_display = ('estudiante', 'curso', 'estado', 'calificacion', 'fecha_respuesta', 'fecha_calificacion')
    list_filter = ('estado', 'curso', 'fecha_respuesta')
    search_fields = ('estudiante__nombre', 'estudiante__telefono', 'respuesta_texto')
    readonly_fields = ('estudiante', 'curso', 'pregunta', 'progreso', 'respuesta_texto', 'fecha_respuesta')

    fieldsets = (
        ('Respuesta del estudiante', {
            'fields': ('estudiante', 'curso', 'pregunta', 'progreso', 'respuesta_texto', 'fecha_respuesta')
        }),
        ('Calificación facilitadora', {
            'fields': ('estado', 'calificacion', 'retroalimentacion', 'calificada_por', 'fecha_calificacion')
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.calificacion is not None:
            obj.estado = 'calificada'
            obj.calificada_por = request.user
            if not obj.fecha_calificacion:
                obj.fecha_calificacion = timezone.now()
        super().save_model(request, obj, form, change)

    ordering = ['-fecha_respuesta']


try:
    admin.site.unregister(RespuestaAbiertaFinal)
except admin.sites.NotRegistered:
    pass


class TransaccionPuntosAdmin(admin.ModelAdmin):
    """Historial de transacciones de puntos"""
    list_display = ('estudiante_nombre', 'puntos_display', 'tipo', 'razon', 'fecha')
    list_filter = ('tipo', 'fecha')
    search_fields = ('perfil__estudiante__nombre', 'razon')
    readonly_fields = ('fecha',)
    list_per_page = 100
    ordering = ['-fecha']
    
    def estudiante_nombre(self, obj):
        return obj.perfil.estudiante.nombre
    estudiante_nombre.short_description = "Estudiante"
    
    def puntos_display(self, obj):
        if obj.tipo in ['GANANCIA', 'BONUS']:
            color = '#4caf50'
            signo = '+'
        else:
            color = '#f44336'
            signo = '-'
        
        return format_html(
            '<span style="background:{};color:white;padding:4px 12px;border-radius:8px;font-weight:bold;">{}{}</span>',
            color, signo, obj.puntos
        )
    puntos_display.short_description = "Puntos"


# ========== RECOMPENSAS ==========
class RecompensaAdmin(admin.ModelAdmin):
    """Gestión de recompensas canjeables (Ver también desde Perfil Gamificación)"""
    list_display = ('icono_nombre', 'puntos_requeridos', 'tipo', 'estado', 'cantidad_info', 'nivel_minimo', 'destacado', 'canjes_totales')
    list_filter = ('tipo', 'estado', 'destacado', 'activo')
    search_fields = ('nombre', 'descripcion')
    list_editable = ('destacado',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'descripcion', 'icono', 'imagen_url')
        }),
        ('Configuración', {
            'fields': ('tipo', 'puntos_requeridos', 'estado', 'cantidad_disponible', 'nivel_minimo')
        }),
        ('Disponibilidad Temporal', {
            'fields': ('fecha_inicio', 'fecha_fin'),
            'classes': ('collapse',)
        }),
        ('Entrega', {
            'fields': ('instrucciones_entrega', 'enlace_descarga'),
            'classes': ('collapse',)
        }),
        ('Visualización', {
            'fields': ('orden', 'destacado', 'activo')
        }),
    )
    
    def icono_nombre(self, obj):
        destacado = '⭐' if obj.destacado else ''
        return format_html(
            '<span style="font-size:18px;">{} {}</span> {}',
            obj.icono, obj.nombre, destacado
        )
    icono_nombre.short_description = "Recompensa"
    
    def cantidad_info(self, obj):
        restante = obj.cantidad_restante()
        if restante is None:
            return format_html('<span style="color:#4caf50;">∞ Ilimitado</span>')
        
        color = '#4caf50' if restante > 10 else '#ff9800' if restante > 0 else '#f44336'
        return format_html(
            '<span style="color:{};">{} / {}</span>',
            color, restante, obj.cantidad_disponible
        )
    cantidad_info.short_description = "Disponible"
    
    def canjes_totales(self, obj):
        return format_html(
            '<span style="background:#2196f3;color:white;padding:4px 8px;border-radius:4px;">{} canjes</span>',
            obj.cantidad_canjeada
        )
    canjes_totales.short_description = "Canjeado"
    
    actions = ['duplicar_recompensa', 'marcar_destacado', 'marcar_agotado']
    
    def duplicar_recompensa(self, request, queryset):
        for recompensa in queryset:
            recompensa.pk = None
            recompensa.nombre = f"{recompensa.nombre} (Copia)"
            recompensa.cantidad_canjeada = 0
            recompensa.save()
        self.message_user(request, f"{queryset.count()} recompensa(s) duplicada(s)")
    duplicar_recompensa.short_description = "Duplicar recompensas seleccionadas"
    
    def marcar_destacado(self, request, queryset):
        queryset.update(destacado=True)
        self.message_user(request, f"{queryset.count()} recompensa(s) marcada(s) como destacadas")
    marcar_destacado.short_description = "Marcar como destacado"
    
    def marcar_agotado(self, request, queryset):
        queryset.update(estado='AGOTADO')
        self.message_user(request, f"{queryset.count()} recompensa(s) marcada(s) como agotadas")
    marcar_agotado.short_description = "Marcar como agotado"


class CanjeRecompensaAdmin(admin.ModelAdmin):
    """Gestión de canjes de recompensas (Ver también desde Perfil Gamificación)"""
    list_display = ('estudiante_nombre', 'recompensa_info', 'puntos_gastados', 'estado_display', 'fecha_canje', 'fecha_entrega', 'atendido_por')
    list_filter = ('estado', 'fecha_canje', 'recompensa__tipo')
    search_fields = ('estudiante__nombre', 'recompensa__nombre')
    readonly_fields = ('estudiante', 'recompensa', 'puntos_gastados', 'fecha_canje')
    
    fieldsets = (
        ('Información del Canje', {
            'fields': ('estudiante', 'recompensa', 'puntos_gastados', 'fecha_canje', 'estado')
        }),
        ('Entrega', {
            'fields': ('fecha_entrega', 'nota_entrega', 'atendido_por')
        }),
    )
    
    def estudiante_nombre(self, obj):
        return obj.estudiante.nombre
    estudiante_nombre.short_description = "Estudiante"
    
    def recompensa_info(self, obj):
        return format_html(
            '{} <b>{}</b>',
            obj.recompensa.icono, obj.recompensa.nombre
        )
    recompensa_info.short_description = "Recompensa"
    
    def estado_display(self, obj):
        colores = {
            'PENDIENTE': '#ff9800',
            'PROCESANDO': '#2196f3',
            'ENTREGADO': '#4caf50',
            'CANCELADO': '#f44336'
        }
        return format_html(
            '<span style="background:{};color:white;padding:4px 12px;border-radius:12px;">{}</span>',
            colores.get(obj.estado, '#999'), obj.get_estado_display()
        )
    estado_display.short_description = "Estado"
    
    actions = ['marcar_entregado', 'marcar_procesando']
    
    def marcar_entregado(self, request, queryset):
        count = 0
        for canje in queryset:
            canje.marcar_entregado(nota="Marcado como entregado desde admin")
            count += 1
        self.message_user(request, f"{count} canje(s) marcado(s) como entregados")
    marcar_entregado.short_description = "Marcar como entregado"
    
    def marcar_procesando(self, request, queryset):
        queryset.update(estado='PROCESANDO')
        self.message_user(request, f"{queryset.count()} canje(s) en procesamiento")
    marcar_procesando.short_description = "Marcar como procesando"


