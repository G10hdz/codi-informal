"""OpenRouter para voz y tickets. Chat completions compatible con OpenAI, solo urllib.

Nada de lo que entra (audio, foto) ni lo que sale (transcripción, monto) se registra:
los errores devuelven None y ya."""

import base64
import json
import os
import urllib.request

URL = "https://openrouter.ai/api/v1/chat/completions"
MODELO = "google/gemini-2.5-flash-lite"
TIMEOUT = 20

_PEDIR_VOZ = (
    "Transcribe this voice note literally, in its original language. "
    "Reply with the transcript only."
)
_PEDIR_TICKET = (
    "Read the receipt in the image. Reply with JSON only: "
    '{"monto": "<total as printed>", "concepto": "<short concept>"}'
)

MAX_RESPUESTA = 1024 * 1024


def transcriptor(ruta) -> str | None:
    """Nota de voz ogg/opus a texto. None ante cualquier error."""
    try:
        with open(ruta, "rb") as f:
            audio = f.read()
        if not audio:
            return None
        contenido = [
            {"type": "text", "text": _PEDIR_VOZ},
            {"type": "input_audio", "input_audio": {
                "data": base64.b64encode(audio).decode(), "format": "ogg"}},
        ]
        texto = _completar(contenido)
    except Exception:
        return None
    if not texto:
        return None
    return " ".join(texto.split()) or None


def lector(imagen_bytes) -> dict | None:
    """Foto de ticket a {"monto", "concepto"}. Solo JSON estricto; None en lo demás."""
    if not imagen_bytes:
        return None
    try:
        url = "data:image/jpeg;base64," + base64.b64encode(imagen_bytes).decode()
        contenido = [
            {"type": "text", "text": _PEDIR_TICKET},
            {"type": "image_url", "image_url": {"url": url}},
        ]
        data = _json(_completar(contenido))
        if not isinstance(data, dict) or "monto" not in data or "concepto" not in data:
            return None
        # el modelo copia el total como viene impreso ("$0.01", "0.01 MXN"); ticket.leer valida el resto
        monto = str(data["monto"]).strip().removeprefix("$").removesuffix("MXN").strip()
        return {"monto": monto, "concepto": data["concepto"]}
    except Exception:
        return None


def _completar(contenido) -> str | None:
    llave = os.environ.get("OPENROUTER_API_KEY", "")
    if not llave:
        return None
    cuerpo = {
        "model": os.environ.get("OPENROUTER_MODEL") or MODELO,
        "messages": [{"role": "user", "content": contenido}],
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(cuerpo).encode(),
        headers={"Authorization": f"Bearer {llave}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as respuesta:
        crudo = respuesta.read(MAX_RESPUESTA + 1)
    if len(crudo) > MAX_RESPUESTA:
        return None
    data = json.loads(crudo or b"{}")
    try:
        texto = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if isinstance(texto, list):
        texto = "".join(p.get("text", "") for p in texto if isinstance(p, dict))
    return texto if isinstance(texto, str) and texto.strip() else None


def _json(texto) -> dict | None:
    if not isinstance(texto, str):
        return None
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        return None
