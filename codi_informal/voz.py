"""Nota de voz a texto. Descarga y transcripción son callables inyectados."""

import os
import re
import tempfile

MAX_BYTES = 5 * 1024 * 1024
MAX_SEGUNDOS = 60
TIMEOUT = 10
_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


def transcribir(audio_id, *, descargar, transcriptor, duracion=None):
    """Devuelve el texto o None. `descargar(audio_id, max_bytes=, timeout=) -> bytes`,
    `transcriptor(ruta) -> str`, `duracion(ruta) -> segundos` (opcional).
    Solo ids de medio del proveedor: nada de URLs del chat."""
    if transcriptor is None or not isinstance(audio_id, str) or not _ID.fullmatch(audio_id):
        return None
    ruta = None
    try:
        datos = descargar(audio_id, max_bytes=MAX_BYTES, timeout=TIMEOUT)
        if not datos or len(datos) > MAX_BYTES:
            return None
        fd, ruta = tempfile.mkstemp(suffix=".audio")
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
        if duracion is not None and duracion(ruta) > MAX_SEGUNDOS:
            return None
        texto = transcriptor(ruta)
    except Exception:
        return None
    finally:
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
    texto = " ".join(texto.split()) if isinstance(texto, str) else ""
    return texto or None
