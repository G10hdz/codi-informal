import base64
import hashlib
import hmac
import json
import logging
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from codi_informal.registro import abrir
from codi_informal.server import Config, handler

APP = "secreto-meta-prueba"
DUENO = "5215500000001"
PNG = b"\x89PNG-de-prueba"


class PeyDoble:
    def __init__(self):
        self.pushes = 0
        self.qrs = 0

    def push(self, **kw):
        self.pushes += 1
        return {"transactionId": "tx1", "codiId": "1"}

    def qr(self, **kw):
        self.qrs += 1
        return {"qrImage": base64.b64encode(PNG).decode()}


def evento(texto, de=DUENO, mid="wamid.1"):
    return json.dumps({"entry": [{"changes": [{"value": {"messages": [
        {"from": de, "id": mid, "type": "text", "text": {"body": texto}}
    ]}}]}]}).encode()


def firma(cuerpo, secreto=APP):
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


class Base(unittest.TestCase):
    def levantar(self, **ajustes):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        config = Config()
        config.pey_webhook_secret = ""
        config.whatsapp_token = ""
        config.whatsapp_app_secret = APP
        config.owner_whatsapp = "5500000001"
        config.registro_path = os.path.join(carpeta.name, "r.sqlite")
        config.limites_path = os.path.join(carpeta.name, "l.sqlite")
        config.host, config.port = "127.0.0.1", 0
        for k, v in ajustes.items():
            setattr(config, k, v)
        self.pey = PeyDoble()
        httpd = ThreadingHTTPServer(
            (config.host, 0), handler(config, abrir(config.registro_path), self.pey)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.base = f"http://127.0.0.1:{httpd.server_address[1]}"
        return config

    def post(self, cuerpo, firmado=True, headers=None):
        h = {"Content-Type": "application/json"}
        if firmado:
            h["X-Hub-Signature-256"] = firma(cuerpo)
        h.update(headers or {})
        req = urllib.request.Request(self.base + "/webhooks/whatsapp", data=cuerpo, headers=h)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code


class FirmaYDueno(Base):
    def test_sin_firma_401_sin_agente(self):
        self.levantar()
        self.assertEqual(self.post(evento("cobra 0.01 al 5512345678"), firmado=False), 401)
        self.assertEqual(self.pey.pushes, 0)

    def test_sin_secreto_401(self):
        self.levantar(whatsapp_app_secret="")
        self.assertEqual(self.post(evento("cobra 0.01 al 5512345678")), 401)
        self.assertEqual(self.pey.pushes, 0)

    def test_ajeno_y_sin_dueno_configurado(self):
        self.levantar()
        self.assertEqual(self.post(evento("cobra 0.01 al 5512345678", de="5215500000999")), 403)
        self.assertEqual(self.pey.pushes, 0)

    def test_dueno_vacio_rechaza_todo(self):
        self.levantar(owner_whatsapp="")
        self.assertEqual(self.post(evento("hola")), 403)

    def test_grupo_se_ignora(self):
        self.levantar()
        cuerpo = json.dumps({"entry": [{"changes": [{"value": {"messages": [
            {"from": DUENO, "id": "g1", "type": "text", "group_id": "120363@g.us",
             "text": {"body": "cobra 0.01 al 5512345678"}}
        ]}}]}]}).encode()
        self.assertNotEqual(self.post(cuerpo), 500)
        self.assertEqual(self.pey.pushes, 0)


class Dedupe(Base):
    def test_repetido_recibe_200_sin_efecto(self):
        self.levantar()
        cuerpo = evento("cobra 0.01 al 5512345678", mid="wamid.dup")
        self.assertEqual(self.post(cuerpo), 200)
        self.assertEqual(self.post(cuerpo), 200)
        self.assertEqual(self.pey.pushes, 1)

    def test_persiste_entre_reinicios(self):
        from codi_informal.limites import Limites
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "l.sqlite")
            self.assertFalse(Limites(ruta).repetido("wamid.x"))
            self.assertTrue(Limites(ruta).repetido("wamid.x"))


class Topes(Base):
    def test_content_length_grande_413(self):
        self.levantar()
        self.assertEqual(self.post(b"x" * 70000), 413)
        self.assertEqual(self.pey.pushes, 0)

    def test_texto_largo_no_llega_al_agente(self):
        self.levantar()
        largo = "cobra 0.01 al 5512345678 " + "a" * 2000
        self.assertEqual(self.post(evento(largo)), 200)
        self.assertEqual(self.pey.pushes, 0)


class Limites_(Base):
    def test_cuarto_cobro_del_minuto_bloqueado(self):
        self.levantar()
        for i in range(4):
            self.post(evento("cobra 0.01 al 5512345678", mid=f"c{i}"))
        self.assertEqual(self.pey.pushes, 3)

    def test_mensaje_once_bloqueado(self):
        self.levantar()
        for i in range(11):
            self.post(evento("qué se ha cobrado", mid=f"m{i}"))
        # el 11 no llega al agente: se ve porque no hay efecto; probamos con cobro
        self.assertEqual(self.post(evento("cobra 0.01 al 5512345678", mid="z")), 200)
        self.assertEqual(self.pey.pushes, 0)

    def test_sin_almacenamiento_bloquea_cobro(self):
        self.levantar(limites_path="/no/existe/l.sqlite")
        self.post(evento("cobra 0.01 al 5512345678"))
        self.assertEqual(self.pey.pushes, 0)


class Salida(Base):
    def test_qr_se_manda_como_imagen(self):
        self.levantar(whatsapp_token="tok", whatsapp_phone_number_id="123")
        vistos = []

        class R:
            def __init__(s, d): s.d = d
            def read(s): return s.d
            def close(s): pass

        def falso(req, timeout=0):
            vistos.append(req)
            return R(b'{"id": "media1"}')

        with mock.patch("urllib.request.urlopen", falso):
            self.post_local = None
            # el POST al bot usa urlopen real; lo hacemos con un opener propio
            req = urllib.request.Request(
                self.base + "/webhooks/whatsapp", data=evento("manda el qr"),
                headers={"X-Hub-Signature-256": firma(evento("manda el qr"))})
            urllib.request.build_opener().open(req).close()
        urls = [r.full_url for r in vistos]
        self.assertTrue(any(u.endswith("/123/media") for u in urls), urls)
        enviado = [json.loads(r.data) for r in vistos if r.full_url.endswith("/messages")]
        self.assertEqual(enviado[0]["type"], "image")
        self.assertEqual(enviado[0]["image"]["id"], "media1")

    def test_fallo_de_envio_se_registra_sin_telefono_ni_cuerpo(self):
        self.levantar(whatsapp_token="tok", whatsapp_phone_number_id="123")

        def falla(req, timeout=0):
            raise urllib.error.URLError("boom 5215500000001 cuerpo-secreto")

        with self.assertLogs("codi_informal", level="WARNING") as logs:
            with mock.patch("urllib.request.urlopen", falla):
                req = urllib.request.Request(
                    self.base + "/webhooks/whatsapp", data=evento("hola"),
                    headers={"X-Hub-Signature-256": firma(evento("hola"))})
                urllib.request.build_opener().open(req).close()
        salida = "\n".join(logs.output)
        self.assertIn("0001", salida)
        self.assertNotIn("5215500000001", salida)
        self.assertNotIn("cuerpo-secreto", salida)


if __name__ == "__main__":
    unittest.main()
