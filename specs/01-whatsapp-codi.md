# Cobro por WhatsApp con CoDi

Fase del hackatón. Depende de `00-plataforma.md`. Los campos de pey están en `docs/pey-api.md`.

## Flujo

El dueño escribe en WhatsApp. El bot pide a pey un push o un QR. Cuando pey avisa que el pago entró, el bot se lo dice al dueño y lo guarda.

## Criterios

REQ-1. WHILE el texto trae un monto y un celular, THE bot SHALL llamar `POST /codi/pn` con `phoneNumber` de 10 dígitos y `amount` mayor que 0.

Evidencia: un test con `+52 55 1234 5678` deja `5512345678` en el cuerpo y no llama a la red.

REQ-2. WHILE el monto pasa de `PEY_MAX_AMOUNT`, THE bot SHALL negarse y SHALL NOT llamar a pey.

Evidencia: el cliente de prueba rechaza 20 cuando el tope es 0.01, y el transporte no se invoca.

REQ-3. WHILE piden el QR del puesto, THE bot SHALL llamar `POST /codi/qr` con un monto fijo dentro del tope y SHALL NOT mandar `amount` 0.

Evidencia: el test de QR en cero no llega a pey. Cero le dejaría el monto a quien escanea, y en la cuenta de prueba ese pago no se devuelve.

REQ-4. WHILE llega un webhook `codi.pn.payment_received` o `codi.qr.payment_received` con firma válida, THE sistema SHALL guardar `transactionId`, monto y concepto, y SHALL NOT guardar la CLABE.

Evidencia: el sqlite de prueba no contiene la CLABE del payload. Una segunda entrega del mismo `transactionId` no duplica el aviso.

REQ-5. WHILE la firma del webhook falla o falta el secreto, THE sistema SHALL responder 401 y SHALL NOT escribir el registro.

Evidencia: el test del servidor contra `POST /webhooks/pey`.

REQ-6. WHILE no hay `PEY_API_KEY`, THE bot SHALL decir qué entendió y que no lo envió.

Evidencia: `POST /mensaje` con `cobra 0.01 al 5512345678`.

## No entra aquí

- NG-6. Links de pago de tarjeta, Apple Pay o Google Pay.
- NG-7. Cobrar más del tope para "verse más real" en la demo.
