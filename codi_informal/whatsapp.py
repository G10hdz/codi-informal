"""WhatsApp Cloud API. El bot vive en el chat: texto, nota de voz y la imagen del QR."""

import hashlib
import hmac


def firma_valida(secreto: str, cuerpo: bytes, firma: str) -> bool:
    if not secreto or not firma.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma.removeprefix("sha256="))


def extraer(payload: dict) -> dict:
    vacio = {"tipo": "vacio", "texto": None, "de": None, "audio_id": None, "id": None, "grupo": False,
             "phone_number_id": None}
    if not isinstance(payload, dict):
        return vacio
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        texto = payload.get("texto") or payload.get("transcript")
        if texto:
            return {"tipo": "text", "texto": str(texto), "de": payload.get("de"), "audio_id": None,
                    "phone_number_id": None}
        return vacio
    metadata = value.get("metadata") or {}
    para = metadata.get("phone_number_id") if isinstance(metadata, dict) else None
    mensajes = value.get("messages") or []
    if not mensajes:
        return {"tipo": "status", "texto": None, "de": None, "audio_id": None,
                "phone_number_id": para}
    mensaje = mensajes[0]
    base = {"de": mensaje.get("from"), "id": mensaje.get("id"), "grupo": "group_id" in mensaje,
            "phone_number_id": para}
    if mensaje.get("type") == "text":
        cuerpo = (mensaje.get("text") or {}).get("body") or ""
        return {**base, "tipo": "text", "texto": cuerpo, "audio_id": None}
    if mensaje.get("type") == "audio":
        audio = mensaje.get("audio") or {}
        return {**base, "tipo": "audio", "texto": None, "audio_id": audio.get("id")}
    return {**base, "tipo": "otro", "texto": None, "audio_id": None}


def cuerpo_texto(destino: str, texto: str) -> dict:
    return {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "text",
        "text": {"body": texto},
    }


def cuerpo_imagen(destino: str, media_id: str) -> dict:
    return {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "image",
        "image": {"id": media_id},
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
