# 🚀 Eki Platform - Core System

Sistema de gestión y administración educativa basado en **Django**. Este núcleo centraliza la operación de envíos de logs, gestión de estudiantes y visualización de métricas clave.

## 📋 Características Principales

* **Dashboard de Métricas:** Visualización en tiempo real del estado de los envíos y logs del sistema.
* **Gestión de Logs:** Interfaz administrativa para el monitoreo de "Envío logs".
* **Arquitectura Escalable:** Base sólida en Django lista para integración con WhatsApp Cloud API.
* **Navegación Personalizada:** Acceso rápido a herramientas críticas desde el Navbar.

## 🛠️ Tecnologías

* **Backend:** Python / Django 4.x
* **Base de Datos:** PostgreSQL / SQLite (según entorno)
* **Frontend:** Django Templates + Bootstrap (Admin Interface)

## ⚙️ Instalación y Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    ```

2.  **Activar entorno virtual:**
    ```bash
    source venv/bin/activate  # En Mac/Linux
    # o
    venv\Scripts\activate     # En Windows
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar variables de entorno (.env):**
    ```bash
    cp .env.example .env  # en Windows puedes copiar manualmente
    ```
    Completa `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` y opcionalmente `WHATSAPP_API_VERSION` (por defecto v19.0).

5.  **Ejecutar migraciones:**
    ```bash
    python manage.py migrate
    ```

6.  **Iniciar el servidor:**
    ```bash
    python manage.py runserver
    ```

## 📊 Estado del Proyecto

Actualmente en fase de implementación del **Módulo de Métricas** e integración de conectores para WhatsApp.

---
Developed for **Eki** © 2025.