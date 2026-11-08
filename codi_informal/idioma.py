"""Idioma de la respuesta. La orden parseada no cambia, solo el texto."""

import re

_ES = {"cobra", "cobrar", "al", "a", "por", "favor", "el", "la", "de", "que", "se", "ha", "cobrado",
       "manda", "mandame", "pesos", "puesto", "hola", "gracias", "cuanto", "y", "un", "una", "del", "los"}
_EN = {"charge", "please", "to", "the", "for", "of", "and", "send", "what", "has", "been", "collected",
       "order", "pesos", "hello", "thanks", "hi", "my", "is", "a", "an", "how", "much"}
# palabras compartidas no cuentan: "a" y "pesos" aparecen en los dos
_ES -= _EN
_EN -= {"pesos"}

_MENSAJES = {
    "AYUDA": {
        "es": "Soy el bot de cobros. Escríbeme, por ejemplo: cobra 0.01 al 5512345678. "
              "O pídeme: manda el qr del puesto.",
        "en": "I am the payments bot. Write to me, for example: cobra 0.01 al 5512345678. "
              "Or ask: send the stall's qr.",
    },
    "TOPE": {
        "es": "Ese monto pasa el tope de prueba de ${tope}. Los pagos de prueba no se devuelven.",
        "en": "That amount is over the test limit of ${tope}. Test payments are not refunded.",
    },
    "CELULAR": {
        "es": "El celular tiene que ser de 10 dígitos.",
        "en": "The phone number must have 10 digits.",
    },
    "VOZ_SIN_TRANSCRIPCION": {
        "es": "Recibí una nota de voz y todavía no la puedo transcribir. Escríbeme: cobra 0.01 al 5512345678.",
        "en": "I got a voice note but I cannot transcribe it yet. Please write: cobra 0.01 al 5512345678.",
    },
}


def detectar(texto):
    """'es', 'en' o None si no hay señal clara."""
    palabras = re.findall(r"[a-záéíóúñ]+", (texto or "").lower())
    es = sum(p in _ES for p in palabras)
    en = sum(p in _EN for p in palabras)
    if es == en:
        return None
    return "es" if es > en else "en"


def mensaje(clave, idioma, **datos):
    textos = _MENSAJES[clave]
    return textos.get(idioma, textos["es"]).format(**datos)
