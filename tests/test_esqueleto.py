import base64
import hashlib
import hmac
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from math import floor

from codi_informal.agente import VOZ_SIN_TRANSCRIPCION, Agente, atender
from codi_informal.firma import FirmaInvalida, verificar
from codi_informal.pey import Pey, PeyError
from codi_informal.registro import abrir, listar, registrar_pago
from codi_informal.server import Config, servir
from codi_informal.whatsapp import cuerpo_texto, extraer, multipart_imagen


SECRETO = "whsec_" + base64.b64encode(b"secreto-de-prueba-pey").decode()


def firmar(cuerpo: bytes) -> dict:
    cuando = datetime.now(timezone.utc)
    msg_id = "msg_prueba"
    sello = str(floor(cuando.timestamp()))
    llave = base64.b64decode(SECRETO[len("whsec_") :] + "==")
    firma = base64.b64encode(
        hmac.new(llave, f"{msg_id}.{sello}.".encode() + cuerpo, hashlib.sha256).digest()
    ).decode()
    return {
        "webhook-id": msg_id,
        "webhook-timestamp": sello,
        "webhook-signature": f"v1,{firma}",
    }


def firmar_whatsapp(cuerpo: bytes, secreto: str) -> str:
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


class PeyTests(unittest.TestCase):
    def test_push_arma_el_cuerpo_documentado(self):
        visto = {}

        def transport(method, path, crudo, headers):
            visto["method"] = method
            visto["path"] = path
            visto["cuerpo"] = json.loads(crudo)
            visto["auth"] = headers["Authorization"]
            return 200, json.dumps({"transactionId": "tx1", "codiId": "123"}).encode()

        cliente = Pey("key-de-prueba", max_amount="0.01", transport=transport)
        respuesta = cliente.push(
            amount="0.01",
            phone="+52 55 1234 5678",
            concept="Cobro del puesto",
            metadata={"canal": "whatsapp"},
        )
        self.assertEqual(respuesta["codiId"], "123")
        self.assertEqual(visto["method"], "POST")
        self.assertEqual(visto["path"], "/codi/pn")
        self.assertEqual(visto["cuerpo"]["phoneNumber"], "5512345678")
        self.assertEqual(visto["cuerpo"]["amount"], 0.01)
        self.assertEqual(visto["auth"], "Bearer key-de-prueba")
        self.assertNotIn("clabe", visto["cuerpo"])

    def test_no_pasa_el_tope_ni_manda_qr_en_cero(self):
        def transport(*args):
            raise AssertionError("no debía llamar a pey")

        cliente = Pey("key", max_amount="0.01", transport=transport)
        with self.assertRaises(PeyError):
            cliente.push(amount="20", phone="5512345678", concept="no")
        with self.assertRaises(PeyError):
            cliente.qr(amount="0", concept="puesto")


class FirmaTests(unittest.TestCase):
    def test_acepta_la_firma_y_rechaza_otra(self):
        cuerpo = b'{"type":"codi.pn.payment_received"}'
        verificar(SECRETO, cuerpo, firmar(cuerpo))
        with self.assertRaises(FirmaInvalida):
            verificar(SECRETO, cuerpo + b" ", firmar(cuerpo))


class RegistroTests(unittest.TestCase):
    def test_guarda_el_pago_sin_clabe_y_no_lo_duplica(self):
        with tempfile.TemporaryDirectory() as carpeta:
            conn = abrir(os.path.join(carpeta, "r.sqlite"))
            evento = {
                "type": "codi.pn.payment_received",
                "amount": 0.01,
                "concept": "Cobro del puesto",
                "numRef": "1234567",
                "transactionId": "tx1",
                "datePaid": 1790724758,
                "metadata": {
                    "clabe": "000000000000000000",
                    "externalMetadata": {"canal": "whatsapp", "puesto": "puesto"},
                },
            }
            self.assertTrue(registrar_pago(conn, evento, "msg1"))
            self.assertFalse(registrar_pago(conn, evento, "msg1"))
            filas = listar(conn)
            self.assertEqual(filas[0]["transaction_id"], "tx1")
            self.assertEqual(filas[0]["concept"], "Cobro del puesto")
            guardado = open(os.path.join(carpeta, "r.sqlite"), "rb").read()
            self.assertNotIn(b"000000000000000000", guardado)


class WhatsAppTests(unittest.TestCase):
    def test_lee_texto_y_nota_de_voz(self):
        texto = extraer(
            {
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "messages": [
                                        {"from": "5215512345678", "type": "text", "text": {"body": "cobra 0.01 al 5512345678"}}
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
        )
        self.assertEqual(texto["tipo"], "text")
        self.assertEqual(texto["de"], "5215512345678")
        audio = extraer(
            {"entry": [{"changes": [{"value": {"messages": [{"from": "1", "type": "audio", "audio": {"id": "abc"}}]}}]}]}
        )
        self.assertEqual(audio["audio_id"], "abc")

    def test_la_nota_de_voz_cae_en_el_mismo_cobro(self):
        agente = Agente(None, None, max_amount="0.01")
        sin_llave = atender({"tipo": "audio", "audio_id": "abc"}, agente)
        self.assertEqual(sin_llave.texto, VOZ_SIN_TRANSCRIPCION)
        con_texto = atender(
            {"tipo": "audio", "audio_id": "abc"},
            agente,
            transcribir=lambda audio_id: "cobra 0.01 al 5512345678",
        )
        self.assertIn("5512345678", con_texto.texto)
        self.assertIn("Falta PEY_API_KEY", con_texto.texto)

    def test_el_mensaje_de_salida_es_el_de_la_cloud_api(self):
        cuerpo = cuerpo_texto("5215512345678", "Entró un pago")
        self.assertEqual(cuerpo["messaging_product"], "whatsapp")
        self.assertEqual(cuerpo["type"], "text")
        png, content_type = multipart_imagen(b"\x89PNG")
        self.assertIn(b"whatsapp", png)
        self.assertIn(b"\x89PNG", png)
        self.assertIn("multipart/form-data", content_type)


class BotTests(unittest.TestCase):
    def test_mensaje_local_y_webhook(self):
        with tempfile.TemporaryDirectory() as carpeta:
            config = Config()
            config.pey_api_key = ""
            config.pey_webhook_secret = SECRETO
            config.whatsapp_token = ""
            config.whatsapp_verify_token = "verificar"
            config.whatsapp_app_secret = "secreto-meta"
            config.owner_whatsapp = "5512345678"
            config.registro_path = os.path.join(carpeta, "r.sqlite")
            config.host = "127.0.0.1"
            config.port = 0
            config.max_amount = "0.01"
            httpd = servir(config)
            hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
            hilo.start()
            self.addCleanup(httpd.shutdown)
            puerto = httpd.server_address[1]
            base = f"http://127.0.0.1:{puerto}"

            salud = json.load(urllib.request.urlopen(base + "/health"))
            self.assertTrue(salud["ok"])

            pedido = urllib.request.Request(
                base + "/mensaje",
                data=json.dumps({"texto": "cobra 0.01 al 5512345678"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            respuesta = json.load(urllib.request.urlopen(pedido))
            self.assertIn("Falta PEY_API_KEY", respuesta["texto"])

            evento = {
                "type": "codi.pn.payment_received",
                "amount": 0.01,
                "concept": "Cobro del puesto",
                "transactionId": "tx-webhook",
                "metadata": {"clabe": "012180009999999999", "externalMetadata": {"puesto": "puesto"}},
            }
            crudo = json.dumps(evento).encode()
            headers = firmar(crudo)
            headers["Content-Type"] = "application/json"
            pago = urllib.request.Request(base + "/webhooks/pey", data=crudo, headers=headers)
            cuerpo = json.load(urllib.request.urlopen(pago))
            self.assertTrue(cuerpo["nuevo"])
            self.assertIn("0.01", cuerpo["aviso"])
            self.assertNotIn("9999999999", cuerpo["aviso"])

            malo = urllib.request.Request(
                base + "/webhooks/pey",
                data=crudo,
                headers={"Content-Type": "application/json", "webhook-signature": "v1,no"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(malo)
            self.assertEqual(ctx.exception.code, 401)
            self.assertEqual(len(listar(abrir(config.registro_path))), 1)

            evento_whatsapp = {
                "entry": [{"changes": [{"value": {"messages": [{
                    "from": "5215512345678", "type": "text",
                    "text": {"body": "qué se ha cobrado"},
                }]}}]}]
            }
            crudo_whatsapp = json.dumps(evento_whatsapp).encode()
            headers_whatsapp = {
                "Content-Type": "application/json",
                "X-Hub-Signature-256": firmar_whatsapp(crudo_whatsapp, config.whatsapp_app_secret),
            }
            respuesta = urllib.request.urlopen(urllib.request.Request(
                base + "/webhooks/whatsapp", data=crudo_whatsapp, headers=headers_whatsapp
            ))
            self.assertTrue(json.load(respuesta)["ok"])

            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(urllib.request.Request(
                    base + "/webhooks/whatsapp", data=crudo_whatsapp,
                    headers={"Content-Type": "application/json"},
                ))
            self.assertEqual(ctx.exception.code, 401)

            desconocido = crudo_whatsapp.replace(b"5215512345678", b"5215587654321")
            headers_desconocido = {
                "Content-Type": "application/json",
                "X-Hub-Signature-256": firmar_whatsapp(desconocido, config.whatsapp_app_secret),
            }
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(urllib.request.Request(
                    base + "/webhooks/whatsapp", data=desconocido, headers=headers_desconocido
                ))
            self.assertEqual(ctx.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
