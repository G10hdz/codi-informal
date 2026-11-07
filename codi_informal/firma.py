"""Verifica webhooks de pey, que firman con Standard Webhooks."""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from math import floor


class FirmaInvalida(Exception):
    pass


def _llave(secreto: str) -> bytes:
    if secreto.startswith("whsec_"):
        secreto = secreto[len("whsec_") :]
    cruda = base64.b64decode(secreto + "==")
    if not cruda:
        raise FirmaInvalida("el secreto del webhook está vacío")
    return cruda


def verificar(
    secreto: str,
    cuerpo: bytes,
    headers: dict,
    *,
    ahora: datetime | None = None,
    tolerancia: timedelta = timedelta(minutes=5),
) -> None:
    """Revisa webhook-id, webhook-timestamp y webhook-signature contra el cuerpo crudo."""
    if not secreto:
        raise FirmaInvalida("falta el secreto del webhook")
    normales = {str(k).lower(): str(v) for k, v in headers.items()}
    msg_id = normales.get("webhook-id")
    firma = normales.get("webhook-signature")
    sello = normales.get("webhook-timestamp")
    if not msg_id or not firma or not sello:
        raise FirmaInvalida("faltan headers del webhook")
    try:
        cuando = datetime.fromtimestamp(float(sello), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        raise FirmaInvalida("timestamp inválido") from None
    ahora = ahora or datetime.now(timezone.utc)
    if cuando < ahora - tolerancia or cuando > ahora + tolerancia:
        raise FirmaInvalida("timestamp fuera de rango")
    firmado = f"{msg_id}.{floor(cuando.timestamp())}.".encode() + cuerpo
    esperada = "v1," + base64.b64encode(
        hmac.new(_llave(secreto), firmado, hashlib.sha256).digest()
    ).decode()
    if not any(hmac.compare_digest(esperada, parte) for parte in firma.split(" ")):
        raise FirmaInvalida("la firma no coincide")
