"""La libreta del dueño: cuánto se cobró hoy o en la última semana."""

import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from codi_informal.agente import Agente
from codi_informal.registro import abrir


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
        self.reloj = Reloj()
        self.fecha = lambda: datetime(2026, 11, 8, 15, 30)  # local, fija para no depender del reloj
        self.agente = Agente(None, self.conn, reloj=self.reloj, fecha=self.fecha)

    def insertar(self, tx, amount, concept, hace_horas=1):
        creado = (self.fecha() - timedelta(hours=hace_horas)).astimezone(timezone.utc)
        self.conn.execute(
            "insert into pagos (transaction_id, tipo, amount, concept, date_paid, created_at)"
            " values (?, 'codi.pn.payment_received', ?, ?, 0, ?)",
            (tx, amount, concept, creado.isoformat()),
        )
        self.conn.commit()


class LibretaTests(Base):
    def test_resumen_de_hoy_cuenta_y_suma(self):
        self.insertar("tx1", "1.50", "Taco", hace_horas=1)
        self.insertar("tx2", "2.00", "Soda", hace_horas=2)
        for frase in ("que cobre hoy", "qué cobré hoy", "cuánto cobré", "resumen", "libreta"):
            with self.subTest(frase=frase):
                r = self.agente.responder(frase)
                self.assertIn("Hoy entraron 2 pagos por $3.50", r.texto)
                self.assertIn("· $1.50 Taco", r.texto)
                self.assertIn("· $2.00 Soda", r.texto)

    def test_sin_pagos_hoy(self):
        r = self.agente.responder("que cobre hoy")
        self.assertEqual(r.texto, "Hoy no ha entrado ningún pago.")

    def test_no_filtra_telefonos_ni_ids(self):
        self.insertar("1234567890123456", "0.01", "Cliente 5512345678")
        r = self.agente.responder("libreta")
        self.assertIsNone(re.search(r"\d{10,}", r.texto), r.texto)
        self.assertNotIn("1234567890123456", r.texto)
        self.assertNotIn("5512345678", r.texto)

    def test_semana_incluye_dias_pasados_y_no_hoy(self):
        self.insertar("tx1", "0.01", "Taco", hace_horas=72)
        semana = self.agente.responder("esta semana")
        self.assertIn("Esta semana entró 1 pago por $0.01", semana.texto)
        self.assertIn("· $0.01 Taco", semana.texto)
        self.assertEqual(self.agente.responder("que cobre hoy").texto,
                         "Hoy no ha entrado ningún pago.")


if __name__ == "__main__":
    unittest.main()
