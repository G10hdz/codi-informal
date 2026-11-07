# Capa CoDi para la economía informal

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

Lo que se puede enseñar antes del domingo a la 1:00 p.m.:

1. Cobro CoDi por push a un puesto. El dueño ausente recibe el aviso.
2. Registro de ese pago, con comprobante, sin foto ni llamada.
3. Si da el tiempo, una tanda de prueba donde el pago no depende de que alguien guarde el efectivo.

Compras colectivas y la red de puntos se cuentan en el pitch como el siguiente uso de la misma capa. No se construyen las dos completas hoy.

## Entrega

- Límite: domingo 8 de noviembre de 2026, 1:00 p.m.
- Correo: hola@aibuilders.lat
- Ganadores: lunes 9 de noviembre, por correo.
- Premios de OpenAI: 500, 300 y 200 dólares en créditos.
- API: https://docs.pey.mx
- Portal: https://portal.pey.mx
- Alta normal ante Banxico: cerca de cinco días. Por eso el hackatón presta CLABEs de prueba. Esas cuentas viven en el correo "INSTRUCCIONES Y PREMIOS". No van en este repo. Las pruebas son de $0.01 y no se devuelven.

## Fuera de alcance

- Otra app de tandas.
- Otro QR genérico, sin el caso del dueño ausente.
- NFC, agente de voz y teclado de WhatsApp. Salieron en la junta y se quedan anotados. No entran al corte de mañana.
