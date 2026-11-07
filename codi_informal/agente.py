"""El bot. WhatsApp y la nota de voz llegan aquí como texto y piden el mismo cobro."""

import base64
import re
import time

from codi_informal.pey import PeyError, dinero, telefono_mx
from codi_informal.registro import listar

AYUDA = (
    "Soy el bot de cobros. Escríbeme, por ejemplo: cobra 0.01 al 5512345678. "
    "O pídeme: manda el qr del puesto."
)

VOZ_SIN_TRANSCRIPCION = (
    "Recibí una nota de voz y todavía no la puedo transcribir. "
    "Escríbeme: cobra 0.01 al 5512345678."
)

_COBRA = re.compile(
    r"cobra(?:r|me)?\s+\$?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:pesos?)?\s*(?:a|al)\s*([+\d][\d\s-]{8,22})",
    re.IGNORECASE,
)
_LISTA = re.compile(r"qu[eé] se ha cobrado|movimientos|registro", re.IGNORECASE)
_QR = re.compile(r"\bqr\b", re.IGNORECASE)


class Resultado:
    def __init__(self, texto: str, imagen: bytes | None = None):
        self.texto = texto
        self.imagen = imagen


class Agente:
    def __init__(self, pey, conn, *, max_amount="0.01"):
        self.pey = pey
        self.conn = conn
        self.max_amount = dinero(max_amount)

    def responder(self, texto: str) -> Resultado:
        limpio = " ".join((texto or "").split())
        if not limpio:
            return Resultado(AYUDA)
        if _LISTA.search(limpio):
            return Resultado(self._lista())
        cobro = _COBRA.search(limpio)
        if cobro:
            return self._push(cobro.group(1), cobro.group(2))
        if _QR.search(limpio):
            return self._qr()
        return Resultado(AYUDA)

    def _push(self, amount_raw: str, phone_raw: str) -> Resultado:
        try:
            monto = dinero(amount_raw)
        except Exception:
            return Resultado(AYUDA)
        tel = telefono_mx(phone_raw)
        if tel is None:
            return Resultado("El celular tiene que ser de 10 dígitos.")
        if monto <= 0 or monto > self.max_amount:
            return Resultado(
                f"Ese monto pasa el tope de prueba de ${self.max_amount}. "
                "Los pagos de prueba no se devuelven."
            )
        if self.pey is None:
            return Resultado(
                f"Entendí: cobrar ${monto} al {tel}. Falta PEY_API_KEY, así que no lo envié."
            )
        try:
            respuesta = self.pey.push(
                amount=monto,
                phone=tel,
                concept="Cobro del puesto",
                metadata={"canal": "whatsapp", "puesto": "puesto"},
                num_ref=_referencia(),
            )
        except PeyError as exc:
            return Resultado(f"pey no pudo cobrar: {exc.message}")
        folio = respuesta.get("codiId") or respuesta.get("transactionId") or ""
        return Resultado(
            f"Le mandé el cobro de ${monto} al {tel}. "
            f"Le llega una notificación de su banco. Folio {folio}."
        )

    def _qr(self) -> Resultado:
        if self.pey is None:
            return Resultado(
                f"Entendí: QR del puesto por ${self.max_amount}. "
                "Falta PEY_API_KEY, así que no lo pedí."
            )
        try:
            respuesta = self.pey.qr(
                amount=self.max_amount,
                concept="Puesto",
                metadata={"canal": "whatsapp", "puesto": "puesto"},
                num_ref=_referencia(),
            )
        except PeyError as exc:
            return Resultado(f"pey no pudo armar el QR: {exc.message}")
        return Resultado(
            f"QR del puesto por ${self.max_amount}. Se puede dejar pegado. "
            "Cuando alguien pague, aviso por aquí.",
            _png(respuesta.get("qrImage")),
        )

    def _lista(self) -> str:
        if self.conn is None:
            return "Todavía no hay registro."
        filas = listar(self.conn)
        if not filas:
            return "Todavía no entra ningún pago."
        lineas = ["Pagos que ya entraron:"]
        for fila in filas:
            lineas.append(f"- ${fila['amount']} {fila.get('concept') or ''} ({fila['transaction_id']})")
        return "\n".join(lineas)


def atender(entrada: dict, agente: Agente, transcribir=None) -> Resultado | None:
    tipo = entrada.get("tipo")
    if tipo == "audio":
        if transcribir is None:
            return Resultado(VOZ_SIN_TRANSCRIPCION)
        return agente.responder(transcribir(entrada.get("audio_id")))
    if tipo == "text":
        return agente.responder(entrada.get("texto") or "")
    return None


def _referencia() -> str:
    return str(int(time.time()))[-7:]


def _png(valor) -> bytes | None:
    if not isinstance(valor, str) or not valor:
        return None
    try:
        return base64.b64decode(valor)
    except Exception:
        return None
