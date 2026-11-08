# Roadmap

Cada fase se puede trabajar en su worktree y su PR. No se salta a la siguiente si la anterior no está usable.

## 0. Hackatón, hasta el domingo 8 de noviembre de 2026 a la 1:00 p.m.

Specs: `01-whatsapp-codi.md`.

Hecha. El bot desplegado cobró $0.01 de verdad, de punta a punta: push, pago en el banco, webhook y el aviso de que entró el pago. El cobro fue el domingo 8 de noviembre de 2026, antes del corte. Texto, push, QR con monto fijo, webhook y registro sin CLABE. Tope $0.01.

## 1. Voz

Specs: REQ-8 y REQ-9.

La nota de voz entra al mismo cobro. Si no hay transcriptor, el bot pide el texto.

## 2. Idiomas

Specs: REQ-11 y REQ-12.

Español seguro. Otro idioma solo cuando el detector está seguro. El JSON hacia pey no cambia.

## 3. Foto del ticket

Specs: REQ-13, REQ-14 y REQ-15.

Lee monto y concepto. Cobra solo después del sí. No guarda la foto.

## 4. Varios puestos y número real

Specs: `05-multitenant.md`.

Cada puesto con su dueño, su cuenta de pey y sus límites. El alta la hace un operador. Hace falta un número de WhatsApp verificado: el sandbox atiende a un solo teléfono.

## 5. Página del puesto

Specs: `06-front.md` y `03-nfc.md`.

URL pública por puesto y QR al momento. La pegatina NFC de `03-nfc.md` abre esa página. Sin CLABE ni teléfono del dueño.

## 6. Libreta

Specs: REQ-35 y REQ-36 de `06-front.md`.

Los pagos y los totales del puesto, por un link de un solo uso. Sin score de crédito.

## 7. Tanda

Specs: `04-comunidad.md`.

Integrantes, monto, orden de turnos y calendario. El cobro es el push de siempre y el dinero cae en la cuenta de quien tiene el turno, sin bote. Si alguien no paga, decide el grupo. Luego la compra compartida y el punto de mandado.

## 8. Agente de voz en vivo

Specs: REQ-10 y REQ-46 a REQ-48 de `02-voz-multimodal.md`.

Una llamada de voz al bot con las mismas órdenes del chat. Solo cobra para el dueño del puesto y pide el mismo código de confirmación que el chat.

## Después

El registro de esos pagos es el historial. No se promete crédito ni alta en el SAT.
