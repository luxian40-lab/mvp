"""
🎨 Guía: Usar Diseños de Canva en Certificados EKI

MARCADORES RGB (plantilla imagen — obligatorio en prod)
=======================================================

En Canva/Photoshop coloca manchas de color PURO (relleno sólido, sin degradado):

  ⬜ GRIS     RGB (128, 128, 128)  → NOMBRE del estudiante
  🟥 ROJO     RGB (255,   0,   0)  → CÉDULA / documento
  🟨 AMARILLO RGB (255, 255,   0)  → FECHA de emisión (hoy; opcional)
  🟦 AZUL     RGB (0,     0, 255)  → CÓDIGO QR de verificación

Tamaños automáticos al generar:
  - Nombre ~56 px
  - Cédula ~30 px
  - Fecha  ~26 px
  - QR     130×130 px

Código: core/utils_certificados.py
Admin: Learning → Plantillas de certificado (caja verde de instrucciones + vista previa)


CÓMO FUNCIONA EL SISTEMA ACTUAL (Sin subir nada):
================================================

1. El sistema GENERA el PDF automáticamente cuando:
   - El estudiante completa un curso
   - Un admin genera el certificado manualmente

2. El PDF se crea con código Python (ReportLab) que:
   ✅ Dibuja el diseño desde cero
   ✅ Pone el nombre del estudiante
   ✅ Pone el nombre del curso
   ✅ Calcula y pone la calificación
   ✅ GENERA el código QR automáticamente
   ✅ Inserta el QR en el PDF (esquina inferior derecha)
   ✅ Guarda todo en un PDF
   ✅ Lo envía por WhatsApp

3. El QR contiene la URL de verificación:
   http://eki-prod-final.../verificar/ABC123XYZ


CÓMO USAR TUS DISEÑOS DE CANVA:
================================

OPCIÓN 1: Imagen de Fondo (Más Fácil) ⭐ RECOMENDADA
----------------------------------------------------

Paso 1: Diseña en Canva
┌─────────────────────────────────────────┐
│ [TU DISEÑO DE CANVA]                    │
│ - Logo EKI                               │
│ - Borde decorativo                       │
│ - Colores de marca                       │
│ - Elementos gráficos                     │
│                                          │
│ [Deja ESPACIO VACÍO + marcadores RGB]   │
│                                          │
└─────────────────────────────────────────┘

Paso 2: Descarga de Canva
- Formato: PNG (mejor para colores exactos de marcadores)
- Calidad: Alta (300 DPI)
- Tamaño: A4 Horizontal (297mm x 210mm)

Paso 3: Sube al Admin de Django
1. Ve a: Admin → Plantillas de certificado
2. Click en "Agregar Plantilla de Certificado"
3. Modo = Imagen; sube PNG con los 3–4 marcadores (amarillo = fecha opcional)
4. Usa la vista previa a la derecha (estudiante real o demo)
3. Sube tu PNG de Canva en "imagen_fondo"
4. Configura las posiciones del texto (X, Y):
   - nombre_x: 400 (centro horizontal)
   - nombre_y: 300 (posición del nombre)
   - curso_x: 400
   - curso_y: 250
   - etc.

Paso 4: El sistema hará esto automáticamente:
┌─────────────────────────────────────────┐
│ [FONDO DE CANVA]                        │
│   ↓ (se dibuja primero)                 │
│                                          │
│   [Nombre Dinámico] ← pone el sistema   │
│   [Curso Dinámico] ← pone el sistema    │
│   [Calificación] ← calcula el sistema   │
│                              [QR] ← auto │
│   Código: ABC123 ← auto                 │
└─────────────────────────────────────────┘

✅ RESULTADO: Tu diseño de Canva + datos dinámicos + QR automático


OPCIÓN 2: Modificar el Código (Más Control)
-------------------------------------------

Si quieres un control total, edita:
📁 core/generador_certificados.py

Puedes cambiar:
- Colores (líneas 40-43)
- Fuentes y tamaños
- Posiciones de elementos
- Agregar imágenes
- Mantener el QR (líneas 156-162)

Ejemplo de cambios simples:
```python
# Cambiar colores
color_primario = '#FF5733'  # Tu color de marca
color_secundario = '#3498DB'  # Color secundario

# Cambiar texto
texto_superior = "TU EMPRESA - Certificación Agrícola"
texto_certificado = "CERTIFICADO OFICIAL"

# Posiciones
c.drawCentredString(width/2, height - 4.2*inch, nombre)  # Ajustar Y
```


EJEMPLOS DE USO:
================

CASO 1: Quiero usar solo mi diseño de Canva
--------------------------------------------
1. Descarga tu diseño completo de Canva (PNG)
2. Subes como imagen de fondo
3. Configuras posiciones de texto
4. ✅ Listo - El sistema pone nombre, curso, QR encima

CASO 2: Quiero un certificado simple con QR
--------------------------------------------
✅ Ya está listo - Solo completa el curso
El sistema genera todo automáticamente


CASO 3: Quiero personalizar todo desde código
----------------------------------------------
1. Edita core/generador_certificados.py
2. Cambia colores, fuentes, posiciones
3. Mantén las líneas 156-162 (generación del QR)
4. Guarda y despliega


DIAGRAMA DEL FLUJO:
===================

[Estudiante completa curso]
           ↓
[Sistema detecta completado]
           ↓
[Calcula calificación automática]
           ↓
[Genera código único: ABC123XYZ]
           ↓
[Crea URL: eki.../verificar/ABC123XYZ]
           ↓
[Genera QR con esa URL] ← AQUÍ SE CREA EL QR
           ↓
[Crea PDF:]
  - Dibuja fondo (Canva o diseño por defecto)
  - Escribe nombre del estudiante
  - Escribe nombre del curso
  - Escribe calificación
  - Dibuja el QR en esquina inferior derecha
  - Escribe código de verificación
           ↓
[Guarda PDF en base de datos]
           ↓
[Envía por WhatsApp al estudiante]
           ↓
[Estudiante recibe:]
  📱 Mensaje con link al PDF
  📄 PDF con QR incluido
  🔗 Link de verificación
           ↓
[Cualquiera puede verificar:]
  Opción 1: Escanea el QR del PDF
  Opción 2: Visita eki.../verificar/ABC123XYZ
  Opción 3: Ingresa código ABC123XYZ manualmente


VERIFICACIÓN DEL CERTIFICADO:
==============================

Cuando alguien escanea el QR o visita el link:
1. Abre: http://eki-prod-final.../verificar/ABC123XYZ
2. El sistema busca el certificado en la base de datos
3. Muestra:
   ✅ Certificado válido
   👤 Nombre del estudiante
   📚 Curso completado
   📅 Fecha de emisión
   📊 Calificación
   🔐 Código de verificación


PARA PROBAR:
============

1. Ve al admin como admin/admin123
2. Ve a Estudiantes
3. Inscribe un estudiante en un curso
4. Marca todos los módulos como completados
5. El sistema automáticamente:
   ✅ Genera el certificado
   ✅ Crea el QR
   ✅ Guarda el PDF
   ✅ Lo envía por WhatsApp (si está configurado)

Luego puedes:
- Ver el PDF en admin → Certificados
- Descargar el PDF
- Verificar que el QR esté en la esquina
- Escanear el QR con tu celular
- Ver que abre la página de verificación


RESUMEN:
========

❌ NO subes un PDF - El sistema lo genera
✅ El QR se genera y dibuja automáticamente en el PDF
✅ El QR aparece en esquina inferior derecha del certificado
✅ El QR contiene la URL de verificación única
✅ Puedes usar tu diseño de Canva como fondo
✅ El sistema pone datos dinámicos encima del fondo

Todo es AUTOMÁTICO cuando el estudiante completa el curso.
