import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database.db"

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dictamenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_matricula TEXT NOT NULL,
            direccion TEXT NOT NULL,
            barrio TEXT NOT NULL,
            estrato INTEGER NOT NULL,
            area REAL NOT NULL,
            estado TEXT NOT NULL,
            valor_consolidado INTEGER,
            fecha_creacion TEXT NOT NULL,
            sombra_9am_cargada INTEGER DEFAULT 0,
            sombra_3pm_cargada INTEGER DEFAULT 0,
            mapa_cargado INTEGER DEFAULT 0,
            pdf_path TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_db_connection():
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

# Inicializar base de datos
init_db()
