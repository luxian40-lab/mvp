# 🤖 Generación Automática de Ejercicios con IA

## 📋 Descripción

Sistema que **lee el contenido de un curso** y **genera ejercicios personalizados automáticamente** usando IA (GPT-4 o Claude).

### ✨ Características

✅ **Analiza el contenido del curso** (módulos, descripciones)  
✅ **Genera ejercicios contextualizados** al tema del curso  
✅ **Contexto rural colombiano** automático  
✅ **Números realistas** para Colombia  
✅ **Ejercicios numéricos y abiertos**  
✅ **Rúbricas automáticas** para ejercicios abiertos

---

## 🚀 Uso Básico

### 1. Generar ejercicios para un curso

```bash
# Generar 5 ejercicios mixtos (numéricos + abiertos)
python manage.py generar_ejercicios_ia --curso-id 1 --settings=mvp_project.settings_local

# Generar 10 ejercicios solo numéricos
python manage.py generar_ejercicios_ia --curso-id 1 --cantidad 10 --tipo numerico --settings=mvp_project.settings_local

# Generar 3 ejercicios abiertos con GPT-3.5
python manage.py generar_ejercicios_ia --curso-id 1 --cantidad 3 --tipo abierto --modelo gpt-3.5-turbo --settings=mvp_project.settings_local
```

### 2. Opciones disponibles

| Opción | Valores | Default | Descripción |
|--------|---------|---------|-------------|
| `--curso-id` | Número | *Requerido* | ID del curso |
| `--cantidad` | 1-20 | 5 | Cantidad de ejercicios |
| `--tipo` | numerico, abierto, mixto | mixto | Tipo de ejercicios |
| `--modelo` | gpt-4, gpt-3.5-turbo, claude-3-sonnet | gpt-4 | Modelo de IA |

---

## 📝 Ejemplos de Ejercicios Generados

### Ejemplo 1: Curso de Café

**Entrada:** Curso "Caficultura Sostenible" con módulos sobre siembra, cosecha, ventas

**Salida (Ejercicio Numérico):**
```
☕ **Venta de Café Pergamino**

Juan tiene una finca cafetera en Quindío. Esta cosecha vendió:
- 150 kilos de café pergamino a $11,500 el kilo

Sus costos fueron:
- Fertilizante: $450,000
- Recolección: $580,000
- Despulpado: $130,000

**Pregunta:** ¿Cuánta utilidad obtuvo Juan en esta cosecha?

💡 Fórmula: Utilidad = Ingresos - Costos
```

**Salida (Ejercicio Abierto):**
```
🌱 **Aplicación Práctica**

Explica cómo aplicarías los conceptos de manejo de costos de café 
en tu propia finca. Menciona al menos 3 estrategias específicas.

**Rúbrica:**
- Excelente (100): Menciona 3+ estrategias viables con detalles
- Bueno (80): Menciona 2-3 estrategias con algo de detalle
- Regular (60): Menciona estrategias generales sin mucho detalle
- Insuficiente (30): Respuesta muy vaga o irrelevante
```

### Ejemplo 2: Curso de Aguacate

**Entrada:** Curso "Producción de Aguacate" con módulos sobre cultivo, comercialización

**Ejercicio Generado:**
```
🥑 **Negocio de Aguacate**

María cosechó 200 aguacates Hass de su finca.
- Vendió 150 aguacates a $2,800 cada uno
- Los 50 restantes se dañaron

Sus costos totales fueron $280,000

**Pregunta:** ¿Cuál fue su utilidad final?
```

---

## 🔧 Configuración

### Variables de Entorno Necesarias

```bash
# Para usar GPT-4 o GPT-3.5
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx

# Para usar Claude (opcional)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

### Añadir en `.env`

```env
OPENAI_API_KEY=tu_clave_aqui
```

---

## 💡 Casos de Uso

### 1. **Cliente pide curso de Maíz**
```bash
# 1. Crear curso en admin con módulos sobre maíz
# 2. Generar ejercicios automáticamente
python manage.py generar_ejercicios_ia --curso-id 2 --cantidad 8 --settings=mvp_project.settings_local

# ✅ Ejercicios de maíz listos en 30 segundos
```

### 2. **Necesitas más ejercicios para un curso existente**
```bash
# Generar 5 ejercicios adicionales
python manage.py generar_ejercicios_ia --curso-id 1 --cantidad 5 --settings=mvp_project.settings_local

# ✅ Se añaden al curso sin duplicar
```

### 3. **Cliente quiere ejercicios solo de cálculo**
```bash
# Generar solo numéricos
python manage.py generar_ejercicios_ia --curso-id 1 --tipo numerico --cantidad 10 --settings=mvp_project.settings_local
```

---

## 📊 Ventajas vs Plantillas Manuales

| Característica | Plantillas Manuales | Generación IA |
|----------------|---------------------|---------------|
| Personalización | ❌ Fijas | ✅ Adaptadas al curso |
| Rapidez | ⏱️ Manual | ⚡ Automático (30s) |
| Variedad | ❌ 8 ejercicios | ✅ Ilimitados |
| Contexto | ⚠️ Genérico | ✅ Específico del tema |
| Escalabilidad | ❌ Requiere programación | ✅ Comando simple |

---

## 🔍 Cómo Funciona Internamente

1. **Lee el contenido del curso** (nombre, descripción, módulos)
2. **Construye un prompt especializado** para educación rural
3. **Envía a IA** (GPT-4 o Claude)
4. **Recibe ejercicios en JSON** estructurado
5. **Valida y guarda** en base de datos
6. **Crea rúbricas** automáticas para ejercicios abiertos

---

## 🎯 Comparación con Sistema Anterior

### Antes: Plantillas Manuales

```bash
# Solo 8 ejercicios predefinidos
python manage.py cargar_plantillas_financieras --curso-id 1

# ❌ Siempre los mismos ejercicios
# ❌ Solo temas financieros
# ❌ No se adapta al contenido del curso
```

### Ahora: Generación IA

```bash
# Ejercicios personalizados al curso
python manage.py generar_ejercicios_ia --curso-id 1 --cantidad 20

# ✅ Únicos cada vez
# ✅ Cualquier tema (café, aguacate, maíz, etc.)
# ✅ Lee y se adapta al contenido
```

---

## 📚 Archivos del Sistema

```
core/
├── generador_ejercicios_ia.py          # ✅ Lógica de generación
├── management/commands/
│   └── generar_ejercicios_ia.py        # ✅ Comando Django
└── plantillas_ejercicios.py            # (Antiguo sistema manual)
```

---

## 🧪 Testing

```bash
# 1. Verificar que funcione
python manage.py generar_ejercicios_ia --curso-id 1 --cantidad 2 --settings=mvp_project.settings_local

# 2. Ver ejercicios generados en admin Django
# http://127.0.0.1:8000/admin/core/ejerciciopractico/
```

---

## ⚠️ Limitaciones Actuales

1. **Requiere API key** de OpenAI (costo por uso)
2. **Curso debe tener módulos** con contenido
3. **Internet requerido** para llamadas a IA
4. **Latencia:** 10-30 segundos por generación

---

## 🔮 Mejoras Futuras

- [ ] Caché de ejercicios generados
- [ ] Soporte para Gemini (Google)
- [ ] Generación de imágenes/diagramas
- [ ] Validación automática de duplicados
- [ ] Historial de ejercicios generados

---

## 📞 Soporte

Si hay errores:

```bash
# Ver traceback completo
python manage.py generar_ejercicios_ia --curso-id 1 --traceback --settings=mvp_project.settings_local
```

**Errores comunes:**

| Error | Solución |
|-------|----------|
| `OPENAI_API_KEY no configurada` | Añadir en `.env` |
| `Curso no tiene módulos` | Crear módulos en admin |
| `API rate limit` | Esperar 1 minuto o usar gpt-3.5-turbo |

---

**Generado:** 5 de Febrero 2026  
**Por:** GitHub Copilot (Claude Sonnet 4.5)  
**Propósito:** Documentar sistema de generación automática de ejercicios con IA
