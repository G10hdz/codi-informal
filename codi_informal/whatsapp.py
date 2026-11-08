"""WhatsApp Cloud API. El bot vive en el chat: texto, nota de voz y la imagen del QR."""

import hashlib
import hmac
import json
import re
import urllib.request
from urllib.parse import urlparse

_GRAPH = "https://graph.facebook.com/v21.0"
KAPSO_API = "https://api.kapso.ai/meta/whatsapp/v24.0"
_MEDIA_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
# solo hosts de Meta: la url firmada del medio sale de la Graph API, nunca del chat (G07)
_HOSTS_META = ("fbsbx.com", "whatsapp.net", "whatsapp.com", "facebook.com", "fbcdn.net")
# con Kapso el medio se baja del proxy de Kapso, mismo criterio (G07)
HOSTS_KAPSO = ("kapso.ai",)
_FIRMA_KAPSO = re.compile(r"[0-9a-fA-F]{64}")


def firma_valida(secreto: str, cuerpo: bytes, firma: str) -> bool:
    if not secreto or not firma.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma.removeprefix("sha256="))


def firma_kapso_valida(secreto: str, cuerpo: bytes, firma: str) -> bool:
    """Kapso firma el cuerpo crudo con HMAC-SHA256 en hex, sin prefijo."""
    if not secreto or not _FIRMA_KAPSO.fullmatch(firma or ""):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma)


def descargar_media(media_id, credencial, *, max_bytes, timeout,
                    api=None, auth=None, hosts=None):
    """Bytes del medio o None. Primero pide la url firmada a la API del proveedor y
    luego baja el archivo, sin pasar de max_bytes. Solo ids de medio del proveedor (G07)."""
    if (not credencial or not isinstance(media_id, str) or not _MEDIA_ID.fullmatch(media_id)
            or not isinstance(max_bytes, int) or max_bytes <= 0):
        return None
    api = api or _GRAPH
    auth = auth if auth is not None else {"Authorization": f"Bearer {credencial}"}
    hosts = hosts or _HOSTS_META
    try:
        req = urllib.request.Request(f"{api}/{media_id}", headers=auth)
        with _abrir(req, timeout) as r:
            meta = json.loads(r.read(65537) or b"{}")
        if not _url_permitida(meta.get("url"), hosts):
            return None
        req = urllib.request.Request(meta["url"], headers=auth)
        with _abrir(req, timeout) as r:
            try:
                if int(r.headers.get("Content-Length") or 0) > max_bytes:
                    return None
            except (TypeError, ValueError):
                pass
            datos = r.read(max_bytes + 1)
    except Exception:
        return None
    if not datos or len(datos) > max_bytes:
        return None
    return datos


def _url_permitida(url, hosts) -> bool:
    if not isinstance(url, str):
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not host:
        return False
    return any(host == h or host.endswith("." + h) for h in hosts)


class _SinRedirects(urllib.request.HTTPRedirectHandler):
    """Un redirect de la url firmada es rechazo: no se siguen a otros hosts (G07)."""

    def redirect_request(self, *args, **kwargs):
        return None


def _abrir(req, timeout):
    return urllib.request.build_opener(_SinRedirects).open(req, timeout=timeout)


def extraer(payload: dict) -> dict:
    vacio = {"tipo": "vacio", "texto": None, "de": None, "audio_id": None, "imagen_id": None,
             "id": None, "grupo": False, "phone_number_id": None}
    if not isinstance(payload, dict):
        return vacio
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        texto = payload.get("texto") or payload.get("transcript")
        if texto:
            return {"tipo": "text", "texto": str(texto), "de": payload.get("de"), "audio_id": None,
                    "imagen_id": None, "phone_number_id": None}
        return vacio
    metadata = value.get("metadata") or {}
    para = metadata.get("phone_number_id") if isinstance(metadata, dict) else None
    mensajes = value.get("messages") or []
    if not mensajes:
        return {"tipo": "status", "texto": None, "de": None, "audio_id": None, "imagen_id": None,
                "phone_number_id": para}
    mensaje = mensajes[0]
    base = {"de": mensaje.get("from"), "id": mensaje.get("id"), "grupo": "group_id" in mensaje,
            "phone_number_id": para}
    if mensaje.get("type") == "text":
        cuerpo = (mensaje.get("text") or {}).get("body") or ""
        return {**base, "tipo": "text", "texto": cuerpo, "audio_id": None, "imagen_id": None}
    if mensaje.get("type") == "audio":
        audio = mensaje.get("audio") or {}
        return {**base, "tipo": "audio", "texto": None, "audio_id": audio.get("id"),
                "imagen_id": None}
    if mensaje.get("type") == "image":
        imagen = mensaje.get("image") or {}
        return {**base, "tipo": "image", "texto": None, "audio_id": None,
                "imagen_id": imagen.get("id")}
    return {**base, "tipo": "otro", "texto": None, "audio_id": None, "imagen_id": None}


def extraer_kapso(payload: dict) -> dict:
    """Webhook de Kapso (v2): `message` con campos de la Cloud API y bloque `kapso`.
    Solo cuentan los entrantes (direction inbound); lo pasivo y los ecos quedan fuera."""
    vacio = {"tipo": "vacio", "texto": None, "de": None, "audio_id": None, "imagen_id": None,
             "id": None, "grupo": False, "phone_number_id": None}
    if not isinstance(payload, dict):
        return vacio
    mensaje = payload.get("message")
    if not isinstance(mensaje, dict):
        return vacio
    kapso = mensaje.get("kapso")
    if (not isinstance(kapso, dict) or kapso.get("direction") != "inbound"
            or kapso.get("passive")):
        return vacio
    de = mensaje.get("from")
    if not de:
        conversacion = payload.get("conversation")
        if isinstance(conversacion, dict):
            de = conversacion.get("phone_number")
    base = {"de": de, "id": mensaje.get("id"), "grupo": "group_id" in mensaje,
            "phone_number_id": payload.get("phone_number_id")}
    tipo = mensaje.get("type")
    if tipo == "text":
        cuerpo = (mensaje.get("text") or {}).get("body") or ""
        return {**base, "tipo": "text", "texto": cuerpo, "audio_id": None, "imagen_id": None}
    if tipo == "audio":
        audio = mensaje.get("audio") or {}
        return {**base, "tipo": "audio", "texto": None, "audio_id": audio.get("id"),
                "imagen_id": None}
    if tipo == "image":
        imagen = mensaje.get("image") or {}
        return {**base, "tipo": "image", "texto": None, "audio_id": None,
                "imagen_id": imagen.get("id")}
    return {**base, "tipo": "otro", "texto": None, "audio_id": None, "imagen_id": None}


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
