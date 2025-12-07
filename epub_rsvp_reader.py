#!/usr/bin/env python3
"""
Lector EPUB con tecnología RSVP (Rapid Serial Visual Presentation)
Aplicación completa con biblioteca personal y seguimiento de progreso
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import re
import threading
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sqlite3
from datetime import datetime

try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    import ttkbootstrap as tb
except ImportError as e:
    print("Faltan dependencias necesarias.")
    print(f"Error detallado: {e}")
    print("Por favor, instale las dependencias manualmente en su entorno virtual:")
    print("pip install ebooklib beautifulsoup4 ttkbootstrap")
    import sys
    sys.exit(1)

class BookDatabase:
    """Maneja la base de datos SQLite para almacenar información de libros y progreso"""
    
    def __init__(self, db_path: str = "library.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa la base de datos con las tablas necesarias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                file_path TEXT UNIQUE NOT NULL,
                total_words INTEGER DEFAULT 0,
                current_word INTEGER DEFAULT 0,
                reading_speed INTEGER DEFAULT 250,
                last_read TIMESTAMP,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                is_valid BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reading_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER,
                session_start TIMESTAMP,
                session_end TIMESTAMP,
                words_read INTEGER,
                average_speed INTEGER,
                FOREIGN KEY (book_id) REFERENCES books (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_book(self, title: str, author: str, file_path: str, total_words: int, file_size: int) -> int:
        """Añade un libro a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO books 
                (title, author, file_path, total_words, file_size, last_read)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, author, file_path, total_words, file_size, datetime.now().isoformat()))
            
            book_id = cursor.lastrowid
            conn.commit()
            return book_id
        except sqlite3.Error as e:
            print(f"Error añadiendo libro: {e}")
            return -1
        finally:
            conn.close()
    
    def get_all_books(self) -> List[Dict]:
        """Obtiene todos los libros de la biblioteca"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, title, author, file_path, total_words, current_word, 
                   reading_speed, last_read, file_size, is_valid
            FROM books 
            WHERE is_valid = 1
            ORDER BY last_read DESC
        ''')
        
        books = []
        for row in cursor.fetchall():
            progress = (row[5] / row[4] * 100) if row[4] > 0 else 0
            books.append({
                'id': row[0],
                'title': row[1],
                'author': row[2],
                'file_path': row[3],
                'total_words': row[4],
                'current_word': row[5],
                'reading_speed': row[6],
                'last_read': row[7],
                'file_size': row[8],
                'progress': progress
            })
        
        conn.close()
        return books
    
    def update_progress(self, book_id: int, current_word: int, reading_speed: int):
        """Actualiza el progreso de lectura de un libro"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE books 
            SET current_word = ?, reading_speed = ?, last_read = ?
            WHERE id = ?
        ''', (current_word, reading_speed, datetime.now().isoformat(), book_id))
        
        conn.commit()
        conn.close()
    
    def mark_invalid(self, file_path: str):
        """Marca un libro como inválido si el archivo no existe o está corrupto"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE books SET is_valid = 0 WHERE file_path = ?', (file_path,))
        conn.commit()
        conn.close()

class EPUBProcessor:
    """Procesa archivos EPUB y extrae el contenido de texto"""
    
    @staticmethod
    def extract_text_from_epub(file_path: str) -> Tuple[str, Dict]:
        """Extrae todo el texto de un archivo EPUB"""
        try:
            book = epub.read_epub(file_path)
            text_content = []
            metadata = {
                'title': 'Título desconocido',
                'author': 'Autor desconocido'
            }
            
            # Extraer metadatos
            if book.get_metadata('DC', 'title'):
                metadata['title'] = book.get_metadata('DC', 'title')[0][0]
            if book.get_metadata('DC', 'creator'):
                metadata['author'] = book.get_metadata('DC', 'creator')[0][0]
            
            # Extraer contenido de texto siguiendo el orden de lectura (spine)
            for item_id, _ in book.spine:
                item = book.get_item_with_id(item_id)
                if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
                    continue
                
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                # Remover scripts y estilos
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text()
                # Limpiar y normalizar el texto
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    text_content.append(text)
            
            full_text = ' '.join(text_content)
            return full_text, metadata
            
        except Exception as e:
            print(f"Error procesando EPUB {file_path}: {e}")
            return "", {"title": "Error", "author": "Error"}
    
    @staticmethod
    def count_words(text: str) -> int:
        """Cuenta las palabras en un texto conservando puntuación"""
        if not text:
            return 0
        return len(text.split())
    
    @staticmethod
    def get_words_list(text: str) -> List[str]:
        """Convierte el texto en una lista de palabras conservando puntuación"""
        if not text:
            return []
        return text.split()

    @staticmethod
    def _clean_title(raw: str) -> str:
        """Limpia título quitando extensión, guiones y recortando"""
        title = re.sub(r'[\-_]', ' ', raw)
        title = re.sub(r'\.(x?html)$', '', title, flags=re.I)
        title = title.strip()
        if len(title) > 80:
            title = title[:77] + '...'
        return title

    @staticmethod
    def extract_words_and_chapters(file_path: str) -> Tuple[List[str], List[Dict], Dict]:
        """Extrae palabras y capítulos de un EPUB y devuelve (words, chapters, metadata)."""
        try:
            book = epub.read_epub(file_path)
            words: List[str] = []
            chapters: List[Dict] = []
            start_idx = 0
            metadata = {
                'title': 'Título desconocido',
                'author': 'Autor desconocido'
            }
            if book.get_metadata('DC', 'title'):
                metadata['title'] = book.get_metadata('DC', 'title')[0][0]
            if book.get_metadata('DC', 'creator'):
                metadata['author'] = book.get_metadata('DC', 'creator')[0][0]

            # Iterar usando el spine para orden correcto
            for item_id, _ in book.spine:
                item = book.get_item_with_id(item_id)
                if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
                    continue

                soup = BeautifulSoup(item.get_content(), 'html.parser')
                for tag in soup(['script', 'style']):
                    tag.decompose()
                
                text = soup.get_text()
                text = re.sub(r'\s+', ' ', text).strip()
                if not text:
                    continue
                
                # Usar split() para conservar puntuación (vital para RSVP)
                item_words = text.split()
                if not item_words:
                    continue

                # Mejor heurística para títulos
                title = None
                # 1. Buscar encabezados reales (h1, h2, h3)
                headings = soup.find_all(re.compile('^h[1-3]$'))
                for h in headings:
                    h_text = h.get_text(strip=True)
                    if h_text and len(h_text) < 100: # Evitar parrafos accidentalmente marcados como h
                        title = EPUBProcessor._clean_title(h_text)
                        break
                
                # 2. Fallback a title tag
                if not title:
                    head_title = soup.find('title')
                    if head_title and head_title.get_text(strip=True):
                        title = EPUBProcessor._clean_title(head_title.get_text(strip=True))
                
                # 3. Fallback a nombre de archivo (limpiado)
                if not title:
                     raw_name = item.get_name().split('/')[-1]
                     # Evitar nombres técnicos feos como 'part0004.html' si es posible, o dejarlos como último recurso
                     title = EPUBProcessor._clean_title(raw_name)

                # Filtrar títulos duplicados o redundantes
                lower_title = title.lower()
                
                # Ignorar si es igual al título del libro (común en portada)
                if lower_title == metadata['title'].lower():
                    # Si es el primer capítulo y no tiene un título distinto, lo llamamos "Inicio" o "Cubierta"
                    if not chapters:
                        title = "Inicio"
                    else:
                        pass # Mantenemos el título aunque sea igual, a veces es "Capítulo 1" vs "Capítulo 1" del libro
                
                # Evitar duplicados consecutivos exactos
                if chapters and lower_title == chapters[-1]['title'].lower():
                    # Si es el mismo título, asumimos que es continuación del capítulo anterior
                    words.extend(item_words)
                    start_idx += len(item_words)
                    continue

                chapters.append({'title': title, 'start': start_idx})
                words.extend(item_words)
                start_idx += len(item_words)
            
            return words, chapters, metadata
        except Exception as e:
            print(f"Error procesando EPUB {file_path}: {e}")
            return [], [], {'title': 'Error', 'author': 'Error'}

class RSVPReader:
    """Lector RSVP (Rapid Serial Visual Presentation)"""
    
    def __init__(self, parent_frame, on_progress_update=None):
        self.parent_frame = parent_frame
        self.on_progress_update = on_progress_update
        self.words = []
        self.current_word_index = 0
        self.reading_speed = 250  # palabras por minuto
        self.is_reading = False
        self.reading_thread = None
        self.chapters = []
        self.words_per_page = 300
        self.page_count = 0
        # Último índice guardado en BD
        self.last_saved_index = -1
        
        self.setup_ui()
    
    def setup_ui(self):
        """Configura la interfaz del lector RSVP"""
        # Frame principal del lector
        self.reader_frame = ttk.Frame(self.parent_frame)
        self.reader_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Área de visualización de palabras
        self.word_display_frame = ttk.Frame(self.reader_frame)
        self.word_display_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Estilo visual tipo Spritz: Alto contraste, Dark Mode
        self.word_label = tk.Label(
            self.word_display_frame,
            text="Selecciona un libro",
            font=("Roboto", 32, "bold"), # Tipografía moderna y grande
            bg="#212529", # Fondo oscuro (coincide con tema Cyborg)
            fg="#f8f9fa", # Texto claro
            relief=tk.FLAT,
            bd=0,
            height=3
        )
        self.word_label.pack(fill=tk.BOTH, expand=True)
        
        # Selección de capítulos
        chapter_frame = ttk.Frame(self.reader_frame)
        chapter_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(chapter_frame, text="Capítulo:").pack(side=tk.LEFT)
        self.chapter_var = tk.StringVar()
        self.chapter_combo = ttk.Combobox(chapter_frame, textvariable=self.chapter_var, state='readonly')
        self.chapter_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(chapter_frame, text="Ir", command=self.jump_to_selected_chapter).pack(side=tk.LEFT, padx=5)

        # Navegación por páginas
        page_frame = ttk.Frame(self.reader_frame)
        page_frame.pack(fill=tk.X, pady=5)
        ttk.Label(page_frame, text="Página:").pack(side=tk.LEFT)
        self.page_var = tk.IntVar(value=1)
        self.page_spin = ttk.Spinbox(page_frame, from_=1, to=1, textvariable=self.page_var, width=6)
        self.page_spin.pack(side=tk.LEFT, padx=5)
        ttk.Button(page_frame, text="Ir", command=self.jump_to_page).pack(side=tk.LEFT, padx=5)
        
        # Controles de reproducción
        controls_frame = ttk.Frame(self.reader_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        self.play_button = ttk.Button(controls_frame, text="▶ Reproducir", command=self.toggle_reading)
        self.play_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(controls_frame, text="⏹ Parar", command=self.stop_reading)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.reset_button = ttk.Button(controls_frame, text="⏮ Reiniciar", command=self.reset_reading)
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
        # Control de velocidad
        speed_frame = ttk.Frame(self.reader_frame)
        speed_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(speed_frame, text="Velocidad (palabras/min):").pack(side=tk.LEFT)
        
        self.speed_var = tk.IntVar(value=self.reading_speed)
        self.speed_scale = ttk.Scale(
            speed_frame,
            from_=100,
            to=500,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=self.update_speed
        )
        self.speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.speed_label = ttk.Label(speed_frame, text=f"{self.reading_speed}")
        self.speed_label.pack(side=tk.RIGHT)
        
        # Barra de progreso
        progress_frame = ttk.Frame(self.reader_frame)
        progress_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(progress_frame, text="Progreso:").pack(side=tk.LEFT)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.pack(side=tk.RIGHT)
    
    def load_text(self, words: List[str], current_position: int = 0):
        """Carga el texto para la lectura RSVP"""
        self.words = words
        self.current_word_index = current_position
        self.set_page_count(len(self.words))
        self.page_var.set(self.current_word_index // self.words_per_page + 1)
        self.update_display()
        self.update_progress()
    
    def update_speed(self, value):
        """Actualiza la velocidad de lectura"""
        self.reading_speed = int(float(value))
        self.speed_label.config(text=f"{self.reading_speed}")
    
    def toggle_reading(self):
        """Inicia o pausa la lectura"""
        if self.is_reading:
            self.pause_reading()
        else:
            self.start_reading()
    
    def start_reading(self):
        """Inicia la lectura RSVP"""
        if not self.words or self.current_word_index >= len(self.words):
            return
        
        self.is_reading = True
        self.play_button.config(text="⏸ Pausar")
        
        self.reading_thread = threading.Thread(target=self._reading_loop)
        self.reading_thread.daemon = True
        self.reading_thread.start()
    
    def pause_reading(self):
        """Pausa la lectura y persiste progreso"""
        self.is_reading = False
        self.play_button.config(text="▶ Reproducir")
        if self.on_progress_update:
            self.on_progress_update(self.current_word_index, self.reading_speed)
            self.last_saved_index = self.current_word_index
    
    def stop_reading(self):
        """Detiene la lectura completamente y guarda progreso"""
        self.is_reading = False
        self.play_button.config(text="▶ Reproducir")
        if self.on_progress_update:
            self.on_progress_update(self.current_word_index, self.reading_speed)
            self.last_saved_index = self.current_word_index
    
    def reset_reading(self):
        """Reinicia la lectura desde el principio"""
        self.stop_reading()
        self.current_word_index = 0
        self.update_display()
        self.update_progress()
    
    def _reading_loop(self):
        """Bucle principal de lectura RSVP"""
        while self.is_reading and self.current_word_index < len(self.words):
            word = self.words[self.current_word_index]
            
            # Actualizar la interfaz en el hilo principal
            self.word_label.after(0, lambda w=word: self.word_label.config(text=w))
            self.current_word_index += 1
            
            # Actualizar progreso
            self.word_label.after(0, self.update_progress)
            
            # Calcular el tiempo de espera basado en la velocidad
            delay = 60.0 / self.reading_speed  # segundos por palabra
            time.sleep(delay)
        
        # Lectura completada
        if self.current_word_index >= len(self.words):
            self.word_label.after(0, lambda: self.word_label.config(text="¡Lectura completada!"))
        
        self.word_label.after(0, lambda: self.play_button.config(text="▶ Reproducir"))
        self.is_reading = False
    
    def update_display(self):
        """Actualiza la palabra mostrada actualmente"""
        if self.words and self.current_word_index < len(self.words):
            self.word_label.config(text=self.words[self.current_word_index])
        elif self.current_word_index >= len(self.words):
            self.word_label.config(text="¡Lectura completada!")
        else:
            self.word_label.config(text="Selecciona un libro para comenzar")
    
    def update_progress(self):
        """Actualiza la barra de progreso"""
        if self.words:
            progress = (self.current_word_index / len(self.words)) * 100
            self.progress_var.set(progress)
            self.progress_label.config(text=f"{progress:.1f}%")
            # Actualizar número de página en el spinbox
            if hasattr(self, 'page_var'):
                self.page_var.set(self.current_word_index // self.words_per_page + 1)
            
            # Guardar progreso cada 5 palabras o al finalizar
            if self.on_progress_update and (
                self.current_word_index - self.last_saved_index >= 5 or self.current_word_index >= len(self.words) - 1
            ):
                self.on_progress_update(self.current_word_index, self.reading_speed)
                self.last_saved_index = self.current_word_index
        else:
            self.progress_var.set(0)
            self.progress_label.config(text="0%")

    # ------------------- Navegación de capítulos -------------------
    def set_chapters(self, chapters: List[Dict]):
        """Recibe lista de capítulos y llena el combobox"""
        self.chapters = chapters or []
        titles = [c['title'] for c in self.chapters]
        self.chapter_combo['values'] = titles
        # Ajustar ancho del combobox al título más largo (mín 30)
        max_len = max((len(t) for t in titles), default=30)
        self.chapter_combo.config(width=max(30, min(max_len, 60)))
        if titles:
            self.chapter_combo.current(0)

    def jump_to_selected_chapter(self):
        """Salta al capítulo seleccionado"""
        if not self.chapters:
            return
        idx = self.chapter_combo.current()
        if 0 <= idx < len(self.chapters):
            self.pause_reading()
            self.current_word_index = self.chapters[idx]['start']
            self.page_var.set(self.current_word_index // self.words_per_page + 1)
            self.update_display()
            self.update_progress()

    # ------------------- Navegación por páginas -------------------
    def set_page_count(self, total_words: int):
        """Calcula número de páginas y actualiza spinbox"""
        self.page_count = max(1, math.ceil(total_words / self.words_per_page))
        self.page_spin.config(to=self.page_count)

    def jump_to_page(self):
        """Salta a la página especificada en el spinbox"""
        try:
            page = int(self.page_var.get())
        except Exception:
            return
        if page < 1 or page > self.page_count:
            return
        self.pause_reading()
        self.current_word_index = (page - 1) * self.words_per_page
        if self.current_word_index >= len(self.words):
            self.current_word_index = len(self.words) - 1
        self.update_display()
        self.update_progress()

    # ------------------- Salto a palabra -------------------
    def jump_to_word(self, word_idx: int):
        """Salta al índice de palabra especificado y actualiza la interfaz"""
        if not self.words or word_idx < 0 or word_idx >= len(self.words):
            return
        self.pause_reading()
        self.current_word_index = word_idx
        # Sincronizar página y capítulo si corresponde
        if hasattr(self, 'page_var'):
            self.page_var.set(self.current_word_index // self.words_per_page + 1)
        self.update_display()
        self.update_progress()

class LibraryBrowser:
    """Navegador de biblioteca de libros"""
    
    def __init__(self, parent_frame, on_book_select=None):
        self.parent_frame = parent_frame
        self.on_book_select = on_book_select
        self.books_data = []
        
        self.setup_ui()
    
    def setup_ui(self):
        """Configura la interfaz del navegador de biblioteca"""
        # Frame principal
        main_frame = ttk.Frame(self.parent_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Título
        title_label = ttk.Label(main_frame, text="Biblioteca Personal", font=("Arial", 16, "bold"))
        title_label.pack(pady=5)
        
        # Botones de acción
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(buttons_frame, text="Escanear Carpeta", command=self.scan_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Añadir Libro", command=self.add_book_manually).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Actualizar", command=self.refresh_library).pack(side=tk.LEFT, padx=5)
        
        # Treeview para mostrar libros
        columns = ('Título', 'Autor', 'Progreso', 'Última lectura')
        self.tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        
        # Configurar columnas
        self.tree.heading('Título', text='Título')
        self.tree.heading('Autor', text='Autor')
        self.tree.heading('Progreso', text='Progreso')
        self.tree.heading('Última lectura', text='Última lectura')
        
        self.tree.column('Título', width=300)
        self.tree.column('Autor', width=200)
        self.tree.column('Progreso', width=100)
        self.tree.column('Última lectura', width=150)
        
        # Scrollbar para el treeview
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Empaquetar treeview y scrollbar
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind para selección de libro
        self.tree.bind('<Double-1>', self.on_tree_select)
    
    def load_books(self, books_data: List[Dict]):
        """Carga los libros en el treeview"""
        self.books_data = books_data
        
        # Limpiar treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Añadir libros
        for book in books_data:
            last_read = book.get('last_read', 'Nunca')
            if last_read and last_read != 'Nunca':
                try:
                    # Formatear fecha
                    dt = datetime.fromisoformat(last_read)
                    last_read = dt.strftime("%d/%m/%Y")
                except:
                    pass
            
            self.tree.insert('', tk.END, values=(
                book['title'][:50] + ('...' if len(book['title']) > 50 else ''),
                book['author'][:30] + ('...' if len(book['author']) > 30 else ''),
                f"{book['progress']:.1f}%",
                last_read
            ))
    
    def on_tree_select(self, event):
        """Maneja la selección de un libro"""
        selection = self.tree.selection()
        if selection and self.on_book_select:
            item = self.tree.item(selection[0])
            book_title = item['values'][0].replace('...', '')
            
            # Buscar el libro completo en books_data
            selected_book = None
            for book in self.books_data:
                if book['title'].startswith(book_title):
                    selected_book = book
                    break
            
            if selected_book:
                self.on_book_select(selected_book)
    
    def scan_folder(self):
        """Escanea una carpeta en busca de archivos EPUB"""
        folder_path = filedialog.askdirectory(title="Seleccionar carpeta con archivos EPUB")
        if folder_path and self.on_book_select:
            # Crear evento personalizado para escanear carpeta
            self.on_book_select({'action': 'scan_folder', 'path': folder_path})
    
    def add_book_manually(self):
        """Permite añadir un libro manualmente"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo EPUB",
            filetypes=[("Archivos EPUB", "*.epub"), ("Todos los archivos", "*.*")]
        )
        if file_path and self.on_book_select:
            self.on_book_select({'action': 'add_book', 'path': file_path})
    
    def refresh_library(self):
        """Actualiza la biblioteca"""
        if self.on_book_select:
            self.on_book_select({'action': 'refresh'})

    

    

class EPUBReaderApp:
    """Aplicación principal del lector EPUB con RSVP"""
    
    def __init__(self):
        # Inicializar ventana con tema moderno oscuro "cyborg"
        self.root = tb.Window(themename="cyborg")
        self.root.title("Lector EPUB con RSVP")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Base de datos
        self.db = BookDatabase()
        
        # Variables de estado
        self.current_book = None
        self.current_text = ""
        self.current_words = []
        
        self.setup_ui()
        self.load_library()
    
    def setup_ui(self):
        """Configura la interfaz principal"""
        # Notebook para pestañas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Pestaña de biblioteca
        self.library_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.library_frame, text="Biblioteca")
        
        # Pestaña de lectura
        self.reading_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.reading_frame, text="Lector RSVP")
        
        
        # Configurar navegador de biblioteca
        self.library_browser = LibraryBrowser(self.library_frame, self.on_book_action)
        
        # Configurar lector RSVP
        self.rsvp_reader = RSVPReader(self.reading_frame, self.on_progress_update)

        
        
        # Barra de estado
        self.status_bar = ttk.Label(self.root, text="Listo", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def on_book_action(self, action_data):
        """Maneja las acciones relacionadas con libros"""
        if isinstance(action_data, dict) and 'action' in action_data:
            if action_data['action'] == 'scan_folder':
                self.scan_epub_folder(action_data['path'])
            elif action_data['action'] == 'add_book':
                self.add_single_book(action_data['path'])
            elif action_data['action'] == 'refresh':
                self.load_library()
        else:
            # Selección de libro
            self.load_book_for_reading(action_data)
    
    def scan_epub_folder(self, folder_path: str):
        """Escanea una carpeta en busca de archivos EPUB"""
        self.status_bar.config(text="Escaneando carpeta...")
        self.root.update()
        
        epub_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.epub'):
                    epub_files.append(os.path.join(root, file))
        
        if not epub_files:
            messagebox.showinfo("Información", "No se encontraron archivos EPUB en la carpeta seleccionada.")
            self.status_bar.config(text="Listo")
            return
        
        # Procesar archivos encontrados
        added_count = 0
        for file_path in epub_files:
            if self.process_epub_file(file_path):
                added_count += 1
        
        messagebox.showinfo("Completado", f"Se añadieron {added_count} libros de {len(epub_files)} archivos procesados.")
        self.load_library()
        self.status_bar.config(text="Listo")
    
    def add_single_book(self, file_path: str):
        """Añade un solo libro a la biblioteca"""
        self.status_bar.config(text="Procesando libro...")
        self.root.update()
        
        if self.process_epub_file(file_path):
            messagebox.showinfo("Éxito", "Libro añadido correctamente a la biblioteca.")
            self.load_library()
        else:
            messagebox.showerror("Error", "No se pudo procesar el archivo EPUB.")
        
        self.status_bar.config(text="Listo")
    
    def process_epub_file(self, file_path: str) -> bool:
        """Procesa un archivo EPUB y lo añade a la base de datos"""
        try:
            # Verificar que el archivo existe
            if not os.path.exists(file_path):
                return False
            
            # Extraer texto y metadatos
            text, metadata = EPUBProcessor.extract_text_from_epub(file_path)
            
            if not text.strip():
                print(f"Archivo EPUB vacío o corrupto: {file_path}")
                return False
            
            # Contar palabras
            word_count = EPUBProcessor.count_words(text)
            file_size = os.path.getsize(file_path)
            
            # Añadir a la base de datos
            book_id = self.db.add_book(
                metadata['title'],
                metadata['author'],
                file_path,
                word_count,
                file_size
            )
            
            return book_id > 0
            
        except Exception as e:
            print(f"Error procesando {file_path}: {e}")
            return False
    
    def load_library(self):
        """Carga la biblioteca desde la base de datos"""
        books = self.db.get_all_books()
        
        # Verificar que los archivos aún existen
        valid_books = []
        for book in books:
            if os.path.exists(book['file_path']):
                valid_books.append(book)
            else:
                # Marcar como inválido en la base de datos
                self.db.mark_invalid(book['file_path'])
        
        self.library_browser.load_books(valid_books)
        self.status_bar.config(text=f"Biblioteca cargada: {len(valid_books)} libros")
    
    def load_book_for_reading(self, book_data: Dict):
        """Carga un libro para lectura RSVP"""
        self.status_bar.config(text="Cargando libro...")
        self.root.update()
        
        try:
            # Extraer palabras y capítulos del libro
            words, chapters, metadata = EPUBProcessor.extract_words_and_chapters(book_data['file_path'])

            # Configurar lector RSVP y vista de texto
            self.current_book = book_data
            self.current_words = words
            self.rsvp_reader.set_chapters(chapters)
            self.rsvp_reader.load_text(words, book_data.get('current_word', 0))
            self.rsvp_reader.reading_speed = book_data.get('reading_speed', 250)
            self.rsvp_reader.speed_var.set(self.rsvp_reader.reading_speed)

            # Cambiar a pestaña de lectura RSVP
            self.notebook.select(self.reading_frame)

            if not words:
                messagebox.showerror("Error", "No se pudo cargar el contenido del libro.")
                return
            self.status_bar.config(text=f"Libro cargado: {metadata['title']}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando el libro: {e}")
            self.status_bar.config(text="Error")
    
    # Código residual eliminado

    def on_progress_update(self, current_word: int, reading_speed: int):
        """Actualiza el progreso de lectura en la base de datos"""
        if self.current_book:
            self.db.update_progress(self.current_book['id'], current_word, reading_speed)
    
    def run(self):
        """Inicia la aplicación"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Maneja el cierre de la aplicación"""
        # Parar cualquier lectura en curso
        if hasattr(self, 'rsvp_reader'):
            self.rsvp_reader.stop_reading()
        
        self.root.destroy()

def main():
    """Función principal"""
    try:
        app = EPUBReaderApp()
        app.run()
    except Exception as e:
        print(f"Error iniciando la aplicación: {e}")
        messagebox.showerror("Error Fatal", f"No se pudo iniciar la aplicación:\n{e}")

if __name__ == "__main__":
    main()