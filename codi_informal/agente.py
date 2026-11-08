"""El bot. WhatsApp y la nota de voz llegan aquí como texto y piden el mismo cobro."""

import base64
import re
import time

from codi_informal.confirmacion import Confirmaciones
from codi_informal.pey import PeyError, PeyIncierto, centavos, pesos, telefono_mx, tope_centavos
from codi_informal.registro import aviso, crear_operacion, listar, marcar_operacion, tiene_incierto

AYUDA = (
    "Soy el bot de cobros. Escríbeme, por ejemplo: cobra 0.01 al 5512345678. "
    "O pídeme: manda el qr del puesto."
)

VOZ_SIN_TRANSCRIPCION = (
    "Recibí una nota de voz y todavía no la puedo transcribir. "
    "Escríbeme: cobra 0.01 al 5512345678."
)

SIN_REGISTRO = "No hay registro donde guardar la operación, así que no cobro."
INCIERTO = (
    "No sé si el cobro salió: pey no respondió a tiempo. No lo reintento para no cobrar doble. "
    "Revisa con el operador antes de pedirlo otra vez."
)
BLOQUEO_INCIERTO = (
    "Tienes un cobro sin resolver: el anterior quedó en duda y pudo haberse creado. "
    "Revísalo con el operador antes de pedir otro, para no cobrar doble."
)

_COBRA = re.compile(
    r"cobra(?:r|me)?\s+\$?\s*(-?[\d.,]+)\s*(?:pesos?)?\s*(?:a|al)\s*([+\d][\d\s-]{8,22})",
    re.IGNORECASE,
)
_CONFIRMA = re.compile(r"confirmar\s+([0-9A-F]{6})", re.IGNORECASE)
_LISTA = re.compile(r"qu[eé] se ha cobrado|movimientos|registro", re.IGNORECASE)
_QR = re.compile(r"\bqr\b", re.IGNORECASE)

AVISO_DINERO = "La prueba mueve dinero real y no se devuelve."
CONCEPTO = "Cobro del puesto"


class Resultado:
    def __init__(self, texto: str, imagen: bytes | None = None):
        self.texto = texto
        self.imagen = imagen


class Agente:
    def __init__(self, pey, conn, *, max_amount="0.01", reloj=time.monotonic):
        self.pey = pey
        self.conn = conn
        self.max_cents = tope_centavos(max_amount)  # None: cobros deshabilitados
        self.confirmaciones = Confirmaciones(reloj)

    def responder(self, texto: str, dueno: str = "local", chat: str = "local") -> Resultado:
        limpio = " ".join((texto or "").split())
        if not limpio:
            return Resultado(AYUDA)
        confirma = _CONFIRMA.fullmatch(limpio)
        if confirma:
            return self._confirmar(confirma.group(1), dueno, chat)
        if _LISTA.search(limpio):
            return Resultado(self._lista())
        cobro = _COBRA.search(limpio)
        if cobro:
            return self.cobrar(cobro.group(2), cobro.group(1), CONCEPTO, dueno=dueno, chat=chat)
        if _QR.search(limpio):
            return self._qr(dueno, chat)
        return Resultado(AYUDA)

    def cobrar(self, telefono, monto, concepto=CONCEPTO, *, dueno="local", chat="local") -> Resultado:
        """Punto único de entrada del cobro push: valida y deja un borrador por confirmar."""
        try:
            cents = centavos(monto)
        except ValueError:
            return Resultado("No entendí el monto. Usa pesos con hasta dos decimales, por ejemplo 0.01.")
        tel = telefono_mx(str(telefono))
        if tel is None:
            return Resultado("El celular tiene que ser de 10 dígitos.")
        sin_cobro = self._no_se_puede(cents)
        if sin_cobro:
            return Resultado(sin_cobro)
        if self.pey is None:
            return Resultado(
                f"Entendí: cobrar ${pesos(cents)} al {tel}. Falta PEY_API_KEY, así que no lo envié."
            )
        if self.conn is None:
            return Resultado(SIN_REGISTRO)
        concepto = " ".join(str(concepto or CONCEPTO).split())[:100] or CONCEPTO
        datos = {"tipo": "push", "cents": cents, "telefono": tel, "concepto": concepto}
        return self._borrador(datos, f"cobrar ${pesos(cents)} MXN al {tel} ({concepto})", dueno, chat)

    def _no_se_puede(self, cents: int) -> str | None:
        if self.max_cents is None:
            return "Los cobros están deshabilitados: PEY_MAX_AMOUNT falta o no es válido (el máximo de la prueba es 0.01)."
        if cents <= 0 or cents > self.max_cents:
            return (
                f"Ese monto no pasa el tope de prueba de ${pesos(self.max_cents)}. "
                "Los pagos de prueba no se devuelven."
            )
        return None

    def _borrador(self, datos: dict, descripcion: str, dueno, chat) -> Resultado:
        if self.conn is not None and tiene_incierto(self.conn, dueno):
            return Resultado(BLOQUEO_INCIERTO)
        codigo = self.confirmaciones.crear(dueno, chat, datos)
        return Resultado(
            f"Voy a {descripcion}. {AVISO_DINERO} "
            f"Para seguir responde: confirmar {codigo}. Vence en 2 minutos."
        )

    def _confirmar(self, codigo: str, dueno, chat) -> Resultado:
        datos = self.confirmaciones.consumir(dueno, chat, codigo)
        if datos is None:
            return Resultado("No hay un cobro por confirmar con ese código, o ya venció. Pídelo de nuevo.")
        sin_cobro = self._no_se_puede(datos["cents"])  # se revalida al consumir
        if sin_cobro or self.conn is None or self.pey is None:
            return Resultado(sin_cobro or SIN_REGISTRO)
        if tiene_incierto(self.conn, dueno):
            return Resultado(BLOQUEO_INCIERTO)
        if datos["tipo"] == "qr":
            return self._ejecutar_qr(datos, dueno, chat)
        return self._ejecutar_push(datos, dueno, chat)

    def _crear(self, datos, dueno, chat):
        cuenta = getattr(self.pey, "bank_account_id", None)
        return crear_operacion(self.conn, dueno, chat, datos["tipo"], datos["cents"], datos["concepto"], cuenta)

    def _ejecutar_push(self, datos, dueno, chat) -> Resultado:
        op = self._crear(datos, dueno, chat)
        try:
            respuesta = self.pey.push(
                amount=pesos(datos["cents"]),
                phone=datos["telefono"],
                concept=datos["concepto"],
                metadata={"canal": "whatsapp", "puesto": "puesto"},
                num_ref=op["num_ref"],
            )
        except PeyIncierto:
            marcar_operacion(self.conn, op["op_id"], "incierto")
            return Resultado(INCIERTO)
        except PeyError as exc:
            marcar_operacion(self.conn, op["op_id"], "fallida")
            return Resultado(f"pey no pudo cobrar: {exc.message}")
        pagados = marcar_operacion(self.conn, op["op_id"], "creada",
                                   transaction_id=respuesta.get("transactionId"))
        folio = respuesta.get("codiId") or respuesta.get("transactionId") or ""
        texto = (
            f"Le mandé el cobro de ${pesos(datos['cents'])} al {datos['telefono']}. "
            f"Le llega una notificación de su banco. Folio {folio}. "
            "Esto no quiere decir que ya pagó: aviso cuando entre el pago."
        )
        for pago in pagados:
            texto += " " + aviso(pago)
        return Resultado(texto)

    def _qr(self, dueno, chat) -> Resultado:
        if self.pey is None:
            return Resultado(
                f"Entendí: QR del puesto por ${pesos(self.max_cents or 0)}. "
                "Falta PEY_API_KEY, así que no lo pedí."
            )
        sin_cobro = self._no_se_puede(self.max_cents or 0)
        if sin_cobro:
            return Resultado(sin_cobro)
        if self.conn is None:
            return Resultado(SIN_REGISTRO)
        datos = {"tipo": "qr", "cents": self.max_cents, "concepto": "Puesto"}
        return self._borrador(datos, f"armar el QR del puesto por ${pesos(self.max_cents)} MXN", dueno, chat)

    def _ejecutar_qr(self, datos, dueno, chat) -> Resultado:
        op = self._crear(datos, dueno, chat)
        try:
            respuesta = self.pey.qr(
                amount=pesos(datos["cents"]),
                concept=datos["concepto"],
                metadata={"canal": "whatsapp", "puesto": "puesto"},
                num_ref=op["num_ref"],
            )
        except PeyIncierto:
            marcar_operacion(self.conn, op["op_id"], "incierto")
            return Resultado(INCIERTO)
        except PeyError as exc:
            marcar_operacion(self.conn, op["op_id"], "fallida")
            return Resultado(f"pey no pudo armar el QR: {exc.message}")
        pagados = marcar_operacion(self.conn, op["op_id"], "creada", qr_id=respuesta.get("id"))
        texto = (
            f"QR del puesto por ${pesos(datos['cents'])}. Se puede dejar pegado. "
            "Cuando alguien pague, aviso por aquí."
        )
        for pago in pagados:
            texto += " " + aviso(pago)
        return Resultado(texto, _png(respuesta.get("qrImage")))

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


def atender(entrada: dict, agente: Agente, transcribir=None, *, dueno: str = "local", chat: str = "local") -> Resultado | None:
    tipo = entrada.get("tipo")
    if tipo == "audio":
        if transcribir is None:
            return Resultado(VOZ_SIN_TRANSCRIPCION)
        return agente.responder(transcribir(entrada.get("audio_id")), dueno=dueno, chat=chat)
    if tipo == "text":
        return agente.responder(entrada.get("texto") or "", dueno=dueno, chat=chat)
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
