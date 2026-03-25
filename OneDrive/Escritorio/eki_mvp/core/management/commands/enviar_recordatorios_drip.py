"""
Comando de gestión Django para enviar recordatorios de re-enganche de Drip Content.

Uso:
    python manage.py enviar_recordatorios_drip

Programar con cron (diariamente a las 8 AM):
    0 8 * * * cd /ruta/proyecto && python manage.py enviar_recordatorios_drip

O con Heroku Scheduler (add-on):
    python manage.py enviar_recordatorios_drip
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from core.models import ProgresoEstudiante
from core.utils import enviar_whatsapp


class Command(BaseCommand):
    help = 'Envía recordatorios a estudiantes cuyo módulo Drip Content se desbloquea hoy.'

    def handle(self, *args, **options):
        hoy = timezone.now().date()
        enviados = 0
        errores = 0

        # Buscar progresos en curso con espera configurada y fecha_ultimo_avance establecida
        progresos = ProgresoEstudiante.objects.filter(
            estado='en_curso',
            fecha_ultimo_avance__isnull=False,
            curso__dias_espera_entre_modulos__gt=0,
        ).select_related('estudiante', 'curso')

        for progreso in progresos:
            dias = progreso.curso.dias_espera_entre_modulos
            fecha_desbloqueo = (progreso.fecha_ultimo_avance + timedelta(days=dias)).date()

            if fecha_desbloqueo == hoy:
                nombre = progreso.estudiante.nombre.split()[0]  # Solo primer nombre
                telefono = progreso.estudiante.telefono
                curso = progreso.curso.nombre

                mensaje = (
                    f"¡Hola {nombre}! 🎓 Tu nuevo módulo de *{curso}* ya está disponible. "
                    f"Responde *LISTO* para continuar. 🚀"
                )

                resultado = enviar_whatsapp(telefono, mensaje)
                if resultado.get('success'):
                    enviados += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Recordatorio enviado a {nombre} ({telefono})')
                    )
                else:
                    errores += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ Error enviando a {nombre} ({telefono}): {resultado.get("response")}'
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🏁 Proceso completado: {enviados} enviados, {errores} errores.'
            )
        )
