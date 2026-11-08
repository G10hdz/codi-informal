"""PNG a RGB de 8 bits, solo stdlib.

WhatsApp rechaza (131053) los PNG que no son RGB/RGBA de 8 bits, y el QR de pey
puede venir en gris o paleta de 1 bit. Esto lo redibuja como RGB de 8 bits.
"""

import struct
import zlib

FIRMA = b"\x89PNG\r\n\x1a\n"
_CANALES = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
MAX_PIXELES = 4_000_000


def _chunk(tipo: bytes, datos: bytes) -> bytes:
    return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _quitar_filtros(crudo: bytes, alto: int, paso: int, bpp: int) -> list:
    filas, previa = [], bytearray(paso)
    for i in range(alto):
        base = i * (paso + 1)
        tipo, fila = crudo[base], bytearray(crudo[base + 1:base + 1 + paso])
        if len(fila) != paso:
            raise ValueError("fila corta")
        for x in range(paso):
            a = fila[x - bpp] if x >= bpp else 0
            b = previa[x]
            c = previa[x - bpp] if x >= bpp else 0
            if tipo == 1:
                fila[x] = (fila[x] + a) & 255
            elif tipo == 2:
                fila[x] = (fila[x] + b) & 255
            elif tipo == 3:
                fila[x] = (fila[x] + (a + b) // 2) & 255
            elif tipo == 4:
                fila[x] = (fila[x] + _paeth(a, b, c)) & 255
            elif tipo != 0:
                raise ValueError("filtro desconocido")
        filas.append(fila)
        previa = fila
    return filas


def _muestras(fila: bytes, ancho: int, canales: int, prof: int) -> list:
    """-> valores por muestra, sin escalar."""
    n = ancho * canales
    if prof == 8:
        return list(fila[:n])
    if prof == 16:
        return [fila[2 * i] for i in range(n)]  # byte alto basta para 8 bits
    por_byte, mascara = 8 // prof, (1 << prof) - 1
    salida = []
    for i in range(n):
        byte = fila[i // por_byte]
        salida.append((byte >> (8 - prof * (i % por_byte + 1))) & mascara)
    return salida


def a_rgb(datos: bytes) -> bytes | None:
    """PNG cualquiera -> PNG RGB de 8 bits, o None si no se puede leer."""
    try:
        if not datos.startswith(FIRMA):
            return None
        pos, idat, plte, ihdr = 8, b"", b"", None
        while pos + 8 <= len(datos):
            largo, tipo = struct.unpack(">I4s", datos[pos:pos + 8])
            cuerpo = datos[pos + 8:pos + 8 + largo]
            if tipo == b"IHDR":
                ihdr = struct.unpack(">IIBBBBB", cuerpo)
            elif tipo == b"PLTE":
                plte = cuerpo
            elif tipo == b"IDAT":
                idat += cuerpo
            elif tipo == b"IEND":
                break
            pos += 12 + largo
        if ihdr is None:
            return None
        ancho, alto, prof, color, _, _, entrelazado = ihdr
        # ponytail: sin Adam7; un QR entrelazado cae al texto del QR
        if entrelazado or color not in _CANALES or ancho * alto > MAX_PIXELES:
            return None
        canales = _CANALES[color]
        bits = canales * prof
        paso, bpp = (ancho * bits + 7) // 8, max(1, bits // 8)
        filas = _quitar_filtros(zlib.decompress(idat), alto, paso, bpp)
        escala = 255 // ((1 << prof) - 1) if prof < 8 else 1
        salida = bytearray()
        for fila in filas:
            salida.append(0)
            m = _muestras(fila, ancho, canales, prof)
            for x in range(ancho):
                px = m[x * canales:(x + 1) * canales]
                if color == 3:
                    rgb = plte[px[0] * 3:px[0] * 3 + 3]
                    if len(rgb) != 3:
                        raise ValueError("indice fuera de la paleta")
                    salida += rgb
                    continue
                if color in (0, 4):
                    rgb, alfa = [px[0] * escala] * 3, (px[1] if color == 4 else 255)
                else:
                    rgb, alfa = px[:3], (px[3] if color == 6 else 255)
                # alfa sobre fondo blanco
                salida += bytes((v * alfa + 255 * (255 - alfa)) // 255 for v in rgb)
        cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
        return FIRMA + _chunk(b"IHDR", cabecera) + _chunk(b"IDAT", zlib.compress(bytes(salida))) + _chunk(b"IEND", b"")
    except (ValueError, IndexError, struct.error, zlib.error):
        return None
