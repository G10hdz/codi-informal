import struct
import unittest
import zlib

from codi_informal.png import a_rgb


def _chunk(tipo, datos):
    return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))


def _png(ancho, alto, profundidad, color, filas, plte=None):
    ihdr = struct.pack(">IIBBBBB", ancho, alto, profundidad, color, 0, 0, 0)
    crudo = b"".join(b"\x00" + f for f in filas)
    cuerpo = _chunk(b"IHDR", ihdr)
    if plte:
        cuerpo += _chunk(b"PLTE", plte)
    return b"\x89PNG\r\n\x1a\n" + cuerpo + _chunk(b"IDAT", zlib.compress(crudo)) + _chunk(b"IEND", b"")


def _leer(png):
    """-> (ancho, alto, profundidad, color, pixeles RGB por fila)"""
    pos, idat = 8, b""
    while pos < len(png):
        largo, tipo = struct.unpack(">I4s", png[pos:pos + 8])
        datos = png[pos + 8:pos + 8 + largo]
        if tipo == b"IHDR":
            ancho, alto, prof, color = struct.unpack(">IIBB", datos[:10])
        elif tipo == b"IDAT":
            idat += datos
        pos += 12 + largo
    crudo = zlib.decompress(idat)
    paso = ancho * 3 + 1
    filas = [crudo[i * paso + 1:(i + 1) * paso] for i in range(alto)]
    return ancho, alto, prof, color, filas


class PngTests(unittest.TestCase):
    def test_gris_de_1_bit_sale_rgb_de_8_bits(self):
        # 3x2: fila 0 negro, blanco, negro; fila 1 blanco, negro, blanco
        png = _png(3, 2, 1, 0, [bytes([0b01000000]), bytes([0b10100000])])
        ancho, alto, prof, color, filas = _leer(a_rgb(png))
        self.assertEqual((ancho, alto, prof, color), (3, 2, 8, 2))
        self.assertEqual(filas[0], bytes([0, 0, 0, 255, 255, 255, 0, 0, 0]))
        self.assertEqual(filas[1], bytes([255, 255, 255, 0, 0, 0, 255, 255, 255]))

    def test_paleta_de_1_bit_usa_sus_colores(self):
        plte = bytes([10, 20, 30, 200, 210, 220])
        png = _png(2, 1, 1, 3, [bytes([0b01000000])], plte=plte)
        _, _, prof, color, filas = _leer(a_rgb(png))
        self.assertEqual((prof, color), (8, 2))
        self.assertEqual(filas[0], bytes([10, 20, 30, 200, 210, 220]))

    def test_rgba_se_pinta_sobre_blanco(self):
        png = _png(1, 1, 8, 6, [bytes([0, 0, 0, 0])])
        self.assertEqual(_leer(a_rgb(png))[4][0], bytes([255, 255, 255]))

    def test_filtro_sub_se_deshace(self):
        ihdr = struct.pack(">IIBBBBB", 2, 1, 8, 0, 0, 0, 0)
        crudo = b"\x01" + bytes([100, 50])  # Sub: segundo pixel = 100 + 50
        png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
               + _chunk(b"IDAT", zlib.compress(crudo)) + _chunk(b"IEND", b""))
        self.assertEqual(_leer(a_rgb(png))[4][0], bytes([100] * 3 + [150] * 3))

    def test_basura_da_none(self):
        self.assertIsNone(a_rgb(b"\x89PNG\r\n\x1a\nbasura"))
        self.assertIsNone(a_rgb(b"no es png"))


if __name__ == "__main__":
    unittest.main()
