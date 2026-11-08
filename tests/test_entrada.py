import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
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
CODIGO = "A1B2C3"


class PeyDoble:
    def __init__(self):
        self.pushes = 0
        self.qrs = 0

    def push(self, **kw):
        self.pushes += 1
        return {"transactionId": "tx1", "codiId": "1"}

    def qr(self, **kw):
        self.qrs += 1
        return {"qrImage": base64.b64encode(PNG).decode(), "qrString": "QRSTRING-PRUEBA"}


class _Respuesta:
    def __init__(self, datos):
        self._d = datos

    def read(self):
        return self._d

    def close(self):
        pass


class _ConnConUnCommitRoto:
    """Proxy de la conexion de limites: el primer commit falla, como un corte de disco."""

    def __init__(self, conn):
        self._conn = conn
        self._falla = True

    def commit(self):
        if self._falla:
            self._falla = False
            raise sqlite3.OperationalError("commit simulado")
        self._conn.commit()

    def __getattr__(self, nombre):
        return getattr(self._conn, nombre)


def _codigo_fijo():
    """Deja siempre el mismo código de confirmación para poder contestarlo."""
    return mock.patch("secrets.token_hex", lambda n: "a1b2c3")


def evento(texto, de=DUENO, mid="wamid.1", para=""):
    return json.dumps({"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": para},
        "messages": [
            {"from": de, "id": mid, "type": "text", "text": {"body": texto}}
        ]}}]}]}).encode()


def firma(cuerpo, secreto=APP):
    return "sha256=" + hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


class Base(unittest.TestCase):
    def levantar(self, limites=None, **ajustes):
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
            (config.host, 0), handler(config, abrir(config.registro_path), self.pey, limites)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.base = f"http://127.0.0.1:{httpd.server_address[1]}"
        return config

    def post(self, cuerpo, firmado=True, headers=None):
        # build_opener no pasa por urllib.request.urlopen: sirve dentro de mocks de urlopen
        h = {"Content-Type": "application/json"}
        if firmado:
            h["X-Hub-Signature-256"] = firma(cuerpo)
        h.update(headers or {})
        req = urllib.request.Request(self.base + "/webhooks/whatsapp", data=cuerpo, headers=h)
        try:
            with urllib.request.build_opener().open(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def cobra_y_confirma(self, mid, para=""):
        """Un cobro y su confirmación; cada entrega espera 200."""
        with _codigo_fijo():
            self.assertEqual(self.post(evento("cobra 0.01 al 5512345678", mid=mid, para=para)), 200)
        self.assertEqual(self.post(evento(f"confirmar {CODIGO}", mid=f"{mid}-ok", para=para)), 200)


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

    def test_evento_de_otro_numero_se_ignora(self):
        self.levantar(whatsapp_phone_number_id="123")
        # firmado pero dirigido a otro negocio de la app: no arma borrador ni cobro
        with _codigo_fijo():
            self.assertEqual(
                self.post(evento("cobra 0.01 al 5512345678", mid="o1", para="999")), 200)
        self.post(evento(f"confirmar {CODIGO}", mid="o2", para="999"))
        self.assertEqual(self.pey.pushes, 0)
        self.cobra_y_confirma("o3", para="123")
        self.assertEqual(self.pey.pushes, 1)

    def test_grupo_se_ignora(self):
        self.levantar()
        cuerpo = json.dumps({"entry": [{"changes": [{"value": {"messages": [
            {"from": DUENO, "id": "g1", "type": "text", "group_id": "120363@g.us",
             "text": {"body": "cobra 0.01 al 5512345678"}}
        ]}}]}]}).encode()
        self.assertNotEqual(self.post(cuerpo), 500)
        self.assertEqual(self.pey.pushes, 0)


class Identidad(Base):
    def test_otro_chat_no_confirma_el_borrador(self):
        self.levantar()
        with _codigo_fijo():
            self.assertEqual(self.post(evento("cobra 0.01 al 5512345678", mid="i1")), 200)
        # el mismo dueño con otro wa id es otro chat: no consume la confirmación
        self.assertEqual(
            self.post(evento(f"confirmar {CODIGO}", de="5500000001", mid="i2")), 200)
        self.assertEqual(self.pey.pushes, 0)
        # el chat que pidió el cobro sí confirma
        self.assertEqual(self.post(evento(f"confirmar {CODIGO}", mid="i3")), 200)
        self.assertEqual(self.pey.pushes, 1)


class Dedupe(Base):
    def test_repetido_recibe_200_sin_efecto(self):
        self.levantar()
        self.cobra_y_confirma("wamid.dup")
        # la reentrega del mismo evento no arma otro borrador ni otro cobro
        self.cobra_y_confirma("wamid.dup")
        self.assertEqual(self.pey.pushes, 1)

    def test_persiste_entre_reinicios(self):
        from codi_informal.limites import Limites
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "l.sqlite")
            self.assertFalse(Limites(ruta).repetido("wamid.x"))
            self.assertTrue(Limites(ruta).repetido("wamid.x"))

    def test_mensaje_sin_id_no_llega_al_agente(self):
        self.levantar()
        with _codigo_fijo():
            self.assertEqual(self.post(evento("cobra 0.01 al 5512345678", mid=None)), 200)
        self.post(evento(f"confirmar {CODIGO}", mid="k-sin-id"))
        self.assertEqual(self.pey.pushes, 0)

    def test_dedupe_caido_reintenta_sin_cobrar(self):
        self.levantar(limites_path="/no/existe/l.sqlite")
        self.assertEqual(self.post(evento("cobra 0.01 al 5512345678")), 503)
        self.post(evento(f"confirmar {CODIGO}", mid="k-caido"))
        self.assertEqual(self.pey.pushes, 0)

    def test_commit_fallido_reintento_llega_al_agente(self):
        from codi_informal.limites import Limites
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        lim = Limites(os.path.join(carpeta.name, "l.sqlite"))
        lim._conn = _ConnConUnCommitRoto(lim._conn)
        self.levantar(limites=lim)
        with _codigo_fijo():
            # el commit del dedupe falla en la primera entrega: 503 y sin borrador
            self.assertEqual(
                self.post(evento("cobra 0.01 al 5512345678", mid="wamid.commit")), 503)
            # la reentrega del mismo id no es duplicado: llega al agente una sola vez
            self.assertEqual(
                self.post(evento("cobra 0.01 al 5512345678", mid="wamid.commit")), 200)
        self.post(evento(f"confirmar {CODIGO}", mid="wamid.commit-ok"))
        self.assertEqual(self.pey.pushes, 1)


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
            self.cobra_y_confirma(f"c{i}")
        self.assertEqual(self.pey.pushes, 3)

    def test_mensaje_once_bloqueado(self):
        self.levantar(whatsapp_token="tok", whatsapp_phone_number_id="123")
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            return _Respuesta(b'{"id": "m1"}')

        with mock.patch("urllib.request.urlopen", falso):
            for i in range(11):
                self.post(evento("qué se ha cobrado", mid=f"m{i}", para="123"))
        cuerpos = [json.loads(r.data)["text"]["body"] for r in vistos
                   if r.full_url.endswith("/messages")]
        # 10 respuestas del agente y el 11 es el rechazo del tope por minuto
        self.assertEqual(len(cuerpos), 11)
        self.assertEqual(cuerpos[:10], ["Todavía no entra ningún pago."] * 10)
        self.assertEqual(cuerpos[10], "Vas muy rápido. Espera un minuto.")

    def test_sin_almacenamiento_bloquea_cobro(self):
        self.levantar(limites_path="/no/existe/l.sqlite")
        self.assertEqual(self.post(evento("cobra 0.01 al 5512345678")), 503)
        self.assertEqual(self.pey.pushes, 0)


class Salida(Base):
    def test_qr_se_manda_como_imagen(self):
        self.levantar(whatsapp_token="tok", whatsapp_phone_number_id="123")
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            return _Respuesta(b'{"id": "media1"}')

        with mock.patch("urllib.request.urlopen", falso):
            with _codigo_fijo():
                self.post(evento("manda el qr", mid="q1", para="123"))
            self.post(evento(f"confirmar {CODIGO}", mid="q2", para="123"))
        urls = [r.full_url for r in vistos]
        self.assertTrue(any(u.endswith("/123/media") for u in urls), urls)
        imagenes = [json.loads(r.data) for r in vistos
                    if r.full_url.endswith("/messages") and json.loads(r.data).get("type") == "image"]
        self.assertEqual(len(imagenes), 1)
        self.assertEqual(imagenes[0]["image"]["id"], "media1")

    def test_qr_sin_imagen_cae_a_texto_con_el_qr_string(self):
        self.levantar(whatsapp_token="tok", whatsapp_phone_number_id="123")
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            if req.full_url.endswith("/media"):
                raise urllib.error.URLError("sin media")
            return _Respuesta(b'{"id": "media1"}')

        with mock.patch("urllib.request.urlopen", falso):
            with _codigo_fijo():
                self.post(evento("manda el qr", mid="q1", para="123"))
            self.post(evento(f"confirmar {CODIGO}", mid="q2", para="123"))
        textos = [json.loads(r.data)["text"]["body"] for r in vistos
                  if r.full_url.endswith("/messages") and json.loads(r.data).get("type") == "text"]
        self.assertIn("QRSTRING-PRUEBA", textos[-1])

    def test_fallo_de_envio_se_registra_sin_telefono_ni_cuerpo(self):
        self.levantar(whatsapp_token="tok", whatsapp_phone_number_id="123")

        def falla(req, timeout=0):
            raise urllib.error.URLError("boom 5215500000001 cuerpo-secreto")

        with self.assertLogs("codi_informal", level="WARNING") as logs:
            with mock.patch("urllib.request.urlopen", falla):
                self.post(evento("hola", mid="h1", para="123"))
        salida = "\n".join(logs.output)
        self.assertIn("0001", salida)
        self.assertNotIn("5215500000001", salida)
        self.assertNotIn("cuerpo-secreto", salida)


if __name__ == "__main__":
    unittest.main()
