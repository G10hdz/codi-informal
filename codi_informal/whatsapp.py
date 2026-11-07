"""WhatsApp Cloud API. El bot vive en el chat: texto, nota de voz y la imagen del QR."""


def extraer(payload: dict) -> dict:
    vacio = {"tipo": "vacio", "texto": None, "de": None, "audio_id": None}
    if not isinstance(payload, dict):
        return vacio
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        texto = payload.get("texto") or payload.get("transcript")
        if texto:
            return {"tipo": "text", "texto": str(texto), "de": payload.get("de"), "audio_id": None}
        return vacio
    mensajes = value.get("messages") or []
    if not mensajes:
        return {"tipo": "status", "texto": None, "de": None, "audio_id": None}
    mensaje = mensajes[0]
    de = mensaje.get("from")
    if mensaje.get("type") == "text":
        cuerpo = (mensaje.get("text") or {}).get("body") or ""
        return {"tipo": "text", "texto": cuerpo, "de": de, "audio_id": None}
    if mensaje.get("type") == "audio":
        audio = mensaje.get("audio") or {}
        return {"tipo": "audio", "texto": None, "de": de, "audio_id": audio.get("id")}
    return {"tipo": "otro", "texto": None, "de": de, "audio_id": None}


def cuerpo_texto(destino: str, texto: str) -> dict:
    return {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "text",
        "text": {"body": texto},
    }


def multipart_imagen(png: bytes) -> tuple[bytes, str]:
    limite = "----codiinformal"
    partes = [
        (
            f"--{limite}\r\n"
            'Content-Disposition: form-data; name="messaging_product"\r\n\r\n'
            "whatsapp\r\n"
        ).encode(),
        (
            f"--{limite}\r\n"
            'Content-Disposition: form-data; name="file"; filename="qr.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + png
        + b"\r\n",
        f"--{limite}--\r\n".encode(),
    ]
    return b"".join(partes), f"multipart/form-data; boundary={limite}"
