"""Dedupe de mensajes y límites por dueño. Su propio sqlite, aparte del registro de pagos."""

import sqlite3
import threading
import time


class Limites:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._candado = threading.Lock()
        with self._candado:
            self._conn.execute("create table if not exists vistos (id text primary key, ts real)")
            self._conn.execute("create table if not exists eventos (dueno text, clave text, ts real)")
            self._conn.commit()

    def repetido(self, mensaje_id: str) -> bool:
        """True si el id ya se había visto; si no, lo guarda."""
        with self._candado:
            try:
                cur = self._conn.execute(
                    "insert or ignore into vistos (id, ts) values (?, ?)", (mensaje_id, time.time())
                )
                self._conn.commit()
            except Exception:
                # sin rollback el insert queda pendiente y el reintento se marca como visto
                self._conn.rollback()
                raise
            return cur.rowcount == 0

    def permitir(self, dueno: str, clave: str, tope: int, ventana: float = 60, ahora=None) -> bool:
        """Cuenta el evento y devuelve False si ya hay `tope` en la ventana."""
        ahora = time.time() if ahora is None else ahora
        with self._candado:
            self._conn.execute("delete from eventos where ts < ?", (ahora - ventana,))
            (n,) = self._conn.execute(
                "select count(*) from eventos where dueno = ? and clave = ?", (dueno, clave)
            ).fetchone()
            if n >= tope:
                self._conn.commit()
                return False
            self._conn.execute("insert into eventos values (?, ?, ?)", (dueno, clave, ahora))
            self._conn.commit()
            return True
