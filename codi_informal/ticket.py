"""Lectura de ticket. El lector (visión) es un callable inyectado; nada se guarda."""

import re
from decimal import Decimal, InvalidOperation

_CUENTA = re.compile(r"\d[\d\s-]{6,}\d")


def leer(imagen_bytes, *, lector):
    """`lector(bytes) -> {"monto", "concepto"}`. Devuelve monto y concepto o None.
    La imagen no se escribe a disco y los números largos (cuentas, CLABEs) se quitan."""
    if not imagen_bytes or lector is None:
        return None
    try:
        crudo = lector(imagen_bytes)
        monto = Decimal(str(crudo["monto"]).strip().replace(",", ""))
    except (Exception, InvalidOperation):
        return None
    if not monto.is_finite() or monto <= 0 or monto != monto.quantize(Decimal("0.01")):
        return None
    concepto = _CUENTA.sub("", str(crudo.get("concepto") or ""))
    return {"monto": monto, "concepto": " ".join(concepto.split()) or "Ticket"}
