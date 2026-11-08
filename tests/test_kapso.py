import hashlib
import hmac
import json
import os
import unittest
import urllib.error
import urllib.request
from unittest import mock

from codi_informal.whatsapp import descargar_media, extraer_kapso, firma_kapso_valida
from tests.test_entrada import Base, CODIGO, _Respuesta, _codigo_fijo
from tests.test_esqueleto import _Media
from tests.test_multimodal import _Resp

WEBHOOK_SECRETO = "kapso-webhook-secreto"
API_KEY = "kapso-api-key"
PHONE_ID = "kapso-phone-1"
DUENO = "5215500000001"


def firma_kapso(cuerpo, secreto=WEBHOOK_SECRETO):
    return hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def _mensaje(mid, de, tipo, extra_msg=None, kapso_extra=None, sin_kapso=False):
    mensaje = {
        "id": mid, "timestamp": "1730092800", "type": tipo, "from": de,
        "kapso": {
            "direction": "inbound", "status": "received",
            "processing_status": "pending", "origin": "cloud_api",
            "has_media": tipo in ("audio", "image"),
            **(kapso_extra or {}),
        },
        **(extra_msg or {}),
    }
    if sin_kapso:
        mensaje.pop("kapso")
    return mensaje


def evento(texto, de=DUENO, mid="wamid.k1", phone_id=PHONE_ID, **kw):
    return json.dumps({
        "message": _mensaje(mid, de, "text", {"text": {"body": texto}}, **kw),
        "conversation": {"id": "conv1", "phone_number": de, "phone_number_id": phone_id},
        "is_new_conversation": False,
        "phone_number_id": phone_id,
    }).encode()


def evento_audio(mid, audio_id="audk1", de=DUENO, phone_id=PHONE_ID):
    return json.dumps({
        "message": _mensaje(mid, de, "audio", {
            "audio": {"id": audio_id, "mime_type": "audio/ogg; codecs=opus"}},
            {"media_url": "https://api.kapso.ai/media/audk1"}),
        "conversation": {"id": "conv1", "phone_number": de, "phone_number_id": phone_id},
        "is_new_conversation": False,
        "phone_number_id": phone_id,
    }).encode()


def evento_imagen(mid, imagen_id="imgk1", de=DUENO, phone_id=PHONE_ID):
    return json.dumps({
        "message": _mensaje(mid, de, "image", {
            "image": {"id": imagen_id, "mime_type": "image/jpeg"}},
            {"media_url": "https://api.kapso.ai/media/imgk1"}),
        "conversation": {"id": "conv1", "phone_number": de, "phone_number_id": phone_id},
        "is_new_conversation": False,
        "phone_number_id": phone_id,
    }).encode()


def textos(vistos):
    return [json.loads(r.data)["text"]["body"] for r in vistos
            if r.full_url.endswith("/messages")]


class FirmaKapsoTests(unittest.TestCase):
    def test_acepta_el_hmac_hex_del_cuerpo_crudo(self):
        cuerpo = b'{"message":{"type":"text"}}'
        self.assertTrue(firma_kapso_valida(WEBHOOK_SECRETO, cuerpo, firma_kapso(cuerpo)))

    def test_rechaza_mala_faltante_o_rara(self):
        cuerpo = b"{}"
        for mala in ("", "sha256=" + firma_kapso(cuerpo), "zz" * 32,
                     firma_kapso(cuerpo, "otro-secreto"), firma_kapso(cuerpo + b" ")):
            self.assertFalse(firma_kapso_valida(WEBHOOK_SECRETO, cuerpo, mala), mala)

    def test_sin_secreto_rechaza(self):
        cuerpo = b"{}"
        self.assertFalse(firma_kapso_valida("", cuerpo, firma_kapso(cuerpo)))


class ExtraerKapsoTests(unittest.TestCase):
    def test_texto(self):
        entrada = extraer_kapso(json.loads(evento("cobra 0.01 al 5512345678")))
        self.assertEqual(entrada["tipo"], "text")
        self.assertEqual(entrada["texto"], "cobra 0.01 al 5512345678")
        self.assertEqual(entrada["de"], DUENO)
        self.assertEqual(entrada["id"], "wamid.k1")
        self.assertEqual(entrada["phone_number_id"], PHONE_ID)
        self.assertFalse(entrada["grupo"])

    def test_audio_e_imagen(self):
        audio = extraer_kapso(json.loads(evento_audio("a1")))
        self.assertEqual(audio["tipo"], "audio")
        self.assertEqual(audio["audio_id"], "audk1")
        imagen = extraer_kapso(json.loads(evento_imagen("i1")))
        self.assertEqual(imagen["tipo"], "image")
        self.assertEqual(imagen["imagen_id"], "imgk1")

    def test_direccion_saliente_o_pasivo_no_entra(self):
        saliente = json.loads(evento("cobra 0.01 al 5512345678"))
        saliente["message"]["kapso"]["direction"] = "outbound"
        self.assertEqual(extraer_kapso(saliente)["tipo"], "vacio")
        pasivo = json.loads(evento("cobra 0.01 al 5512345678"))
        pasivo["message"]["kapso"]["passive"] = True
        self.assertEqual(extraer_kapso(pasivo)["tipo"], "vacio")

    def test_sin_kapso_o_sin_mensaje_es_vacio(self):
        self.assertEqual(extraer_kapso({})["tipo"], "vacio")
        self.assertEqual(extraer_kapso({"conversation": {}})["tipo"], "vacio")
        sin_kapso = extraer_kapso(json.loads(evento("hola", sin_kapso=True)))
        self.assertEqual(sin_kapso["tipo"], "vacio")

    def test_grupo_y_otro_tipo(self):
        grupo = json.loads(evento("hola"))
        grupo["message"]["group_id"] = "120363@g.us"
        self.assertTrue(extraer_kapso(grupo)["grupo"])
        reaccion = json.loads(evento(""))
        reaccion["message"]["type"] = "reaction"
        reaccion["message"]["reaction"] = {"emoji": "👍"}
        self.assertEqual(extraer_kapso(reaccion)["tipo"], "otro")

    def test_sin_from_cae_al_telefono_de_la_conversacion(self):
        datos = json.loads(evento("hola"))
        datos["message"].pop("from")
        self.assertEqual(extraer_kapso(datos)["de"], DUENO)

    def test_sin_from_ni_conversacion_no_hay_remitente(self):
        datos = json.loads(evento("hola"))
        datos["message"].pop("from")
        datos.pop("conversation")
        self.assertIsNone(extraer_kapso(datos)["de"])


class DescargaKapsoTests(unittest.TestCase):
    def _bajar(self, falso, media_id="audk1"):
        with mock.patch("codi_informal.whatsapp._abrir", falso):
            return descargar_media(media_id, API_KEY, max_bytes=10, timeout=7,
                                   api="https://api.kapso.ai/meta/whatsapp/v24.0",
                                   auth={"X-API-Key": API_KEY}, hosts=("kapso.ai",))

    def test_pide_la_url_al_proxy_y_baja_con_x_api_key(self):
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            if req.full_url == "https://api.kapso.ai/meta/whatsapp/v24.0/audk1":
                return _Media(b'{"url": "https://api.kapso.ai/media/audk1"}')
            return _Media(b"BYTES-OGG")

        self.assertEqual(self._bajar(falso), b"BYTES-OGG")
        self.assertEqual([r.full_url for r in vistos], [
            "https://api.kapso.ai/meta/whatsapp/v24.0/audk1",
            "https://api.kapso.ai/media/audk1",
        ])
        for req in vistos:
            self.assertEqual(req.headers["X-api-key"], API_KEY)
            self.assertFalse(req.has_header("Authorization"))

    def test_url_que_no_es_de_kapso_no_se_baja(self):
        llamadas = []

        def falso(req, timeout=0):
            llamadas.append(req.full_url)
            if req.full_url.endswith("/audk1"):
                return _Media(b'{"url": "https://evil.test/steal"}')
            return _Media(b"x")

        self.assertIsNone(self._bajar(falso))
        self.assertEqual(llamadas, ["https://api.kapso.ai/meta/whatsapp/v24.0/audk1"])


class KapsoBase(Base):
    def levantar_kapso(self, **ajustes):
        return self.levantar(
            whatsapp_provider="kapso",
            kapso_api_key=API_KEY,
            kapso_phone_number_id=PHONE_ID,
            kapso_webhook_secret=WEBHOOK_SECRETO,
            **ajustes)

    def post_kapso(self, cuerpo, firmado=True, evento_tipo="whatsapp.message.received",
                   headers=None):
        h = {"Content-Type": "application/json"}
        if firmado:
            h["X-Webhook-Signature"] = firma_kapso(cuerpo)
        if evento_tipo:
            h["X-Webhook-Event"] = evento_tipo
        h.update(headers or {})
        req = urllib.request.Request(self.base + "/webhooks/whatsapp", data=cuerpo, headers=h)
        try:
            with urllib.request.build_opener().open(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code


class WebhookKapsoTests(KapsoBase):
    def test_firma_mala_o_faltante_401_sin_agente(self):
        self.levantar_kapso()
        self.assertEqual(self.post_kapso(evento("cobra 0.01 al 5512345678"), firmado=False), 401)
        self.assertEqual(
            self.post_kapso(evento("cobra 0.01 al 5512345678"), firmado=False,
                            headers={"X-Webhook-Signature": "00" * 32}), 401)
        self.assertEqual(self.pey.pushes, 0)

    def test_sin_secreto_401(self):
        self.levantar_kapso(kapso_webhook_secret="")
        self.assertEqual(self.post_kapso(evento("cobra 0.01 al 5512345678")), 401)
        self.assertEqual(self.pey.pushes, 0)

    def test_remitente_ajeno_403(self):
        self.levantar_kapso()
        self.assertEqual(
            self.post_kapso(evento("cobra 0.01 al 5512345678", de="5215599999999")), 403)
        self.assertEqual(self.pey.pushes, 0)

    def test_521_del_dueno_llega_al_agente(self):
        # el owner se guarda como 5500000001; Kapso puede mandar 5215500000001
        self.levantar_kapso()
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            return _Respuesta(b'{"id": "m1"}')

        with mock.patch("urllib.request.urlopen", falso):
            self.assertEqual(self.post_kapso(evento("qué se ha cobrado")), 200)
        self.assertEqual(textos(vistos), ["Todavía no entra ningún pago."])

    def test_envio_sale_por_el_proxy_de_kapso_con_x_api_key(self):
        self.levantar_kapso()
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            return _Respuesta(b'{"id": "m1"}')

        with mock.patch("urllib.request.urlopen", falso):
            self.assertEqual(self.post_kapso(evento("qué se ha cobrado")), 200)
        (req,) = vistos
        self.assertEqual(
            req.full_url,
            f"https://api.kapso.ai/meta/whatsapp/v24.0/{PHONE_ID}/messages")
        self.assertEqual(req.headers["X-api-key"], API_KEY)
        self.assertFalse(req.has_header("Authorization"))
        cuerpo = json.loads(req.data)
        self.assertEqual(cuerpo["messaging_product"], "whatsapp")
        self.assertEqual(cuerpo["type"], "text")

    def test_reintento_con_el_mismo_id_no_duplica(self):
        self.levantar_kapso()
        with _codigo_fijo():
            self.assertEqual(
                self.post_kapso(evento("cobra 0.01 al 5512345678", mid="d1")), 200)
        self.assertEqual(self.post_kapso(evento(f"confirmar {CODIGO}", mid="d1-ok")), 200)
        # Kapso reintenta si no ve 200: la reentrega del mismo id no arma otro cobro
        with _codigo_fijo():
            self.assertEqual(
                self.post_kapso(evento("cobra 0.01 al 5512345678", mid="d1")), 200)
        self.post_kapso(evento(f"confirmar {CODIGO}", mid="d1-ok"))
        self.assertEqual(self.pey.pushes, 1)

    def test_otro_evento_se_ignora(self):
        self.levantar_kapso()
        self.assertEqual(
            self.post_kapso(evento("cobra 0.01 al 5512345678"),
                            evento_tipo="whatsapp.message.delivered"), 200)
        self.assertEqual(self.pey.pushes, 0)

    def test_mensaje_saliente_no_cobra(self):
        self.levantar_kapso()
        datos = json.loads(evento("cobra 0.01 al 5512345678"))
        datos["message"]["kapso"]["direction"] = "outbound"
        self.assertEqual(self.post_kapso(json.dumps(datos).encode()), 200)
        self.assertEqual(self.pey.pushes, 0)

    def test_qr_sube_la_imagen_por_kapso(self):
        self.levantar_kapso()
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            return _Respuesta(b'{"id": "media1"}')

        with mock.patch("urllib.request.urlopen", falso):
            with _codigo_fijo():
                self.post_kapso(evento("manda el qr", mid="q1"))
            self.post_kapso(evento(f"confirmar {CODIGO}", mid="q2"))
        urls = [r.full_url for r in vistos]
        base = f"https://api.kapso.ai/meta/whatsapp/v24.0/{PHONE_ID}"
        self.assertTrue(any(u == base + "/media" for u in urls), urls)
        for req in vistos:
            self.assertEqual(req.headers["X-api-key"], API_KEY)
            self.assertFalse(req.has_header("Authorization"))
        imagenes = [json.loads(r.data) for r in vistos
                    if r.full_url == base + "/messages"
                    and json.loads(r.data).get("type") == "image"]
        self.assertEqual(len(imagenes), 1)
        self.assertEqual(imagenes[0]["image"]["id"], "media1")


class VozKapsoTests(KapsoBase):
    OGG = b"OggS\x00\x02" + (30 * 48000).to_bytes(8, "little") + b"\x00" * 20

    def _media(self, req, timeout=0):
        self.bajadas.append(req)
        if req.full_url == "https://api.kapso.ai/meta/whatsapp/v24.0/audk1":
            return _Media(b'{"url": "https://api.kapso.ai/media/audk1"}')
        return _Media(self.OGG)

    def _red(self, enviados, transcript="cobra 0.01 al 5512345678"):
        def falso(req, timeout=0):
            if "openrouter" in req.full_url:
                if transcript is None:
                    raise urllib.error.URLError("caido")
                return _Resp(json.dumps(
                    {"choices": [{"message": {"content": transcript}}]}).encode())
            enviados.append(req)
            return _Resp(b'{"id": "m1"}')
        return falso

    def test_nota_de_voz_baja_por_kapso_y_cobra_lo_mismo(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "key-or"}):
            self.levantar_kapso()
            self.bajadas = []
            enviados = []
            with mock.patch("urllib.request.urlopen", self._red(enviados)), \
                    mock.patch("codi_informal.whatsapp._abrir", self._media):
                with _codigo_fijo():
                    self.assertEqual(self.post_kapso(evento_audio("v1")), 200)
                self.assertEqual(
                    self.post_kapso(evento(f"confirmar {CODIGO}", mid="v2")), 200)
            self.assertEqual([r.full_url for r in self.bajadas], [
                "https://api.kapso.ai/meta/whatsapp/v24.0/audk1",
                "https://api.kapso.ai/media/audk1",
            ])
            for req in self.bajadas:
                self.assertEqual(req.headers["X-api-key"], API_KEY)
            self.assertIn("confirmar", textos(enviados)[0])
            self.assertEqual(self.pey.pushes, 1)

    def test_url_de_medio_fuera_de_kapso_no_se_baja(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "key-or"}):
            self.levantar_kapso()
            bajadas = []
            enviados = []

            def media_rara(req, timeout=0):
                bajadas.append(req.full_url)
                if req.full_url.endswith("/audk1"):
                    return _Media(b'{"url": "https://evil.test/aud"}')
                return _Media(self.OGG)

            with mock.patch("urllib.request.urlopen", self._red(enviados, transcript=None)), \
                    mock.patch("codi_informal.whatsapp._abrir", media_rara):
                self.assertEqual(self.post_kapso(evento_audio("v3")), 200)
            self.assertEqual(bajadas, ["https://api.kapso.ai/meta/whatsapp/v24.0/audk1"])
            self.assertIn("nota de voz", textos(enviados)[0])
            self.assertEqual(self.pey.pushes, 0)


class TicketKapsoTests(KapsoBase):
    JPEG = b"\xff\xd8JPEG-KAPSO-PRUEBA-7841"

    def test_foto_de_ticket_baja_por_kapso_y_se_lee(self):
        def media(req, timeout=0):
            if req.full_url == "https://api.kapso.ai/meta/whatsapp/v24.0/imgk1":
                return _Media(b'{"url": "https://api.kapso.ai/media/imgk1"}')
            return _Media(self.JPEG)

        enviados = []

        def red(req, timeout=0):
            if "openrouter" in req.full_url:
                return _Resp(json.dumps({"choices": [{"message": {"content":
                    '{"monto": "0.01", "concepto": "Tacos"}'}}]}).encode())
            enviados.append(req)
            return _Resp(b'{"id": "m1"}')

        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "key-or"}):
            self.levantar_kapso()
            with mock.patch("urllib.request.urlopen", red), \
                    mock.patch("codi_informal.whatsapp._abrir", media):
                self.assertEqual(self.post_kapso(evento_imagen("i1")), 200)
            self.assertEqual(textos(enviados)[0],
                             "Leí $0.01 por Tacos. Para cobrarlo escribe: cobra 0.01 al <teléfono>")
            self.assertEqual(self.pey.pushes, 0)


if __name__ == "__main__":
    unittest.main()
