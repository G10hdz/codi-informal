"""Confirmación de un solo uso para cobros. Vive en memoria: si el bot reinicia, se pide otra."""

import secrets
import threading
import time

VIGENCIA = 120


class Confirmaciones:
    def __init__(self, reloj=time.monotonic, vigencia: int = VIGENCIA):
        self._reloj = reloj
        self._vigencia = vigencia
        self._candado = threading.Lock()
        self._pendientes: dict[tuple, tuple] = {}

    def crear(self, dueno: str, chat: str, datos: dict) -> str:
        """Un borrador nuevo del mismo dueño y chat reemplaza (invalida) al anterior."""
        codigo = secrets.token_hex(3).upper()
        with self._candado:
            self._pendientes[(dueno, chat)] = (codigo, dict(datos), self._reloj() + self._vigencia)
        return codigo

    def consumir(self, dueno: str, chat: str, codigo: str, datos: dict | None = None):
        """Devuelve los datos del borrador y lo borra, o None. Atómico."""
        with self._candado:
            guardado = self._pendientes.get((dueno, chat))
            if guardado is None:
                return None
            esperado, original, vence = guardado
            if self._reloj() > vence:
                del self._pendientes[(dueno, chat)]
                return None
            if not secrets.compare_digest(esperado, (codigo or "").upper()):
                return None
            del self._pendientes[(dueno, chat)]
            if datos is not None and datos != original:
                return None
            return original
