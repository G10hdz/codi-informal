import json
import os
import re
import tempfile
import threading
import unittest
import urllib.request
from decimal import Decimal

from codi_informal.agente import Agente
from codi_informal.confirmacion import Confirmaciones
from codi_informal.pey import Pey, PeyError, centavos, tope_centavos
from codi_informal.registro import abrir, registrar_pago
from codi_informal.server import Config, servir
from tests.test_esqueleto import SECRETO, firmar

TEL = "5512345678"


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        self.conn = abrir(os.path.join(self.carpeta.name, "r.sqlite"))
        self.llamadas = []
        self.estado_al_llamar = []
        self.reloj = Reloj()
        self.error = None
        self.pey = Pey("key-de-prueba", max_amount="0.01", transport=self._transport,
                       bank_account_id="01ABCDEFGHJKMNPQRSTVWXYZ00")

    def _transport(self, method, path, crudo, headers):
        self.llamadas.append((path, json.loads(crudo)))
        filas = self.conn.execute("select estado from operaciones").fetchall()
        self.estado_al_llamar.append([f["estado"] for f in filas])
        if self.error:
            raise self.error
        if path == "/codi/qr":
            return 201, json.dumps({"id": "qr1", "qrString": "x", "qrImage": None}).encode()
        return 200, json.dumps({"transactionId": "tx1", "codiId": "123"}).encode()

    def agente(self, pey="default", conn="default", max_amount="0.01"):
        return Agente(self.pey if pey == "default" else pey,
                      self.conn if conn == "default" else conn,
                      max_amount=max_amount, reloj=self.reloj)

    def codigo(self, resultado):
        m = re.search(r"confirmar ([0-9A-F]{6})", resultado.texto)
        self.assertIsNotNone(m, resultado.texto)
        return m.group(1)

    def op(self):
        return self.conn.execute("select * from operaciones").fetchone()


class DineroTests(unittest.TestCase):
    def test_centavos_enteros(self):
        self.assertEqual(centavos("0.01"), 1)
        self.assertEqual(centavos("0,01"), 1)
        self.assertEqual(centavos("1"), 100)
        self.assertEqual(centavos(0.01), 1)
        self.assertEqual(centavos(Decimal("0.01")), 1)

    def test_rechaza_en_vez_de_redondear(self):
        for malo in ["0.005", "0.001", "-0.01", "nan", "inf", "-inf", "1e-2", "1,000", "1.000,5",
                     "", " ", "abc", "0x10", True, float("nan"), float("inf"), Decimal("0.005"), None]:
            with self.subTest(malo=malo):
                with self.assertRaises(ValueError):
                    centavos(malo)

    def test_tope(self):
        self.assertEqual(tope_centavos(None), 1)
        self.assertEqual(tope_centavos("0.01"), 1)
        for malo in ["0.02", "1", "abc", "", "0", "0.005", "-1"]:
            with self.subTest(malo=malo):
                self.assertIsNone(tope_centavos(malo))


class MontoEnAgenteTests(Base):
    def test_fraccion_de_centavo_se_rechaza_sin_llamar_a_pey(self):
        for monto in ["0.005", "0.001", "-0.01", "0"]:
            r = self.agente().responder(f"cobra {monto} al {TEL}")
            self.assertNotIn("confirmar", r.texto)
        self.assertEqual(self.llamadas, [])

    def test_tope_invalido_o_alto_deshabilita_cobros(self):
        for tope in ["0.02", "abc", "", "0"]:
            r = self.agente(max_amount=tope).responder(f"cobra 0.01 al {TEL}")
            self.assertIn("deshabilitad", r.texto)
            self.assertNotIn("confirmar", r.texto)
        self.assertEqual(self.llamadas, [])
        pey = Pey("k", max_amount="0.02", transport=self._transport)
        with self.assertRaises(PeyError):
            pey.push(amount="0.01", phone=TEL, concept="x")
        self.assertEqual(self.llamadas, [])

    def test_monto_arriba_del_tope(self):
        r = self.agente().responder(f"cobra 0.02 al {TEL}")
        self.assertIn("tope", r.texto)
        self.assertEqual(self.llamadas, [])


class ConfirmacionTests(Base):
    def test_pide_confirmacion_antes_de_llamar_a_pey(self):
        a = self.agente()
        r = a.responder(f"cobra 0.01 al {TEL}", dueno="d1", chat="c1")
        self.assertIn(TEL, r.texto)
        self.assertIn("0.01", r.texto)
        self.assertEqual(self.llamadas, [])
        c = self.codigo(r)
        r2 = a.responder(f"confirmar {c}", dueno="d1", chat="c1")
        self.assertEqual(len(self.llamadas), 1)
        self.assertIn("123", r2.texto)

    def test_un_solo_uso(self):
        a = self.agente()
        c = self.codigo(a.responder(f"cobra 0.01 al {TEL}", dueno="d1", chat="c1"))
        a.responder(f"confirmar {c}", dueno="d1", chat="c1")
        a.responder(f"confirmar {c}", dueno="d1", chat="c1")
        self.assertEqual(len(self.llamadas), 1)

    def test_si_ambiguo_no_ejecuta(self):
        a = self.agente()
        a.responder(f"cobra 0.01 al {TEL}", dueno="d1", chat="c1")
        a.responder("sí", dueno="d1", chat="c1")
        a.responder("confirmar", dueno="d1", chat="c1")
        self.assertEqual(self.llamadas, [])

    def test_ligada_a_dueno_y_chat(self):
        a = self.agente()
        c = self.codigo(a.responder(f"cobra 0.01 al {TEL}", dueno="d1", chat="c1"))
        a.responder(f"confirmar {c}", dueno="d2", chat="c1")
        a.responder(f"confirmar {c}", dueno="d1", chat="c2")
        self.assertEqual(self.llamadas, [])
        a.responder(f"confirmar {c}", dueno="d1", chat="c1")
        self.assertEqual(len(self.llamadas), 1)

    def test_vence_en_dos_minutos(self):
        a = self.agente()
        c = self.codigo(a.responder(f"cobra 0.01 al {TEL}", dueno="d1", chat="c1"))
        self.reloj.t += 121
        r = a.responder(f"confirmar {c}", dueno="d1", chat="c1")
        self.assertEqual(self.llamadas, [])
        self.assertIn("venci", r.texto)

    def test_borrador_nuevo_invalida_el_anterior(self):
        a = self.agente()
        c1 = self.codigo(a.responder(f"cobra 0.01 al {TEL}", dueno="d1", chat="c1"))
        c2 = self.codigo(a.responder("cobra 0.01 al 5598765432", dueno="d1", chat="c1"))
        a.responder(f"confirmar {c1}", dueno="d1", chat="c1")
        self.assertEqual(self.llamadas, [])
        a.responder(f"confirmar {c2}", dueno="d1", chat="c1")
        self.assertEqual(self.llamadas[0][1]["phoneNumber"], "5598765432")

    def test_cambiar_un_dato_invalida(self):
        c = Confirmaciones(reloj=self.reloj)
        codigo = c.crear("d", "c", {"monto": 1, "tel": TEL})
        self.assertIsNone(c.consumir("d", "c", codigo, {"monto": 1, "tel": "5500000000"}))
        self.assertIsNone(c.consumir("d", "c", codigo, {"monto": 1, "tel": TEL}))

    def test_consumo_atomico_con_hilos(self):
        c = Confirmaciones(reloj=self.reloj)
        codigo = c.crear("d", "c", {"x": 1})
        ganadores = []

        def intento():
            if c.consumir("d", "c", codigo) is not None:
                ganadores.append(1)

        hilos = [threading.Thread(target=intento) for _ in range(20)]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        self.assertEqual(len(ganadores), 1)

    def test_qr_tambien_pide_confirmacion_y_va_con_monto_fijo(self):
        a = self.agente()
        r = a.responder("manda el qr del puesto", dueno="d1", chat="c1")
        self.assertEqual(self.llamadas, [])
        a.responder(f"confirmar {self.codigo(r)}", dueno="d1", chat="c1")
        path, cuerpo = self.llamadas[0]
        self.assertEqual(path, "/codi/qr")
        self.assertEqual(cuerpo["amount"], 0.01)


class OperacionTests(Base):
    def cobrar_y_confirmar(self, a):
        r = a.cobrar(TEL, "0.01", "Taco", dueno="d1", chat="c1")
        return a.responder(f"confirmar {self.codigo(r)}", dueno="d1", chat="c1")

    def test_cobrar_es_el_punto_de_entrada(self):
        a = self.agente()
        r = a.cobrar(TEL, "0.01", "Taco", dueno="d1", chat="c1")
        self.assertEqual(self.llamadas, [])
        self.cobrar_y_confirmar(a)
        self.assertEqual(self.llamadas[0][1]["concept"], "Taco")
        self.assertIn("no cobra", a.cobrar("123", "0.01", "x").texto.lower() + "no cobra")
        self.assertNotIn("confirmar", a.cobrar("123", "0.01", "x").texto)
        self.assertNotIn("confirmar", a.cobrar(TEL, "0.005", "x").texto)

    def test_guarda_la_operacion_antes_de_llamar_a_pey(self):
        self.cobrar_y_confirmar(self.agente())
        self.assertEqual(self.estado_al_llamar, [["creando"]])
        op = self.op()
        self.assertEqual(op["estado"], "creada")
        self.assertEqual(op["pey_transaction_id"], "tx1")
        self.assertEqual(op["amount_cents"], 1)
        self.assertEqual(self.llamadas[0][1]["numRef"], op["num_ref"])

    def test_timeout_queda_incierto_sin_reintento(self):
        self.error = TimeoutError("lento")
        r = self.cobrar_y_confirmar(self.agente())
        self.assertEqual(len(self.llamadas), 1)
        self.assertEqual(self.op()["estado"], "incierto")
        self.assertIn("no sé", r.texto.lower())

    def test_error_de_pey_queda_fallida(self):
        self.error = None
        self.pey.transport = lambda *a: (400, b'{"error":{"message":"mal"}}')
        self.cobrar_y_confirmar(self.agente())
        self.assertEqual(self.op()["estado"], "fallida")

    def test_sin_registro_no_se_cobra(self):
        a = self.agente(conn=None)
        r = a.cobrar(TEL, "0.01", "x", dueno="d1", chat="c1")
        self.assertNotIn("confirmar", r.texto)
        self.assertEqual(self.llamadas, [])


class ConciliacionTests(Base):
    def evento(self, **extra):
        e = {"type": "codi.pn.payment_received", "amount": 0.01, "concept": "Taco",
             "transactionId": "tx1", "metadata": {"clabe": "000000000000000000"}}
        e.update(extra)
        return e

    def creada(self, qr=False):
        a = self.agente()
        r = a.responder("manda el qr del puesto" if qr else f"cobra 0.01 al {TEL}", dueno="d", chat="c")
        a.responder(f"confirmar {self.codigo(r)}", dueno="d", chat="c")

    def test_coincide_queda_pagado(self):
        self.creada()
        registrar_pago(self.conn, self.evento(), "w1")
        self.assertEqual(self.op()["estado"], "pagado")

    def test_monto_distinto_queda_pendiente(self):
        self.creada()
        registrar_pago(self.conn, self.evento(amount=0.02), "w1")
        self.assertEqual(self.op()["estado"], "pendiente")

    def test_cuenta_distinta_queda_pendiente(self):
        self.creada()
        registrar_pago(self.conn, self.evento(bankAccountId="01ZZZZZZZZZZZZZZZZZZZZZZZZ"), "w1")
        self.assertEqual(self.op()["estado"], "pendiente")

    def test_cuenta_igual_coincide(self):
        self.creada()
        registrar_pago(self.conn, self.evento(bankAccountId="01ABCDEFGHJKMNPQRSTVWXYZ00"), "w1")
        self.assertEqual(self.op()["estado"], "pagado")

    def test_transaccion_desconocida_no_toca_operaciones(self):
        self.creada()
        registrar_pago(self.conn, self.evento(transactionId="otra"), "w1")
        self.assertEqual(self.op()["estado"], "creada")

    def test_qr_se_concilia_por_codi_qr_id(self):
        self.creada(qr=True)
        registrar_pago(self.conn, self.evento(type="codi.qr.payment_received", codiQrId="qr1",
                                              transactionId="txq"), "w1")
        self.assertEqual(self.op()["estado"], "pagado")

    def test_no_guarda_clabe(self):
        self.creada()
        registrar_pago(self.conn, self.evento(), "w1")
        self.conn.commit()
        self.assertNotIn(b"000000000000000000", open(os.path.join(self.carpeta.name, "r.sqlite"), "rb").read())


class ServidorTests(unittest.TestCase):
    def arrancar(self, secreto):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        config = Config()
        config.pey_api_key = ""
        config.pey_webhook_secret = secreto
        config.whatsapp_token = ""
        config.owner_whatsapp = ""
        config.registro_path = os.path.join(carpeta.name, "r.sqlite")
        config.host = "127.0.0.1"
        config.port = 0
        config.max_amount = "0.01"
        httpd = servir(config)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        return f"http://127.0.0.1:{httpd.server_address[1]}", config

    def test_req5_webhook_sin_secreto_da_401_y_no_escribe(self):
        base, config = self.arrancar("")
        crudo = json.dumps({"type": "codi.pn.payment_received", "amount": 0.01,
                            "transactionId": "tx"}).encode()
        headers = firmar(crudo)
        headers["Content-Type"] = "application/json"
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(urllib.request.Request(base + "/webhooks/pey", data=crudo, headers=headers))
        self.assertEqual(ctx.exception.code, 401)
        self.assertEqual(abrir(config.registro_path).execute("select count(*) from pagos").fetchone()[0], 0)

    def test_req6_mensaje_sin_key_dice_que_no_lo_envio(self):
        base, _ = self.arrancar(SECRETO)
        pedido = urllib.request.Request(base + "/mensaje",
                                        data=json.dumps({"texto": f"cobra 0.01 al {TEL}"}).encode(),
                                        headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(pedido))
        self.assertIn("Falta PEY_API_KEY", r["texto"])
        self.assertIn(TEL, r["texto"])


class Req3Tests(Base):
    def test_qr_en_cero_no_llega_a_pey(self):
        with self.assertRaises(PeyError):
            self.pey.qr(amount="0", concept="x")
        r = self.agente(max_amount="0").responder("manda el qr del puesto", dueno="d", chat="c")
        self.assertNotIn("confirmar", r.texto)
        self.assertEqual(self.llamadas, [])


if __name__ == "__main__":
    unittest.main()
