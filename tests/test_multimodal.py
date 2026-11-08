import base64
import json
import os
import tempfile
import unittest
import urllib.error
from decimal import Decimal
from unittest import mock

from codi_informal import idioma, openrouter, ticket, voz

ENV_OR = {"OPENROUTER_API_KEY": "key-openrouter-prueba"}


class _Resp:
    def __init__(self, datos):
        self._d = datos

    def read(self, n=-1):
        return self._d if n is None or n < 0 else self._d[:n]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def close(self):
        pass


def _completar(texto):
    return _Resp(json.dumps({"choices": [{"message": {"content": texto}}]}).encode())


class VozTests(unittest.TestCase):
    def test_transcribe_y_borra_el_temporal(self):
        vistos = []

        def transcriptor(ruta):
            vistos.append(ruta)
            self.assertTrue(os.path.exists(ruta))
            return "cobra 0.01 al 5512345678"

        texto = voz.transcribir("abc123", descargar=lambda i, **k: b"x" * 10, transcriptor=transcriptor,
                                duracion=lambda r: 30)
        self.assertEqual(texto, "cobra 0.01 al 5512345678")
        self.assertFalse(os.path.exists(vistos[0]))

    def test_borra_el_temporal_si_el_transcriptor_falla(self):
        vistos = []

        def transcriptor(ruta):
            vistos.append(ruta)
            raise RuntimeError("boom")

        self.assertIsNone(voz.transcribir("abc", descargar=lambda i, **k: b"x", transcriptor=transcriptor,
                                          duracion=lambda r: 30))
        self.assertFalse(os.path.exists(vistos[0]))

    def test_sin_transcriptor_devuelve_none_sin_descargar(self):
        def descargar(*a, **k):
            raise AssertionError("no debe descargar")

        self.assertIsNone(voz.transcribir("abc", descargar=descargar, transcriptor=None))

    def test_rechaza_urls_y_ids_raros(self):
        descargar = mock.Mock(return_value=b"x")
        for malo in ("http://evil.test/a.ogg", "../etc/passwd", "a/b", "", "x" * 300):
            self.assertIsNone(voz.transcribir(malo, descargar=descargar, transcriptor=lambda r: "hola",
                                              duracion=lambda r: 30))
        descargar.assert_not_called()

    def test_rechaza_mas_de_5mb(self):
        t = mock.Mock(return_value="hola")
        grande = b"x" * (5 * 1024 * 1024 + 1)
        self.assertIsNone(voz.transcribir("abc", descargar=lambda i, **k: grande, transcriptor=t,
                                          duracion=lambda r: 30))
        t.assert_not_called()

    def test_rechaza_mas_de_60s(self):
        t = mock.Mock(return_value="hola")
        self.assertIsNone(
            voz.transcribir("abc", descargar=lambda i, **k: b"x", transcriptor=t, duracion=lambda r: 61)
        )
        t.assert_not_called()

    def test_sin_duracion_no_transcribe(self):
        t = mock.Mock(return_value="hola")
        self.assertIsNone(voz.transcribir("abc", descargar=lambda i, **k: b"x", transcriptor=t))
        t.assert_not_called()

    def test_duracion_inverificable_no_transcribe(self):
        t = mock.Mock(return_value="hola")

        def falla(ruta):
            raise RuntimeError("no se pudo verificar")

        for duracion in (lambda r: float("nan"), lambda r: -5, lambda r: "largo", falla):
            self.assertIsNone(voz.transcribir("abc", descargar=lambda i, **k: b"x", transcriptor=t,
                                              duracion=duracion))
            t.assert_not_called()

    def test_pasa_timeout_y_tope_a_descargar_y_tolera_fallos(self):
        pedido = {}

        def descargar(i, **k):
            pedido.update(k)
            raise TimeoutError

        self.assertIsNone(voz.transcribir("abc", descargar=descargar, transcriptor=lambda r: "x",
                                          duracion=lambda r: 30))
        self.assertEqual(pedido["max_bytes"], 5 * 1024 * 1024)
        self.assertGreater(pedido["timeout"], 0)

    def test_transcripcion_vacia_es_none(self):
        self.assertIsNone(voz.transcribir("abc", descargar=lambda i, **k: b"x", transcriptor=lambda r: "  ",
                                          duracion=lambda r: 30))


class DuracionTests(unittest.TestCase):
    def _escribe(self, datos):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        self.addCleanup(lambda: os.path.exists(f.name) and os.remove(f.name))
        f.write(datos)
        f.close()
        return f.name

    def _pagina(self, granule):
        return b"OggS\x00\x02" + granule.to_bytes(8, "little") + b"\x00" * 13 + b"\x03xx"

    def test_granule_de_la_ultima_pagina_a_48k(self):
        ruta = self._escribe(self._pagina(48000) + b"ruidoxx" + self._pagina(96000))
        self.assertEqual(voz.duracion(ruta), 2.0)

    def test_medio_segundo(self):
        self.assertEqual(voz.duracion(self._escribe(self._pagina(24000))), 0.5)

    def test_no_ogg_incompleto_o_inexistente_es_none(self):
        self.assertIsNone(voz.duracion(self._escribe(b"mp3 basura")))
        self.assertIsNone(voz.duracion(self._escribe(b"OggS\x00\x02" + b"\x00" * 4)))
        self.assertIsNone(voz.duracion(self._escribe(b"")))
        self.assertIsNone(voz.duracion("/no/existe/audio.ogg"))

    def test_oggs_falso_dentro_del_payload_no_estorba(self):
        datos = self._pagina(48000) + b"OggS\x99" + b"\x00" * 20
        self.assertEqual(voz.duracion(self._escribe(datos)), 1.0)


class IdiomaTests(unittest.TestCase):
    def test_detecta_es_y_en(self):
        self.assertEqual(idioma.detectar("cobra 0.01 al 5512345678 por favor"), "es")
        self.assertEqual(idioma.detectar("please charge 0.01 to 5512345678 for the order"), "en")

    def test_ambiguo_o_desconocido_es_none_y_cae_en_es(self):
        for t in ("", "5512345678", "qr", "ok"):
            self.assertIsNone(idioma.detectar(t))
        self.assertEqual(idioma.mensaje("AYUDA", None), idioma.mensaje("AYUDA", "es"))
        self.assertEqual(idioma.mensaje("AYUDA", "fr"), idioma.mensaje("AYUDA", "es"))

    def test_mensajes_en_ambos_idiomas_para_cada_clave(self):
        for clave in ("AYUDA", "TOPE", "CELULAR", "VOZ_SIN_TRANSCRIPCION"):
            self.assertNotEqual(idioma.mensaje(clave, "es", tope="1"), idioma.mensaje(clave, "en", tope="1"))

    def test_tope_se_formatea(self):
        self.assertIn("0.01", idioma.mensaje("TOPE", "en", tope="0.01"))
        self.assertIn("0.01", idioma.mensaje("TOPE", "es", tope="0.01"))


class TicketTests(unittest.TestCase):
    def test_lee_monto_y_concepto(self):
        r = ticket.leer(b"img", lector=lambda b: {"monto": "125.50", "concepto": "Tacos"})
        self.assertEqual(r, {"monto": Decimal("125.50"), "concepto": "Tacos"})

    def test_acepta_solo_formatos_de_dinero_explicitos(self):
        casos = {
            "12": Decimal("12"),
            "12.50": Decimal("12.50"),
            "1,234.50": Decimal("1234.50"),
            "1234": Decimal("1234"),
            "1,234": Decimal("1234"),
            "12,345,678.90": Decimal("12345678.90"),
        }
        for crudo, esperado in casos.items():
            r = ticket.leer(b"i", lector=lambda b, c=crudo: {"monto": c, "concepto": "x"})
            self.assertEqual(r["monto"], esperado)

    def test_rechaza_montos_ambiguos(self):
        for malo in ("0,01", "1,2,3", "12.5", "12,34", "1,23,456", "1.234", ".50",
                     "12.", "1e2", "+5", "1 234.50"):
            self.assertIsNone(ticket.leer(b"i", lector=lambda b, c=malo: {"monto": c, "concepto": "x"}))

    def test_montos_extremos_o_no_finitos_no_levantan(self):
        for malo in ("1e100", "NaN", "Infinity", "9" * 40):
            self.assertIsNone(ticket.leer(b"i", lector=lambda b, c=malo: {"monto": c, "concepto": "x"}))

    def test_sin_monto_o_monto_invalido_es_none(self):
        for crudo in ({}, {"monto": ""}, {"monto": "abc"}, {"monto": "0"}, {"monto": "-5"},
                      {"monto": "NaN"}, {"monto": "Infinity"}, {"monto": "1.005"}):
            self.assertIsNone(ticket.leer(b"img", lector=lambda b, c=crudo: c))
        self.assertIsNone(ticket.leer(b"img", lector=lambda b: None))

    def test_lector_que_falla_es_none(self):
        def lector(b):
            raise RuntimeError

        self.assertIsNone(ticket.leer(b"img", lector=lector))
        self.assertIsNone(ticket.leer(b"", lector=lambda b: {"monto": "1"}))

    def test_quita_numeros_de_cuenta_del_concepto(self):
        r = ticket.leer(b"i", lector=lambda b: {"monto": "10", "concepto": "Pago 012345678901234567 tacos 5512345678"})
        self.assertNotRegex(r["concepto"], r"\d{8,}")
        self.assertIn("tacos", r["concepto"])

    def test_concepto_vacio_usa_valor_neutro(self):
        r = ticket.leer(b"i", lector=lambda b: {"monto": "10", "concepto": "  "})
        self.assertEqual(r["concepto"], "Ticket")


class OpenRouterTests(unittest.TestCase):
    def _audio(self, datos=b"OggS-audio-de-prueba"):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".ogg")
        self.addCleanup(lambda: os.path.exists(f.name) and os.remove(f.name))
        f.write(datos)
        f.close()
        return f.name

    def test_transcriptor_manda_audio_ogg_y_devuelve_el_texto(self):
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            return _completar("cobra 0.01 al 5512345678")

        with mock.patch.dict(os.environ, ENV_OR):
            with mock.patch("urllib.request.urlopen", falso):
                texto = openrouter.transcriptor(self._audio())
        self.assertEqual(texto, "cobra 0.01 al 5512345678")
        (req,) = vistos
        self.assertEqual(req.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(req.headers["Authorization"], "Bearer key-openrouter-prueba")
        cuerpo = json.loads(req.data)
        self.assertEqual(cuerpo["model"], "google/gemini-2.5-flash-lite")
        (parte_texto, parte_audio) = cuerpo["messages"][0]["content"]
        self.assertEqual(parte_texto["type"], "text")
        self.assertEqual(parte_audio["type"], "input_audio")
        self.assertEqual(parte_audio["input_audio"]["format"], "ogg")
        self.assertEqual(parte_audio["input_audio"]["data"],
                         base64.b64encode(b"OggS-audio-de-prueba").decode())

    def test_modelo_viene_del_env(self):
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            return _completar("hola")

        env = {**ENV_OR, "OPENROUTER_MODEL": "otro/modelo-1"}
        with mock.patch.dict(os.environ, env):
            with mock.patch("urllib.request.urlopen", falso):
                openrouter.transcriptor(self._audio())
        self.assertEqual(json.loads(vistos[0].data)["model"], "otro/modelo-1")

    def test_sin_llave_no_llama_a_la_red(self):
        def falso(req, timeout=0):
            raise AssertionError("no debe llamar")

        with mock.patch.dict(os.environ) as env:
            env.pop("OPENROUTER_API_KEY", None)
            with mock.patch("urllib.request.urlopen", falso):
                self.assertIsNone(openrouter.transcriptor(self._audio()))
                self.assertIsNone(openrouter.lector(b"jpg"))

    def test_transcriptor_tolera_fallos_y_respuestas_raras(self):
        casos = [
            lambda req, timeout=0: (_ for _ in ()).throw(urllib.error.URLError("caido")),
            lambda req, timeout=0: _Resp(b"no json"),
            lambda req, timeout=0: _Resp(b"{}"),
            lambda req, timeout=0: _Resp(b'{"choices": []}'),
            lambda req, timeout=0: _completar(""),
        ]
        with mock.patch.dict(os.environ, ENV_OR):
            for falso in casos:
                with mock.patch("urllib.request.urlopen", falso):
                    self.assertIsNone(openrouter.transcriptor(self._audio()))

    def test_lector_devuelve_monto_y_concepto(self):
        vistos = []

        def falso(req, timeout=0):
            vistos.append(req)
            return _completar('{"monto": "125.50", "concepto": "Tacos"}')

        with mock.patch.dict(os.environ, ENV_OR):
            with mock.patch("urllib.request.urlopen", falso):
                r = openrouter.lector(b"\xff\xd8jpg-de-prueba")
        self.assertEqual(r, {"monto": "125.50", "concepto": "Tacos"})
        cuerpo = json.loads(vistos[0].data)
        (parte_texto, parte_img) = cuerpo["messages"][0]["content"]
        self.assertEqual(parte_img["type"], "image_url")
        esperado = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8jpg-de-prueba").decode()
        self.assertEqual(parte_img["image_url"]["url"], esperado)
        self.assertIn("monto", parte_texto["text"])

    def test_lector_acepta_json_entre_cercos(self):
        def falso(req, timeout=0):
            return _completar('```json\n{"monto": "0.01", "concepto": "Torta"}\n```')

        with mock.patch.dict(os.environ, ENV_OR):
            with mock.patch("urllib.request.urlopen", falso):
                self.assertEqual(openrouter.lector(b"j"), {"monto": "0.01", "concepto": "Torta"})

    def test_lector_rechaza_prosa_y_campos_faltantes(self):
        def falso(texto):
            return lambda req, timeout=0: _completar(texto)

        malos = ["el total es 0.01", '{"total": "0.01"}', "[]", '"0.01"', '{"monto": "0.01"}']
        with mock.patch.dict(os.environ, ENV_OR):
            for malo in malos:
                with mock.patch("urllib.request.urlopen", falso(malo)):
                    self.assertIsNone(openrouter.lector(b"j"), malo)

    def test_lector_tolera_fallos(self):
        def falso(req, timeout=0):
            raise urllib.error.URLError("caido")

        with mock.patch.dict(os.environ, ENV_OR):
            with mock.patch("urllib.request.urlopen", falso):
                self.assertIsNone(openrouter.lector(b"j"))


if __name__ == "__main__":
    unittest.main()
