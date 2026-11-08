"""Cliente mínimo de la API pública de pey. Los campos salen de docs/pey-api.md."""

import json
import re
import urllib.error
import urllib.request
from decimal import Decimal


API_MAX_CENTAVOS = 1_000_000 * 100
TOPE_DEMO_CENTAVOS = 1
_MONTO = re.compile(r"(\d{1,9})(?:[.,](\d{1,2}))?")


class PeyError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class PeyIncierto(PeyError):
    """El POST no terminó: pey pudo haber creado el cobro. No se reintenta."""

    def __init__(self, message: str = "pey no respondió a tiempo"):
        super().__init__(0, message)


def centavos(valor) -> int:
    """Monto en centavos enteros. Rechaza lo que no sea pesos con hasta 2 decimales."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError("monto inválido")
    coincide = _MONTO.fullmatch(str(valor).strip())
    if coincide is None:
        raise ValueError("monto inválido")
    return int(coincide.group(1)) * 100 + int((coincide.group(2) or "0").ljust(2, "0"))


def tope_centavos(valor) -> int | None:
    """Tope de prueba. Ausente usa 1 centavo; inválido o mayor a 1 centavo: None (sin cobros)."""
    if valor is None:
        return TOPE_DEMO_CENTAVOS
    try:
        monto = centavos(valor)
    except ValueError:
        return None
    return monto if 0 < monto <= TOPE_DEMO_CENTAVOS else None


def pesos(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)


def dinero(valor) -> Decimal:
    return pesos(centavos(valor))


def telefono_mx(raw: str) -> str | None:
    digitos = "".join(caracter for caracter in raw if caracter.isdigit())
    if len(digitos) == 13 and digitos.startswith("521"):
        digitos = digitos[3:]
    elif len(digitos) == 12 and digitos.startswith("52"):
        digitos = digitos[2:]
    if len(digitos) == 10:
        return digitos
    return None


def _mensaje_error(payload: bytes) -> str:
    try:
        data = json.loads(payload.decode() or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return ""


class Pey:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.pey.mx",
        bank_account_id: str | None = None,
        max_amount: Decimal | str = "0.01",
        transport=None,
    ):
        if not api_key:
            raise PeyError(0, "falta PEY_API_KEY")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.bank_account_id = bank_account_id or None
        self.max_cents = tope_centavos(max_amount) or 0
        self.transport = transport

    def push(self, *, amount, phone: str, concept: str, metadata: dict | None = None, num_ref: str | None = None) -> dict:
        monto = self._tope(amount)
        tel = telefono_mx(phone)
        if tel is None:
            raise PeyError(400, "el celular tiene que ser de 10 dígitos")
        cuerpo = {"amount": float(monto), "phoneNumber": tel, "concept": concept}
        if num_ref:
            cuerpo["numRef"] = num_ref
        self._metadata(cuerpo, metadata)
        self._cuenta(cuerpo)
        return self._llamar("POST", "/codi/pn", cuerpo)

    def qr(self, *, amount, concept: str, metadata: dict | None = None, num_ref: str | None = None) -> dict:
        # amount 0 le deja el monto a quien escanea. En la cuenta de prueba eso no se devuelve.
        monto = self._tope(amount)
        cuerpo = {
            "amount": float(monto),
            "concept": concept,
            "expiration": 0,
            "generateImage": True,
        }
        if num_ref:
            cuerpo["numRef"] = num_ref
        self._metadata(cuerpo, metadata)
        self._cuenta(cuerpo)
        return self._llamar("POST", "/codi/qr", cuerpo)

    def _tope(self, amount) -> Decimal:
        try:
            cents = centavos(amount)
        except ValueError:
            raise PeyError(400, "monto inválido") from None
        if cents <= 0:
            raise PeyError(400, "el monto tiene que ser mayor que 0")
        if cents > API_MAX_CENTAVOS:
            raise PeyError(400, "pey no acepta más de 1000000")
        if self.max_cents == 0:
            raise PeyError(400, "cobros deshabilitados: PEY_MAX_AMOUNT inválido")
        if cents > self.max_cents:
            raise PeyError(400, "el monto pasa el tope de prueba")
        return pesos(cents)

    def _cuenta(self, cuerpo: dict) -> None:
        if self.bank_account_id:
            cuerpo["bankAccountId"] = self.bank_account_id

    def _metadata(self, cuerpo: dict, metadata: dict | None) -> None:
        if not metadata:
            return
        limpia = {}
        for llave, valor in list(metadata.items())[:50]:
            nombre = str(llave)[:40]
            if isinstance(valor, (dict, list)):
                raise PeyError(400, "metadata solo acepta valores simples")
            limpia[nombre] = valor
        cuerpo["metadata"] = limpia

    def _llamar(self, method: str, path: str, cuerpo: dict) -> dict:
        crudo = json.dumps(cuerpo).encode()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            if self.transport is not None:
                status, payload = self.transport(method, path, crudo, headers)
            else:
                status, payload = _http(self.base_url + path, method, crudo, headers)
        except OSError:
            # timeout o corte: pey pudo haber creado el cobro
            raise PeyIncierto() from None
        if status >= 400:
            raise PeyError(status, _mensaje_error(payload) or f"pey respondió {status}")
        if not payload:
            return {}
        return json.loads(payload)


def _http(url: str, method: str, crudo: bytes, headers: dict) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=crudo, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as respuesta:
            return respuesta.status, respuesta.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
