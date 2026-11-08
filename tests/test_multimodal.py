import os
import unittest
from decimal import Decimal

from codi_informal import idioma, ticket, voz


class VozTests(unittest.TestCase):
    def test_transcribe_y_borra_el_temporal(self):
        vistos = []

        def transcriptor(ruta):
            vistos.append(ruta)
            self.assertTrue(os.path.exists(ruta))
            return "cobra 0.01 al 5512345678"

        texto = voz.transcribir("abc123", descargar=lambda i, **k: b"x" * 10, transcriptor=transcriptor)
        self.assertEqual(texto, "cobra 0.01 al 5512345678")
        self.assertFalse(os.path.exists(vistos[0]))

    def test_borra_el_temporal_si_el_transcriptor_falla(self):
        vistos = []

        def transcriptor(ruta):
            vistos.append(ruta)
            raise RuntimeError("boom")

        self.assertIsNone(voz.transcribir("abc", descargar=lambda i, **k: b"x", transcriptor=transcriptor))
        self.assertFalse(os.path.exists(vistos[0]))

    def test_sin_transcriptor_devuelve_none_sin_descargar(self):
        def descargar(*a, **k):
            raise AssertionError("no debe descargar")

        self.assertIsNone(voz.transcribir("abc", descargar=descargar, transcriptor=None))

    def test_rechaza_urls_y_ids_raros(self):
        def descargar(*a, **k):
            raise AssertionError("no debe descargar")

        for malo in ("http://evil.test/a.ogg", "../etc/passwd", "a/b", "", "x" * 300):
            self.assertIsNone(voz.transcribir(malo, descargar=descargar, transcriptor=lambda r: "hola"))

    def test_rechaza_mas_de_5mb(self):
        t = lambda r: self.fail("no debe transcribir")
        grande = b"x" * (5 * 1024 * 1024 + 1)
        self.assertIsNone(voz.transcribir("abc", descargar=lambda i, **k: grande, transcriptor=t))

    def test_rechaza_mas_de_60s(self):
        t = lambda r: self.fail("no debe transcribir")
        self.assertIsNone(
            voz.transcribir("abc", descargar=lambda i, **k: b"x", transcriptor=t, duracion=lambda r: 61)
        )

    def test_pasa_timeout_y_tope_a_descargar_y_tolera_fallos(self):
        pedido = {}

        def descargar(i, **k):
            pedido.update(k)
            raise TimeoutError

        self.assertIsNone(voz.transcribir("abc", descargar=descargar, transcriptor=lambda r: "x"))
        self.assertEqual(pedido["max_bytes"], 5 * 1024 * 1024)
        self.assertGreater(pedido["timeout"], 0)

    def test_transcripcion_vacia_es_none(self):
        self.assertIsNone(voz.transcribir("abc", descargar=lambda i, **k: b"x", transcriptor=lambda r: "  "))


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
            self.assertNotEqual(idioma.mensaje(clave, "es"), idioma.mensaje(clave, "en"))

    def test_tope_se_formatea(self):
        self.assertIn("0.01", idioma.mensaje("TOPE", "en", tope="0.01"))
        self.assertIn("0.01", idioma.mensaje("TOPE", "es", tope="0.01"))


class TicketTests(unittest.TestCase):
    def test_lee_monto_y_concepto(self):
        r = ticket.leer(b"img", lector=lambda b: {"monto": "125.50", "concepto": "Tacos"})
        self.assertEqual(r, {"monto": Decimal("125.50"), "concepto": "Tacos"})

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


if __name__ == "__main__":
    unittest.main()
