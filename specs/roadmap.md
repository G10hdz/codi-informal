# Roadmap

Cada fase se puede trabajar en su worktree y su PR. No se salta a la siguiente si la anterior no está usable en WhatsApp.

## 0. Hackatón, hasta el domingo 8 de noviembre de 2026 a la 1:00 p.m.

Specs: `01-whatsapp-codi.md`.

Texto, push, QR con monto fijo, webhook y registro sin CLABE. Tope $0.01. Desplegado, con llave de pey y número de WhatsApp, para que Altagracia lo pruebe.

La rama `feature/bot-whatsapp` trae el esqueleto. Sin las llaves sigue siendo local.

## 1. Voz

Specs: REQ-8, REQ-9 y REQ-10.

La nota de voz entra al mismo cobro. Si no hay transcriptor, el bot pide el texto.

## 2. Idiomas

Specs: REQ-11 y REQ-12.

Español seguro. Otro idioma solo cuando el detector está seguro. El JSON hacia pey no cambia.

## 3. Foto del ticket

Specs: REQ-13, REQ-14 y REQ-15.

Lee monto y concepto. Cobra solo después del sí. No guarda la foto.

## 4. NFC

Specs: `03-nfc.md`.

El tap nombra al puesto. El dinero sigue yendo por QR o push.

## 5. Comunidad

Specs: `04-comunidad.md`.

Tanda sin administrador que se lleve el efectivo. Luego la compra compartida y el punto de mandado.

## Después, si la fase 0 ya se usa

El registro de esos pagos es el historial. No se promete crédito ni alta en el SAT.
