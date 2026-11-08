"""Lectura de ticket. El lector (visión) es un callable inyectado; nada se guarda."""

import re
from decimal import Decimal, InvalidOperation

_CUENTA = re.compile(r"\d[\d\s-]{6,}\d")
_MONTO = re.compile(r"^\d+(?:,\d{3})*(?:\.\d{2})?$")


def leer(imagen_bytes, *, lector):
    """`lector(bytes) -> {"monto", "concepto"}`. Devuelve monto y concepto o None.
    Solo montos en formato explicito: "12", "12.50" o "1,234.50" (la coma agrupa miles
    de a tres). La imagen no se escribe a disco y los numeros largos (cuentas, CLABEs) se quitan."""
    if not imagen_bytes or lector is None:
        return None
    try:
        crudo = lector(imagen_bytes)
        crudo_monto = str(crudo["monto"]).strip()
        if not _MONTO.fullmatch(crudo_monto):
            return None
        monto = Decimal(crudo_monto.replace(",", ""))
    except (Exception, InvalidOperation):
        return None
    if not monto.is_finite() or monto <= 0 or monto != monto.quantize(Decimal("0.01")):
        return None
    concepto = _CUENTA.sub("", str(crudo.get("concepto") or ""))
    return {"monto": monto, "concepto": " ".join(concepto.split()) or "Ticket"}
