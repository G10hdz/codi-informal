"""Cliente mínimo de la API pública de pey. Los campos salen de docs/pey-api.md."""

import json
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP


API_MAX = Decimal("1000000")


class PeyError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def dinero(valor) -> Decimal:
    if isinstance(valor, Decimal):
        monto = valor
    else:
        monto = Decimal(str(valor).strip().replace(",", "."))
    return monto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
        self.max_amount = dinero(max_amount)
        self.transport = transport

    def push(self, *, amount, phone: str, concept: str, metadata: dict | None = None, num_ref: str | None = None) -> dict:
        monto = self._tope(dinero(amount))
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
        monto = self._tope(dinero(amount))
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

    def _tope(self, monto: Decimal) -> Decimal:
        if monto <= 0:
            raise PeyError(400, "el monto tiene que ser mayor que 0")
        if monto > API_MAX:
            raise PeyError(400, "pey no acepta más de 1000000")
        if monto > self.max_amount:
            raise PeyError(400, f"el monto pasa el tope de prueba de {self.max_amount}")
        return monto

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
        if self.transport is not None:
            status, payload = self.transport(method, path, crudo, headers)
        else:
            status, payload = _http(self.base_url + path, method, crudo, headers)
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
