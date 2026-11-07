"""Servidor del bot. Escucha a WhatsApp y a pey. No sirve páginas."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from codi_informal.agente import Agente, atender
from codi_informal.firma import FirmaInvalida, verificar
from codi_informal.pey import Pey
from codi_informal.registro import abrir, aviso, registrar_pago
from codi_informal.whatsapp import extraer


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
        self.owner_whatsapp = os.environ.get("OWNER_WHATSAPP", "")
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


def handler(config: Config, conn, pey):
    agente = Agente(pey, conn, max_amount=config.max_amount)

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
            try:
                data = json.loads(cuerpo.decode() or "{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "json inválido"})
                return
            entrada = extraer(data)
            resultado = atender(entrada, agente)
            if resultado and resultado.texto and entrada.get("de"):
                self._avisar(entrada["de"], resultado.texto)
            self._json(200, {"ok": True})

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

        def _avisar(self, destino: str, texto: str):
            if not config.whatsapp_token or not config.whatsapp_phone_number_id:
                return
            from codi_informal.whatsapp import cuerpo_texto
            import urllib.request

            url = (
                "https://graph.facebook.com/v21.0/"
                f"{config.whatsapp_phone_number_id}/messages"
            )
            req = urllib.request.Request(
                url,
                data=json.dumps(cuerpo_texto(destino, texto)).encode(),
                headers={
                    "Authorization": f"Bearer {config.whatsapp_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=15).close()
            except Exception:
                return

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


def servir(config: Config | None = None):
    config = config or Config()
    carpeta = os.path.dirname(config.registro_path)
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
