# 0001. La puerta es WhatsApp

## Contexto

El puesto cobra en efectivo. Si el dueño no está, el comprobante es una llamada o una foto. La mitad de quien trabaja en el país está en la informalidad y no va a instalar otra app para un cobro de unos pesos. pey ya manda el push de CoDi al celular y ya arma el QR.

## Decisión

No hay frontend. El agente vive en WhatsApp: texto, nota de voz, foto del ticket y el aviso de que el pago entró. NFC, cuando exista, solo identifica el puesto y reusa ese cobro.

## Consecuencias

Hace falta un número de WhatsApp y una URL pública para el webhook. Sin eso el hackatón no está usable, aunque el repo tenga tests. La voz y la foto no crean otro flujo de dinero. Un tap NFC no autoriza a inventar un endpoint que pey no documenta.

## Estado

Aceptada para el corte del 7 y 8 de noviembre de 2026.
