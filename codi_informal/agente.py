"""El bot. WhatsApp y la nota de voz llegan aquí como texto y piden el mismo cobro."""

import base64
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from codi_informal.confirmacion import Confirmaciones
from codi_informal.png import a_rgb
from codi_informal.pey import PeyError, PeyIncierto, centavos, pesos, telefono_mx, tope_centavos
from codi_informal.registro import aviso, crear_operacion, listar, marcar_operacion, pagos_desde, tiene_incierto

AYUDA = (
    "Soy Varísimo, el bot de cobros. Escríbeme, por ejemplo: cobra 0.01 al 5512345678. "
    "O pídeme: manda el qr del puesto."
)

VOZ_SIN_TRANSCRIPCION = (
    "Recibí una nota de voz y todavía no la puedo transcribir. "
    "Escríbeme: cobra 0.01 al 5512345678."
)

TICKET_ILEGIBLE = (
    "Recibí la foto del ticket pero no pude leer el total. "
    "Escríbeme: cobra 0.01 al 5512345678."
)

SIN_REGISTRO = "No hay registro donde guardar la operación, así que no cobro."
INCIERTO = (
    "No sé si el cobro salió: pey no respondió a tiempo. No lo reintento para no cobrar doble. "
    "Revisa con el operador antes de pedirlo otra vez."
)
EN_CURSO = "Hay otro cobro en curso o sin resolver. Espera a que termine antes de pedir otro."
BLOQUEO_INCIERTO = (
    "Tienes un cobro sin resolver: el anterior quedó en duda y pudo haberse creado. "
    "Revísalo con el operador antes de pedir otro, para no cobrar doble."
)
PAUSADOS = (
    "Los cobros están en pausa por ahora. "
    "Los pagos que ya iban en camino se siguen registrando."
)

_COBRA = re.compile(
    r"cobra(?:r|me)?\s+\$?\s*(-?[\d.,]+)\s*(?:pesos?)?\s*(?:a|al)\s*(?:(?:n[uú]mero|cel(?:ular)?|tel[eé]fono)\s*)?([+\d][\d\s-]{8,22})",
    re.IGNORECASE,
)
_CONFIRMA = re.compile(r"confirmar\s+([0-9A-F]{6})", re.IGNORECASE)
_LISTA = re.compile(r"qu[eé] se ha cobrado|movimientos|registro", re.IGNORECASE)
_LIBRETA = re.compile(
    r"\b(?:qu[eé]? cobr[eé]|cu[aá]nto cobr[eé]|resumen|libreta|semana)\b",
    re.IGNORECASE,
)
_QR = re.compile(r"\bqr\b", re.IGNORECASE)

AVISO_DINERO = "La prueba mueve dinero real y no se devuelve."
CONCEPTO = "Cobro del puesto"


class Resultado:
    def __init__(self, texto: str, imagen: bytes | None = None, qr_texto: str | None = None):
        self.texto = texto
        self.imagen = imagen
        self.qr_texto = qr_texto


class Agente:
    def __init__(self, pey, conn, *, max_amount="0.01", reloj=time.monotonic,
                 cobros_activos=True, fecha=None):
        self.pey = pey
        self.conn = conn
        self.max_cents = tope_centavos(max_amount)  # None: cobros deshabilitados
        self.cobros_activos = cobros_activos
        self.confirmaciones = Confirmaciones(reloj)
        self.fecha = fecha or datetime.now

    def responder(self, texto: str, dueno: str = "local", chat: str = "local") -> Resultado:
        limpio = " ".join((texto or "").split())
        if not limpio:
            return Resultado(AYUDA)
        confirma = _CONFIRMA.fullmatch(limpio)
        if confirma:
            return self._confirmar(confirma.group(1), dueno, chat)
        if _LISTA.search(limpio):
            return Resultado(self._lista())
        if _LIBRETA.search(limpio):
            return Resultado(self._libreta(semana="semana" in limpio.lower()))
        cobro = _COBRA.search(limpio)
        if cobro:
            return self.cobrar(cobro.group(2), cobro.group(1), CONCEPTO, dueno=dueno, chat=chat)
        if _QR.search(limpio):
            return self._qr(dueno, chat)
        return Resultado(AYUDA)

    def cobrar(self, telefono, monto, concepto=CONCEPTO, *, dueno="local", chat="local") -> Resultado:
        """Punto único de entrada del cobro push: valida y deja un borrador por confirmar."""
        if not self.cobros_activos:
            return Resultado(PAUSADOS)
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
        if not self.cobros_activos:
            return Resultado(PAUSADOS)
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
        if op is None:
            return Resultado(EN_CURSO)
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
        if not self.cobros_activos:
            return Resultado(PAUSADOS)
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
        if op is None:
            return Resultado(EN_CURSO)
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
        return Resultado(texto, _png(respuesta.get("qrImage")), qr_texto=respuesta.get("qrString"))

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

    def _libreta(self, semana: bool = False) -> str:
        if self.conn is None:
            return "Todavía no hay registro."
        etiqueta = "Esta semana" if semana else "Hoy"
        filas = pagos_desde(self.conn, _desde(semana, self.fecha))
        if not filas:
            return f"{etiqueta} no ha entrado ningún pago."
        total = sum((Decimal(fila["amount"]) for fila in filas), Decimal("0"))
        if len(filas) == 1:
            lineas = [f"{etiqueta} entró 1 pago por ${total:.2f}:"]
        else:
            lineas = [f"{etiqueta} entraron {len(filas)} pagos por ${total:.2f}:"]
        for fila in filas[:5]:
            concepto = " ".join(re.sub(r"\d{10,}", " ", str(fila.get("concept") or "")).split())
            hora = _hora(fila["created_at"])
            lineas.append(" ".join(p for p in [f"· ${fila['amount']}", concepto, hora] if p))
        return "\n".join(lineas)


def atender(entrada: dict, agente: Agente, transcribir=None, leer_imagen=None, *,
            dueno: str = "local", chat: str = "local") -> Resultado | None:
    tipo = entrada.get("tipo")
    if tipo == "audio":
        texto = transcribir(entrada.get("audio_id")) if transcribir else None
        texto = " ".join(texto.split()) if isinstance(texto, str) else None
        if not texto:
            return Resultado(VOZ_SIN_TRANSCRIPCION)
        return agente.responder(texto, dueno=dueno, chat=chat)
    if tipo == "image":
        # se dice lo leído y el cobro lo pide la persona por texto: nada va a pey aquí
        try:
            leido = leer_imagen(entrada.get("imagen_id")) if leer_imagen else None
        except Exception:
            leido = None
        if not isinstance(leido, dict) or leido.get("monto") is None:
            return Resultado(TICKET_ILEGIBLE)
        concepto = " ".join(str(leido.get("concepto") or "ticket").split())
        return Resultado(
            f"Leí ${leido['monto']} por {concepto}. "
            f"Para cobrarlo escribe: cobra {leido['monto']} al <teléfono>"
        )
    if tipo == "text":
        return agente.responder(entrada.get("texto") or "", dueno=dueno, chat=chat)
    return None


def _referencia() -> str:
    return str(int(time.time()))[-7:]


def _desde(semana: bool, fecha) -> str:
    """Marca ISO (UTC) desde la que cuentan los pagos: hoy local o los últimos 7 días."""
    ahora = fecha()
    if semana:
        return (ahora.astimezone(timezone.utc) - timedelta(days=7)).isoformat()
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio.astimezone(timezone.utc).isoformat()


def _hora(created_at: str) -> str:
    try:
        return datetime.fromisoformat(created_at).astimezone().strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def _png(valor) -> bytes | None:
    """qrImage de pey -> bytes de imagen, o None si no es PNG ni JPEG.

    Acepta base64 suelto o con prefijo data:. Bytes que no son imagen se
    descartan para que el QR salga como texto en vez de una imagen rota."""
    if not isinstance(valor, str) or not valor:
        return None
    if valor.startswith("data:") and "," in valor:
        valor = valor.split(",", 1)[1]
    try:
        datos = base64.b64decode("".join(valor.split()), validate=True)
    except Exception:
        return None
    if datos.startswith(b"\xff\xd8\xff"):
        return datos
    # WhatsApp solo acepta PNG RGB/RGBA de 8 bits; el QR de pey puede venir en 1 bit
    return a_rgb(datos)
