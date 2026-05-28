from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "pedidos.db")))

SQL_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS pedidos (
    id TEXT PRIMARY KEY,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    status TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT
)
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL;")
    connection.execute("PRAGMA synchronous=NORMAL;")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(SQL_CREATE_TABLE)
        connection.commit()


def save_pedido(payload: dict[str, Any], status: str = "processado") -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO pedidos (id, descricao, valor, status, processed_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                descricao = excluded.descricao,
                valor = excluded.valor,
                status = excluded.status,
                processed_at = excluded.processed_at
            """,
            (payload["id"], payload["descricao"], payload["valor"], status),
        )
        connection.commit()