"""
Comando Django para administrar el sistema eki
python manage.py eki [acción]

Compatible con entornos de producción (Heroku, Render, Railway, etc.)
"""
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import connection, transaction
from django.conf import settings
import sys
import os


class Command(BaseCommand):
    help = 'Administración del sistema eki MVP - Compatible con Heroku/Render'

    def add_arguments(self, parser):
        parser.add_argument(
            'accion',
            nargs='?',
            type=str,
            choices=['setup', 'migrar', 'temas', 'conversacion', 'verificar', 'stats', 'agentes', 'health'],
            help='Acción a ejecutar'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar ejecución sin confirmación'
        )

    def handle(self, *args, **options):
        accion = options.get('accion')
        force = options.get('force', False)
        
        # Verificar conexión a BD
        try:
            self.verificar_conexion_db()
        except Exception as e:
            raise CommandError(f"❌ Error de conexión a BD: {e}")
        
        if not accion:
            self.mostrar_menu()
            return
        
        # Ejecutar acción con manejo de errores robusto
        try:
            if accion == 'setup':
                self.setup_completo(force)
            elif accion == 'migrar':
                self.migrar()
            elif accion == 'temas':
                self.crear_temas()
            elif accion == 'conversacion':
                self.crear_conversacion()
            elif accion == 'verificar':
                self.verificar_conversaciones()
            elif accion == 'stats':
                self.mostrar_estadisticas()
            elif accion == 'agentes':
                self.reporte_agentes()
            elif accion == 'health':
                self.health_check()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n⚠️  Operación cancelada por el usuario"))
            sys.exit(0)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error: {str(e)}"))
            if settings.DEBUG:
                import traceback
                self.stdout.write(traceback.format_exc())
            sys.exit(1)
    
    def verificar_conexion_db(self):
        """Verifica que la conexión a la base de datos funcione"""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

    def mostrar_menu(self):
        """Muestra el menú interactivo"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("🌱 eki MVP - ADMINISTRACIÓN"))
        self.stdout.write("="*60 + "\n")
        
        # Mostrar información del entorno
        env = "PRODUCCIÓN" if not settings.DEBUG else "DESARROLLO"
        db_engine = settings.DATABASES['default']['ENGINE'].split('.')[-1]
        self.stdout.write(f"Entorno: {env} | Base de datos: {db_engine}\n")
        
        self.stdout.write("Comandos disponibles:\n")
        self.stdout.write("  python manage.py eki setup       - Configuración inicial completa")
        self.stdout.write("  python manage.py eki migrar      - Aplicar migraciones")
        self.stdout.write("  python manage.py eki temas       - Crear temas de campaña")
        self.stdout.write("  python manage.py eki conversacion- Crear conversación de prueba")
        self.stdout.write("  python manage.py eki verificar   - Verificar estado")
        self.stdout.write("  python manage.py eki stats       - Estadísticas del sistema")
        self.stdout.write("  python manage.py eki agentes     - Reporte de agentes IA")
        self.stdout.write("  python manage.py eki health      - Health check completo\n")
        
        self.stdout.write("Opciones:")
        self.stdout.write("  --force                          - Forzar sin confirmación\n")

    def setup_completo(self, force=False):
        """Configuración inicial completa del sistema"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("🚀 CONFIGURACIÓN INICIAL COMPLETA"))
        self.stdout.write("="*60 + "\n")
        
        if not force and not settings.DEBUG:
            respuesta = input("\n⚠️  Estás en PRODUCCIÓN. ¿Continuar? (yes/no): ")
            if respuesta.lower() != 'yes':
                self.stdout.write(self.style.WARNING("Operación cancelada"))
                return
        
        # 1. Migraciones
        self.stdout.write("\n📦 Paso 1/3: Aplicando migraciones...")
        try:
            call_command('migrate', verbosity=0)
            self.stdout.write(self.style.SUCCESS("  ✅ Migraciones completadas"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Error en migraciones: {e}"))
            raise
        
        # 2. Crear temas
        self.stdout.write("\n🏷️  Paso 2/3: Creando temas de campaña...")
        try:
            self.crear_temas()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Error creando temas: {e}"))
            raise
        
        # 3. Crear conversación de prueba (solo en desarrollo)
        if settings.DEBUG:
            self.stdout.write("\n💬 Paso 3/3: Creando conversación de prueba...")
            if force:
                respuesta = 's'
            else:
                respuesta = input("\n¿Deseas crear una conversación de prueba? (s/n): ")
            
            if respuesta.lower() == 's':
                try:
                    self.crear_conversacion()
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  ⚠️  Error: {e}"))
        else:
            self.stdout.write("\n⏭️  Paso 3/3: Omitido (producción)")
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("✅ CONFIGURACIÓN COMPLETADA"))
        self.stdout.write("="*60)
        
        if settings.DEBUG:
            self.stdout.write("\n📍 Accede al admin: http://127.0.0.1:8000/admin/")
            self.stdout.write("📍 Usuario: admin / Password: Jul14n123\n")
        else:
            self.stdout.write("\n📍 Sistema listo para producción\n")

    def migrar(self):
        """Aplica las migraciones"""
        self.stdout.write("\n📦 Aplicando migraciones...")
        try:
            call_command('makemigrations', verbosity=1)
            call_command('migrate', verbosity=1)
            self.stdout.write(self.style.SUCCESS("✅ Migraciones completadas\n"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}\n"))
            raise

    def crear_temas(self):
        """Crea temas de campaña con transacción atómica"""
        from core.models import TemaCampana
        
        temas_crear = [
            {'nombre': 'Café', 'emoji': '☕', 'descripcion': 'Plantillas relacionadas con cultivo de café'},
            {'nombre': 'Aguacate', 'emoji': '🥑', 'descripcion': 'Plantillas relacionadas con cultivo de aguacate'},
            {'nombre': 'Maíz', 'emoji': '🌽', 'descripcion': 'Plantillas relacionadas con cultivo de maíz'},
            {'nombre': 'Yuca', 'emoji': '🥔', 'descripcion': 'Plantillas relacionadas con cultivo de yuca'},
            {'nombre': 'Plátano', 'emoji': '🍌', 'descripcion': 'Plantillas relacionadas con cultivo de plátano'},
            {'nombre': 'Cacao', 'emoji': '🍫', 'descripcion': 'Cultivo de cacao'},
            {'nombre': 'Motivación General', 'emoji': '💪', 'descripcion': 'Mensajes motivacionales generales'},
            {'nombre': 'Recordatorios', 'emoji': '⏰', 'descripcion': 'Mensajes de recordatorio'},
            {'nombre': 'Bienvenida', 'emoji': '👋', 'descripcion': 'Mensajes de bienvenida'},
            {'nombre': 'Evaluaciones', 'emoji': '📝', 'descripcion': 'Información sobre exámenes'},
            {'nombre': 'Técnicas Agrícolas', 'emoji': '🌱', 'descripcion': 'Técnicas generales de agricultura'},
        ]
        
        creados = 0
        existentes = 0
        
        with transaction.atomic():
            for tema_data in temas_crear:
                try:
                    tema, created = TemaCampana.objects.get_or_create(
                        nombre=tema_data['nombre'],
                        defaults={
                            'emoji': tema_data['emoji'],
                            'descripcion': tema_data['descripcion'],
                            'activo': True
                        }
                    )
                    
                    if created:
                        self.stdout.write(f"  ✅ {tema}")
                        creados += 1
                    else:
                        self.stdout.write(f"  ℹ️  {tema} (ya existe)")
                        existentes += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ❌ Error con {tema_data['nombre']}: {e}"))
        
        self.stdout.write(f"\n✅ Temas creados: {creados}")
        self.stdout.write(f"ℹ️  Temas existentes: {existentes}")
        self.stdout.write(f"📁 Total: {TemaCampana.objects.count()}\n")

    def crear_conversacion(self):
        """Crea una conversación de prueba"""
        from core.models import Estudiante, WhatsappLog
        from django.utils import timezone
        from datetime import timedelta
        
        # Verificar o crear estudiante
        estudiante, created = Estudiante.objects.get_or_create(
            telefono='573001234567',
            defaults={
                'nombre': 'Juan Pérez Demo',
                'activo': True
            }
        )
        
        if created:
            self.stdout.write(f"✅ Estudiante creado: {estudiante.nombre}")
        else:
            self.stdout.write(f"ℹ️  Usando estudiante existente: {estudiante.nombre}")
        
        # Conversación de ejemplo
        conversacion = [
            {'tipo': 'INCOMING', 'mensaje': 'Hola, necesito ayuda con matemáticas', 'tiempo': -10},
            {'tipo': 'SENT', 'mensaje': '¡Hola! Estoy aquí para ayudarte. ¿Qué tema de matemáticas te está costando?', 'tiempo': -9},
            {'tipo': 'INCOMING', 'mensaje': 'Es que no entiendo las fracciones', 'tiempo': -8},
            {'tipo': 'SENT', 'mensaje': '📊 Perfecto. Una fracción representa una parte de un todo. Por ejemplo: 1/2 significa "la mitad". ¿Te explico con ejemplos del campo?', 'tiempo': -7},
            {'tipo': 'INCOMING', 'mensaje': 'Sí por favor', 'tiempo': -6},
            {'tipo': 'SENT', 'mensaje': '🌾 Imagina que tienes 1 hectárea de tierra. 1/2 hectárea = la mitad del terreno. Si plantas maíz en 1/2 y yuca en 1/4, ¿cuánto usaste?', 'tiempo': -5},
            {'tipo': 'INCOMING', 'mensaje': 'Creo que 3/4?', 'tiempo': -3},
            {'tipo': 'SENT', 'mensaje': '🎉 ¡Correcto! 1/2 + 1/4 = 3/4. Muy bien, Juan. ¿Practicamos más?', 'tiempo': -2},
        ]
        
        with transaction.atomic():
            for i, msg_data in enumerate(conversacion, 1):
                fecha = timezone.now() + timedelta(minutes=msg_data['tiempo'])
                WhatsappLog.objects.create(
                    telefono=estudiante.telefono,
                    mensaje=msg_data['mensaje'],
                    mensaje_id=f"demo_{timezone.now().timestamp()}_{i}",
                    tipo=msg_data['tipo'],
                    estado='SENT' if msg_data['tipo'] == 'SENT' else 'RECEIVED',
                    estudiante=estudiante,
                    fecha=fecha
                )
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Conversación de prueba creada"))
        self.stdout.write(f"👤 Estudiante: {estudiante.nombre}")
        self.stdout.write(f"💬 Mensajes: {len(conversacion)}")
        if settings.DEBUG:
            self.stdout.write(f"🔗 Ver: http://127.0.0.1:8000/admin/conversaciones/?estudiante={estudiante.id}\n")

    def verificar_conversaciones(self):
        """Verifica el estado de las conversaciones"""
        from core.models import Estudiante, WhatsappLog
        
        total_estudiantes = Estudiante.objects.count()
        total_whatsapp = WhatsappLog.objects.count()
        whatsapp_con_estudiante = WhatsappLog.objects.filter(estudiante__isnull=False).count()
        whatsapp_incoming = WhatsappLog.objects.filter(tipo='INCOMING').count()
        whatsapp_sent = WhatsappLog.objects.filter(tipo='SENT').count()
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("🔍 ESTADO DE CONVERSACIONES"))
        self.stdout.write("="*60 + "\n")
        
        self.stdout.write(f"👥 Estudiantes: {total_estudiantes}")
        self.stdout.write(f"\n💬 Mensajes WhatsApp:")
        self.stdout.write(f"   - Total: {total_whatsapp}")
        self.stdout.write(f"   - Con estudiante: {whatsapp_con_estudiante}")
        self.stdout.write(f"   - Recibidos (INCOMING): {whatsapp_incoming}")
        self.stdout.write(f"   - Enviados (SENT): {whatsapp_sent}")
        
        if total_whatsapp > 0:
            self.stdout.write(f"\n📋 Últimos 3 mensajes:")
            for msg in WhatsappLog.objects.select_related('estudiante').order_by('-fecha')[:3]:
                estudiante_nombre = msg.estudiante.nombre if msg.estudiante else "Sin asignar"
                tipo_emoji = "📥" if msg.tipo == 'INCOMING' else "📤"
                self.stdout.write(f"   {tipo_emoji} {msg.fecha.strftime('%Y-%m-%d %H:%M')} | {estudiante_nombre} | {msg.mensaje[:40]}...")
        
        self.stdout.write("")

    def mostrar_estadisticas(self):
        """Muestra estadísticas del sistema"""
        from core.models import Estudiante, WhatsappLog, Campana, Plantilla, TemaCampana
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📊 ESTADÍSTICAS DEL SISTEMA"))
        self.stdout.write("="*60 + "\n")
        
        self.stdout.write(f"👥 Estudiantes: {Estudiante.objects.count()}")
        self.stdout.write(f"💬 Mensajes WhatsApp: {WhatsappLog.objects.count()}")
        self.stdout.write(f"📢 Campañas: {Campana.objects.count()}")
        self.stdout.write(f"📄 Plantillas: {Plantilla.objects.count()}")
        self.stdout.write(f"🏷️  Temas: {TemaCampana.objects.count()}\n")

    def reporte_agentes(self):
        """Muestra reporte de agentes IA"""
        try:
            call_command('reporte_agentes')
        except:
            self.stdout.write(self.style.WARNING("⚠️  Comando reporte_agentes no disponible\n"))
    
    def health_check(self):
        """Health check completo del sistema (tipo Heroku)"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("🏥 HEALTH CHECK"))
        self.stdout.write("="*60 + "\n")
        
        checks_passed = 0
        checks_total = 0
        
        # 1. Conexión a BD
        checks_total += 1
        try:
            self.verificar_conexion_db()
            self.stdout.write(self.style.SUCCESS("✅ Conexión a base de datos"))
            checks_passed += 1
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Base de datos: {e}"))
        
        # 2. Migraciones aplicadas
        checks_total += 1
        try:
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                self.stdout.write(self.style.WARNING(f"⚠️  Migraciones pendientes: {len(plan)}"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Migraciones actualizadas"))
                checks_passed += 1
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error verificando migraciones: {e}"))
        
        # 3. Variables de entorno críticas
        checks_total += 1
        env_vars = ['SECRET_KEY', 'ALLOWED_HOSTS']
        missing_vars = [var for var in env_vars if not os.environ.get(var) and var not in dir(settings)]
        
        if not missing_vars:
            self.stdout.write(self.style.SUCCESS("✅ Variables de entorno configuradas"))
            checks_passed += 1
        else:
            self.stdout.write(self.style.WARNING(f"⚠️  Variables faltantes: {', '.join(missing_vars)}"))
        
        # 4. Modelos principales
        checks_total += 1
        try:
            from core.models import Estudiante, WhatsappLog, Campana, Plantilla
            Estudiante.objects.exists()
            self.stdout.write(self.style.SUCCESS("✅ Modelos principales accesibles"))
            checks_passed += 1
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error con modelos: {e}"))
        
        # 5. OpenAI API Key
        checks_total += 1
        openai_key = os.environ.get('OPENAI_API_KEY')
        if openai_key:
            self.stdout.write(self.style.SUCCESS("✅ OpenAI API Key configurada"))
            checks_passed += 1
        else:
            self.stdout.write(self.style.WARNING("⚠️  OpenAI API Key no encontrada"))
        
        # Resumen
        self.stdout.write("\n" + "-"*60)
        percentage = (checks_passed / checks_total) * 100
        
        if percentage == 100:
            status_style = self.style.SUCCESS
            status = "🎉 SISTEMA SALUDABLE"
        elif percentage >= 75:
            status_style = self.style.WARNING
            status = "⚠️  SISTEMA FUNCIONAL (con advertencias)"
        else:
            status_style = self.style.ERROR
            status = "❌ SISTEMA CON PROBLEMAS"
        
        self.stdout.write(status_style(f"{status}"))
        self.stdout.write(f"Checks: {checks_passed}/{checks_total} ({percentage:.0f}%)\n")
