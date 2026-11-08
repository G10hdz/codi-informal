"""Servidor del bot. Escucha a WhatsApp y a pey. No sirve páginas."""

import json
import logging
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from codi_informal import openrouter, voz
from codi_informal.agente import Agente, atender
from codi_informal.firma import FirmaInvalida, verificar
from codi_informal.limites import Limites
from codi_informal.pey import Pey
from codi_informal.registro import abrir, aviso, registrar_pago
from codi_informal.whatsapp import (
    cuerpo_imagen, cuerpo_texto, descargar_media, extraer, firma_valida, multipart_imagen,
)

log = logging.getLogger("codi_informal")

MAX_CUERPO = 64 * 1024
MAX_TEXTO = 2000
MSG_POR_MIN = 10
COBROS_POR_MIN = 3
_COBRO = re.compile(r"cobra(?:r|me)?\s|\bqr\b", re.IGNORECASE)


class Config:
    def __init__(self):
        self.pey_api_key = os.environ.get("PEY_API_KEY", "")
        self.pey_webhook_secret = os.environ.get("PEY_WEBHOOK_SECRET", "")
        self.pey_bank_account_id = os.environ.get("PEY_BANK_ACCOUNT_ID", "")
        self.pey_base_url = os.environ.get("PEY_BASE_URL", "https://api.pey.mx")
        self.max_amount = os.environ.get("PEY_MAX_AMOUNT", "0.01")
        self.whatsapp_token = os.environ.get("WHATSAPP_TOKEN", "")
        self.whatsapp_phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.whatsapp_verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
        self.whatsapp_app_secret = os.environ.get("WHATSAPP_APP_SECRET", "")
        self.owner_whatsapp = os.environ.get("OWNER_WHATSAPP", "")
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.cobros_activos = os.environ.get("COBROS_ACTIVOS") != "0"
        self.limites_path = os.environ.get("LIMITES_PATH", "data/limites.sqlite")
        self.registro_path = os.environ.get("REGISTRO_PATH", "data/registro.sqlite")
        self.host = os.environ.get("HOST", "127.0.0.1")
        self.port = int(os.environ.get("PORT", "8787"))


def crear_pey(config: Config):
    if not config.pey_api_key:
        return None
    return Pey(
        config.pey_api_key,
        base_url=config.pey_base_url,
        bank_account_id=config.pey_bank_account_id or None,
        max_amount=config.max_amount,
    )


def _censurar(telefono) -> str:
    return "***" + "".join(c for c in str(telefono) if c.isdigit())[-4:]


def crear_transcribir(config: Config):
    """audio_id -> texto o None: baja el ogg de Meta, mide su duración y lo
    transcribe con OpenRouter (REQ-8)."""
    def transcribir(audio_id):
        return voz.transcribir(
            audio_id,
            descargar=lambda media_id, **kw: descargar_media(media_id, config.whatsapp_token, **kw),
            transcriptor=openrouter.transcriptor,
            duracion=voz.duracion,
        )
    return transcribir


def handler(config: Config, conn, pey, limites=None):
    if limites is None:
        try:
            limites = Limites(config.limites_path)
        except Exception:
            log.warning("limites no disponibles: se bloquean los cobros")
    agente = Agente(pey, conn, max_amount=config.max_amount,
                    cobros_activos=config.cobros_activos)
    transcribir = crear_transcribir(config) if config.openrouter_api_key else None

    class Bot(BaseHTTPRequestHandler):
        def log_message(self, formato, *args):
            return

        def do_GET(self):
            ruta = urlparse(self.path)
            if ruta.path == "/health":
                self._json(200, {"ok": True})
                return
            if ruta.path == "/webhooks/whatsapp":
                self._verificar_whatsapp(ruta.query)
                return
            self._json(404, {"error": "no existe"})

        def do_POST(self):
            ruta = urlparse(self.path).path
            try:
                largo = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError:
                largo = -1
            if largo < 0 or largo > MAX_CUERPO:
                self.close_connection = True
                self._json(413 if largo > 0 else 400, {"error": "cuerpo no aceptado"})
                return
            cuerpo = self._cuerpo()
            if ruta == "/webhooks/pey":
                self._pey(cuerpo)
                return
            if ruta == "/webhooks/whatsapp":
                self._whatsapp(cuerpo)
                return
            if ruta == "/mensaje":
                self._mensaje_local(cuerpo)
                return
            self._json(404, {"error": "no existe"})

        def _verificar_whatsapp(self, query: str):
            datos = parse_qs(query)
            modo = datos.get("hub.mode", [""])[0]
            token = datos.get("hub.verify_token", [""])[0]
            reto = datos.get("hub.challenge", [""])[0]
            if modo == "subscribe" and token and token == config.whatsapp_verify_token:
                self._texto(200, reto)
                return
            self._texto(403, "no")

        def _mensaje_local(self, cuerpo: bytes):
            try:
                data = json.loads(cuerpo.decode() or "{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "json inválido"})
                return
            resultado = atender({"tipo": "text", "texto": data.get("texto", "")}, agente)
            self._json(200, {"texto": resultado.texto, "tiene_imagen": resultado.imagen is not None})

        def _whatsapp(self, cuerpo: bytes):
            if not firma_valida(
                config.whatsapp_app_secret,
                cuerpo,
                self.headers.get("X-Hub-Signature-256", ""),
            ):
                self._json(401, {"error": "webhook rechazado"})
                return
            try:
                data = json.loads(cuerpo.decode() or "{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "json inválido"})
                return
            entrada = extraer(data)
            # el evento tiene que ir dirigido a nuestro número; otro negocio de la app se ignora
            if (entrada.get("phone_number_id") or "") != (config.whatsapp_phone_number_id or ""):
                self._json(200, {"ok": True})
                return
            if entrada.get("tipo") == "status":
                self._json(200, {"ok": True})
                return
            if entrada.get("grupo"):
                self._json(200, {"ok": True})
                return
            if not _mismo_telefono(entrada.get("de"), config.owner_whatsapp):
                self._json(403, {"error": "remitente no autorizado"})
                return
            de = entrada["de"]
            # sin id de WhatsApp no hay dedupe posible: se ignora, no llega al agente
            if not entrada.get("id"):
                self._json(200, {"ok": True})
                return
            try:
                if limites is None:
                    raise RuntimeError("dedupe sin almacenamiento")
                if limites.repetido(entrada["id"]):
                    self._json(200, {"ok": True})
                    return
            except Exception:
                # un evento repetido no debe crear dos cargos: se pide reintento
                log.warning("dedupe no disponible")
                self._json(503, {"error": "reintenta más tarde"})
                return
            texto = entrada.get("texto") or ""
            if len(texto) > MAX_TEXTO:
                self._avisar(de, "El mensaje es muy largo. Escríbelo en menos de 2,000 caracteres.")
                self._json(200, {"ok": True})
                return
            rechazo = self._cupo(de, texto)
            if rechazo:
                self._avisar(de, rechazo)
                self._json(200, {"ok": True})
                return
            resultado = atender(entrada, agente, transcribir=transcribir, dueno=de, chat=de)
            if resultado and resultado.texto:
                self._avisar(de, resultado.texto, resultado.imagen, resultado.qr_texto)
            self._json(200, {"ok": True})

        def _cupo(self, de: str, texto: str):
            cobro = bool(_COBRO.search(texto))
            try:
                if limites is None:
                    raise RuntimeError("sin almacenamiento")
                if not limites.permitir(de, "mensajes", MSG_POR_MIN):
                    return "Vas muy rápido. Espera un minuto."
                if cobro and not limites.permitir(de, "cobros", COBROS_POR_MIN):
                    return "Ya van 3 cobros en este minuto. Espera un poco."
            except Exception:
                if cobro:
                    log.warning("limites no disponibles: cobro bloqueado %s", _censurar(de))
                    return "Ahorita no puedo cobrar. Intenta más tarde."
            return None

        def _pey(self, cuerpo: bytes):
            try:
                verificar(config.pey_webhook_secret, cuerpo, dict(self.headers))
                evento = json.loads(cuerpo.decode() or "{}")
            except (FirmaInvalida, json.JSONDecodeError):
                self._json(401, {"error": "webhook rechazado"})
                return
            if not isinstance(evento, dict):
                self._json(400, {"error": "json inválido"})
                return
            tipo = evento.get("type")
            if tipo == "bank.account.updated":
                self._json(200, {"ok": True})
                return
            if tipo not in ("codi.pn.payment_received", "codi.qr.payment_received"):
                self._json(200, {"ok": True})
                return
            try:
                nuevo = registrar_pago(conn, evento, self.headers.get("webhook-id"))
            except ValueError:
                self._json(400, {"error": "falta transactionId"})
                return
            texto = ""
            if nuevo:
                texto = aviso(
                    {
                        "amount": evento.get("amount"),
                        "concept": evento.get("concept"),
                    }
                )
                if config.owner_whatsapp:
                    self._avisar(config.owner_whatsapp, texto)
            self._json(200, {"ok": True, "nuevo": nuevo, "aviso": texto})

        def _avisar(self, destino: str, texto: str, imagen: bytes | None = None,
                    texto_imagen: str | None = None):
            if not config.whatsapp_token or not config.whatsapp_phone_number_id:
                return
            base = f"https://graph.facebook.com/v21.0/{config.whatsapp_phone_number_id}"
            auth = {"Authorization": f"Bearer {config.whatsapp_token}"}
            try:
                if imagen:
                    try:
                        enviado = self._enviar_imagen(base, auth, destino, imagen)
                    except Exception as exc:
                        log.warning("imagen no enviada a %s: %s", _censurar(destino), _causa(exc))
                        enviado = False
                    if enviado:
                        return
                if texto_imagen:
                    texto = f"{texto}\n\n{texto_imagen}"
                self._post(base + "/messages", auth, cuerpo_texto(destino, texto))
            except Exception as exc:
                log.warning("aviso no enviado a %s: %s", _censurar(destino), _causa(exc))

        def _enviar_imagen(self, base, auth, destino, imagen) -> bool:
            crudo, tipo = multipart_imagen(imagen)
            req = urllib.request.Request(
                base + "/media", data=crudo, headers={**auth, "Content-Type": tipo}, method="POST"
            )
            media = json.loads(urllib.request.urlopen(req, timeout=15).read() or b"{}").get("id")
            if not media:
                return False
            self._post(base + "/messages", auth, cuerpo_imagen(destino, media))
            return True

        def _post(self, url, auth, datos):
            req = urllib.request.Request(
                url,
                data=json.dumps(datos).encode(),
                headers={**auth, "Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=15).close()

        def _cuerpo(self) -> bytes:
            largo = int(self.headers.get("Content-Length", "0") or "0")
            return self.rfile.read(largo)

        def _json(self, status: int, data: dict):
            crudo = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(crudo)))
            self.end_headers()
            self.wfile.write(crudo)

        def _texto(self, status: int, texto: str):
            crudo = texto.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(crudo)))
            self.end_headers()
            self.wfile.write(crudo)

    return Bot


def _causa(exc: Exception) -> str:
    # solo el tipo y el código HTTP: el mensaje puede traer cuerpos o teléfonos
    return f"{type(exc).__name__} {getattr(exc, 'code', '')}".strip()


def _mismo_telefono(uno, otro) -> bool:
    def digitos(valor):
        numero = "".join(c for c in str(valor or "") if c.isdigit())
        if len(numero) == 13 and numero.startswith("521"):
            return numero[3:]
        if len(numero) == 12 and numero.startswith("52"):
            return numero[2:]
        return numero

    return bool(uno and otro) and digitos(uno) == digitos(otro)


def servir(config: Config | None = None):
    config = config or Config()
    for ruta in (config.registro_path, config.limites_path):
        carpeta = os.path.dirname(ruta)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
    conn = abrir(config.registro_path)
    pey = crear_pey(config)
    httpd = ThreadingHTTPServer((config.host, config.port), handler(config, conn, pey))
    return httpd


def main():
    config = Config()
    print(
        f"bot en http://{config.host}:{config.port} "
        f"pey={'lista' if config.pey_api_key else 'sin key'}",
        flush=True,
    )
    servir(config).serve_forever()
