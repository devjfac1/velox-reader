# Epubeador Fast Read 🚀📖

Un lector de libros electrónicos (EPUB) moderno y ultrarrápido basado en la tecnología **RSVP** (Rapid Serial Visual Presentation). Diseñado para aumentar tu velocidad de lectura y comprensión eliminando los movimientos oculares sacádicos.

## ✨ Características Principales

- **Motor RSVP Fluido:** Lectura palabra por palabra con velocidad ajustable (100 - 1000 WPM).
- **Interfaz Moderna:** Diseño limpio con modo oscuro "Cyborg" (gracias a `ttkbootstrap`) para reducir la fatiga visual.
- **Biblioteca Integrada:** Gestión automática de libros recientes, progreso de lectura y metadatos.
- **Navegación Inteligente:** Detección de capítulos y saltos rápidos por página.
- **Persistencia:** Guarda tu progreso automáticamente (palabra y capítulo exacto) al cerrar.
- **Multiplataforma:** Funciona en Linux, Windows y macOS gracias a Python.

## 🛠️ Tecnologías

Este proyecto está construido con Python 3 y las siguientes librerías de código abierto:

*   **[ttkbootstrap](https://ttkbootstrap.readthedocs.io/):** Framework de UI moderno basado en Tkinter.
*   **[EbookLib](https://github.com/aerkalov/ebooklib):** Para análisis y extracción de contenido EPUB.
*   **[BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/):** Para limpieza y procesamiento de HTML.

## 📦 Instalación

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/devjfac1/epubeador-fast-read.git
    cd epubeador-fast-read
    ```

2.  **Instalar dependencias:**
    Se recomienda usar un entorno virtual:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

## 🚀 Uso

Puedes ejecutar la aplicación directamente usando el script auxiliar:

```bash
./run.sh
```

O manualmente desde Python:

```bash
python epub_rsvp_reader.py
```

1.  Haz clic en **"Añadir Libro"** o **"Escanear Carpeta"** para cargar tus EPUBs.
2.  Selecciona un libro de la lista.
3.  Ajusta la velocidad WPM (Words Per Minute) a tu gusto.
4.  ¡Presiona **Play** y empieza a leer!

## 📂 Estructura del Proyecto

*   `epub_rsvp_reader.py`: Código fuente principal.
*   `library.db`: Base de datos SQLite local (se genera automáticamente).
*   `samples/`: Libros de prueba de dominio público.
*   `requirements.txt`: Lista de dependencias.

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Si tienes ideas para mejorar la detección de capítulos, soportar PDF o mejorar la UI, no dudes en abrir un Issue o Pull Request.

## 📜 Licencia

Este proyecto es de código abierto.
