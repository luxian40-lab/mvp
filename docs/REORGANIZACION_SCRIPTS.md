# Reorganización de Scripts del Proyecto EKI

## Estructura Actual (DESORGANIZADA)
50+ scripts Python en la raíz del proyecto mezclados

## Estructura Propuesta (PROFESIONAL)

```
eki_mvp/
├── manage.py
├── scripts/                    # Scripts de administración
│   ├── setup/                  # Scripts de configuración inicial
│   │   ├── crear_cursos_demo.py
│   │   ├── crear_datos_gamificacion.py
│   │   ├── crear_grupos_ejemplo.py
│   │   ├── crear_temas_campana.py
│   │   ├── load_demo_data.py
│   │   └── setup_vosk.py
│   │
│   ├── maintenance/            # Scripts de mantenimiento
│   │   ├── backup_certificados.py
│   │   ├── run_backup.py
│   │   ├── compile_messages.py
│   │   └── cleanup_project.py
│   │
│   ├── verification/           # Scripts de verificación
│   │   ├── verificar_deployment.py
│   │   ├── verificar_twilio.py
│   │   ├── verificar_certificados.py
│   │   ├── verificar_cursos.py
│   │   ├── verificar_demo.py
│   │   └── diagnostico_sistema.py
│   │
│   ├── utils/                  # Utilidades
│   │   ├── comprimir_videos.py
│   │   ├── generar_secret_key.py
│   │   ├── validar_telefonos.py
│   │   └── crear_plantilla.py
│   │
│   └── dev/                    # Scripts de desarrollo/testing
│       ├── test_sistema_completo.py
│       ├── crear_conversacion_prueba.py
│       └── quick_verify.py
│
├── core/                       # Aplicación Django
├── mvp_project/               # Settings
└── docs/                      # Documentación
    ├── CODE_CLEANUP_REPORT.md
    ├── DEPLOYMENT_GUIDE.md
    └── RESUMEN_LIMPIEZA.md
```

## Scripts a Eliminar (OBSOLETOS)
- agregar_curso_cacao.py - Ya se creó, no se necesita más
- agregar_preguntas_modulos.py - Obsoleto
- ajustar_emojis.py - Ya se ejecutó, eliminar
- asociar_video.py - Funcionalidad debe estar en admin
- crear_curso_platano.py - Ya se creó
- crear_cursos_inicial.py - Usar crear_cursos_demo.py
- generar_certificado_julian.py - Script específico, eliminar
- load_cafe_data.py - Usar load_demo_data.py
- reorganizar_preguntas.py - Una sola vez, eliminar
- resetear_estudiante.py - Funcionalidad en admin
- resetear_estudiante_simple.py - Duplicado
- simplificar_mensajes.py - Obsoleto
- sistema_campanas.py - Funcionalidad en admin
- setup_gamificacion_cursos.py - Usar crear_datos_gamificacion.py
- setup_solo_cafe.py - Obsoleto
- listar_todos_estudiantes_certificados.py - Usar admin
- consolidar_cursos.py - Una sola vez
- verificar_certificado_estudiante.py - Usar verificar_certificados.py
- verificar_contexto_curso.py - Debe ser un test unitario
- verificar_conversaciones.py - Debe ser un comando management
- verificar_plantillas.py - Debe ser un test
- verificar_preguntas_modulos.py - Debe ser un test
- verificar_videos_modulos.py - Debe ser un test
- demo_plantillas.py - Obsoleto
- diagnostico_rapido.py - Usar diagnostico_sistema.py
- auditoria_deployment.py - Usar check_production_readiness.py
- get_aws_info.py - Innecesario

## Beneficios de la Reorganización

1. **Claridad**: Fácil encontrar el script que necesitas
2. **Mantenibilidad**: Código organizado por función
3. **Escalabilidad**: Fácil agregar nuevos scripts
4. **Profesionalismo**: Estructura enterprise-grade
5. **Menos confusión**: No más 50+ archivos en la raíz

## Implementación

### Paso 1: Crear estructura
```bash
mkdir scripts\setup
mkdir scripts\maintenance
mkdir scripts\verification
mkdir scripts\utils
mkdir scripts\dev
mkdir docs
```

### Paso 2: Mover scripts (mantener solo los útiles)
```bash
# Scripts de setup
move crear_cursos_demo.py scripts\setup\
move crear_datos_gamificacion.py scripts\setup\
move crear_grupos_ejemplo.py scripts\setup\
move crear_temas_campana.py scripts\setup\
move load_demo_data.py scripts\setup\

# Scripts de mantenimiento
move backup_certificados.py scripts\maintenance\
move run_backup.py scripts\maintenance\
move compile_messages.py scripts\maintenance\
move cleanup_project.py scripts\maintenance\

# Scripts de verificación
move verificar_deployment.py scripts\verification\
move verificar_twilio.py scripts\verification\
move verificar_certificados.py scripts\verification\
move verificar_cursos.py scripts\verification\
move verificar_demo.py scripts\verification\
move diagnostico_sistema.py scripts\verification\
move check_production_readiness.py scripts\verification\

# Utilidades
move comprimir_videos.py scripts\utils\
move generar_secret_key.py scripts\utils\
move validar_telefonos.py scripts\utils\
move crear_plantilla.py scripts\utils\

# Dev/Testing
move test_sistema_completo.py scripts\dev\
move crear_conversacion_prueba.py scripts\dev\
move quick_verify.py scripts\dev\

# Docs
move CODE_CLEANUP_REPORT.md docs\
move DEPLOYMENT_GUIDE.md docs\
move RESUMEN_LIMPIEZA.md docs\
```

### Paso 3: Eliminar obsoletos
```bash
# Eliminar scripts que ya no se usan
del agregar_curso_cacao.py
del agregar_preguntas_modulos.py
del ajustar_emojis.py
del asociar_video.py
del crear_curso_platano.py
del crear_cursos_inicial.py
del generar_certificado_julian.py
del load_cafe_data.py
del reorganizar_preguntas.py
del resetear_estudiante.py
del resetear_estudiante_simple.py
del simplificar_mensajes.py
del sistema_campanas.py
del setup_gamificacion_cursos.py
del setup_solo_cafe.py
del listar_todos_estudiantes_certificados.py
del consolidar_cursos.py
del verificar_certificado_estudiante.py
del verificar_contexto_curso.py
del verificar_conversaciones.py
del verificar_plantillas.py
del verificar_preguntas_modulos.py
del verificar_videos_modulos.py
del demo_plantillas.py
del diagnostico_rapido.py
del auditoria_deployment.py
del get_aws_info.py
```

## Notas

- Los scripts de setup solo se ejecutan una vez en ambientes nuevos
- Los scripts de verificación se usan antes de deployments
- Los scripts de mantenimiento son para tareas periódicas
- Los scripts dev son para desarrollo local

## Próximo Paso

Después de reorganizar, actualizar el README.md con:
- Qué hace cada carpeta
- Cuándo usar cada script
- Ejemplos de uso
