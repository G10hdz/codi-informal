# Varísimo: capa CoDi para la economía informal

Hackatón OpenAI DevDay Exchange, Ciudad de México, 7 y 8 de noviembre de 2026.

## Tesis

Atacamos la informalidad financiera de México con CoDi.

El tianguis cobra en efectivo, sin comprobante, y si el dueño no está, todo es llamadas y fotos de tickets. La tanda funciona por confianza, y si quien administra el dinero desaparece, se acabó el ahorro. En los dos casos no queda registro, así que esa gente no construye historial.

Una sola capa de CoDi cubre las tres cosas: QR y push con comprobante para el tianguis, tandas donde el pago se ejecuta y nadie se puede llevar el dinero, y un registro que es el primer paso hacia historial.

El diferenciador que salió en la junta: compras colectivas entre comercios de tianguis, y la red de puntos comunitarios para mandado, tandas y compras entre vecinos. Alguien del equipo ya armó esa red en una plaza. Se puede extender a tianguis.

No es otra app de tandas ni otro QR. Es infraestructura de pagos para la economía informal.

## Lo que ya vimos en vivo

La demo de CoDi cobró $0.01 con dos modos: QR y notificación push. Para el puesto encaja mejor la push. El dueño deja un QR fijo en el local y le llega un aviso por cada pago, aunque no esté atendiendo. Se acaban la llamada y la foto del ticket.

CoDi pide cuenta de banco. El comercio informal no necesita estar dado de alta en el SAT para recibir.

## Corte de este hackatón

No hay frontend. Quien cobra y quien prueba hablan con un bot de WhatsApp.

1. El dueño escribe, o manda una nota de voz: `cobra 0.01 al 5512345678`. El bot pide a pey un push de CoDi. A quien paga le llega el aviso en la app de su banco.
2. El bot también puede armar el QR del puesto y mandarlo por el mismo chat, para dejarlo pegado. Si el dueño no está, el pago igual entra.
3. Cuando pey avisa que el pago llegó, el bot se lo dice al dueño por WhatsApp y lo guarda. Sin foto del ticket y sin llamada.
4. El tope de prueba es $0.01. Esos pagos no se devuelven. Subirlo es cambiar `PEY_MAX_AMOUNT`.

La nota de voz no es otra pantalla: es el mismo bot. Si todavía no hay llave para transcribir, el bot pide el mensaje escrito.

La tanda automática, las compras colectivas y la red de puntos se cuentan en el pitch como el siguiente uso de esta misma capa. No se construyen completas hoy.

Altagracia no escribe código. Prueba el bot como lo usaría alguien del puesto: manda el mensaje, ve si se entiende y dice dónde se atora. Si ella se atora, el flujo no está listo.

## Entrega

- Límite: domingo 8 de noviembre de 2026, 1:00 p.m.
- Correo: hola@aibuilders.lat
- Ganadores: lunes 9 de noviembre, por correo.
- Premios de OpenAI: 500, 300 y 200 dólares en créditos.
- API: https://docs.pey.mx
- Portal: https://portal.pey.mx
- Alta normal ante Banxico: cerca de cinco días. Por eso el hackatón presta CLABEs de prueba. Esas cuentas viven en el correo "INSTRUCCIONES Y PREMIOS". No van en este repo. Las pruebas son de $0.01 y no se devuelven.

## Fuera de alcance

- Una página o una app. El corte es el bot de WhatsApp.
- Otra app de tandas.
- NFC. Salió en la junta y se queda anotado.
- Verificación de identidad por voz ante Banxico. pey no tiene ese endpoint. La voz aquí solo dicta el cobro.
